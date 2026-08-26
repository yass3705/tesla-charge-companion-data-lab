#!/usr/bin/env node
import fs from 'node:fs';
import zlib from 'node:zlib';
import { chromium } from 'playwright-core';

const INV='data/national/waat_direct_stations_france.json.gz';
const OUT='data/national/waat_monta_public_tariffs_france.json.gz';
const REPORT='data/reports/waat_monta_public_tariffs_report.json';
const inv=JSON.parse(zlib.gunzipSync(fs.readFileSync(INV)).toString('utf8'));
const stations=(inv.stations||[]).filter(s=>Array.isArray(s.coordinates)&&s.coordinates.length>=2);

const candidates=['/usr/bin/google-chrome','/usr/bin/google-chrome-stable','/usr/bin/chromium','/usr/bin/chromium-browser'];
const executablePath=candidates.find(fs.existsSync);
if(!executablePath) throw new Error('No Chromium/Chrome executable found');
const browser=await chromium.launch({executablePath,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const context=await browser.newContext({locale:'fr-FR',userAgent:'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',viewport:{width:1280,height:900}});
const page=await context.newPage();

let apiHeaders=null;
page.on('request',async req=>{
  if(apiHeaders||!req.url().includes('api.monta.app/api/v1/charge_points/map')) return;
  const h=await req.allHeaders();
  const keep=['authorization','operator','application','application-version','accept','accept-language'];
  const picked=Object.fromEntries(keep.filter(k=>h[k]).map(k=>[k,h[k]]));
  if(picked.authorization) apiHeaders=picked;
});

// Exact bootstrap already validated by the browser-capture workflow.
await page.goto('https://maps.monta.app/?lat=45.7045&lng=4.9445&zoom=16&locale=fr',{waitUntil:'domcontentloaded',timeout:60000});
for(let i=0;i<60&&!apiHeaders;i++) await page.waitForTimeout(500);
if(!apiHeaders?.authorization) throw new Error('Public Monta guest authorization header was not observed');

// All subsequent API calls are executed inside the public map browser origin. The anonymous
// guest credential remains memory-only and is never written to disk or logs.
async function fetchJson(url){
  return await page.evaluate(async ({url,headers})=>{
    try{
      const r=await fetch(url,{headers});
      const text=await r.text();
      let data=null;try{data=JSON.parse(text);}catch{}
      return {status:r.status,data,text:data?null:text.slice(0,2000)};
    }catch(e){return {status:0,data:null,text:String(e)}}
  },{url,headers:apiHeaders});
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const norm=s=>String(s??'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const isWaat=s=>/WAAT|FR\*?WA2/i.test(String(s??''));
const loc=g=>{const m=String(g?.location||'').match(/(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)/);return m?[+m[1],+m[2]]:null};
const dist=(a,b)=>{const R=6371000,r=x=>x*Math.PI/180,d1=r(b[0]-a[0]),d2=r(b[1]-a[1]),p1=r(a[0]),p2=r(b[0]);return 2*R*Math.asin(Math.sqrt(Math.sin(d1/2)**2+Math.cos(p1)*Math.cos(p2)*Math.sin(d2/2)**2))};
function evseIds(obj){const out=new Set();const walk=x=>{if(Array.isArray(x))return x.forEach(walk);if(!x||typeof x!=='object')return;for(const[k,v]of Object.entries(x)){if(typeof v==='string'&&/(evse|identifier)/i.test(k)&&/^FR\*?WA2/i.test(v))out.add(v);if(v&&typeof v==='object')walk(v)}};walk(obj);return[...out]}
function priceFields(obj){const out={};const walk=(x,p='$')=>{if(Array.isArray(x))return x.forEach((v,i)=>walk(v,`${p}[${i}]`));if(!x||typeof x!=='object')return;for(const[k,v]of Object.entries(x)){const q=`${p}.${k}`;if(/pric|tariff|fee|currency|kwh|minute|session|parking|idle|time/i.test(k))out[q]=v;if(v&&typeof v==='object')walk(v,q)}};walk(obj);return out}

const groups=new Map(), matches=new Map();
let mapCalls=0,mapErrors=0,cursor=0;
async function worker(){
  while(true){
    const i=cursor++;if(i>=stations.length)return;
    const s=stations[i],[lat,lng]=s.coordinates,dLat=.012,dLng=.018;
    const q=new URLSearchParams({top:String(lat+dLat),bottom:String(lat-dLat),left:String(lng-dLng),right:String(lng+dLng),zoom:'15',center_lat:String(lat),center_lng:String(lng),segmented:'1',busy_all:'1',busy_queue:'1',passive:'1'});
    let r=null;
    for(let a=0;a<3;a++){
      r=await fetchJson('https://api.monta.app/api/v1/charge_points/map?'+q);mapCalls++;
      if(r.status===200)break;
      if([429,500,502,503,504].includes(r.status)){await sleep(400*(a+1));continue}break;
    }
    if(r?.status!==200){mapErrors++;continue}
    const seen=new Set(),near=[];
    for(const g of [...(r.data?.list||[]),...(r.data?.single_list||[])]){
      const key=`${g.document||'group'}:${g.id}`;if(seen.has(key))continue;seen.add(key);
      const xy=loc(g),m=xy?dist([lat,lng],xy):null;if(m!=null&&m>1800)continue;
      const c={key,document:g.document,id:g.id,identifier:g.identifier,name:g.name,operator_name:g.operator_name,operator_id:g.operator_id,team_id:g.team_id,location:g.location,address1:g.address1,city:g.city,zip:g.zip,max_kw:g.max_kw,min_kw:g.min_kw,type_label:g.type_label,price_label:g.price_label,kwh_sales_fixed_prices:g.kwh_sales_fixed_prices,currency:g.currency,visibility:g.visibility,distanceM:m};
      if(!groups.has(key))groups.set(key,c);
      if(isWaat(g.operator_name)||(m!=null&&m<=150))near.push(c);
    }
    matches.set(norm(s.stationIdNormalized||s.stationId),near.sort((a,b)=>(a.distanceM??1e9)-(b.distanceM??1e9)).slice(0,10));
  }
}
await Promise.all(Array.from({length:6},worker));

const candidateKeys=new Set();
for(const[k,g]of groups)if(isWaat(g.operator_name))candidateKeys.add(k);
for(const arr of matches.values())for(const g of arr)if((g.distanceM??Infinity)<=150)candidateKeys.add(g.key);

const details=[];let detailErrors=0;
for(const key of candidateKeys){
  const g=groups.get(key);if(!g)continue;
  let detail=null,detailStatus=null,children=null,childrenStatus=null;
  if(g.document==='charge_point_group'){
    let r=await fetchJson(`https://api.monta.app/api/v1/charge_point_groups/${g.id}`);detailStatus=r.status;if(r.status===200)detail=r.data;
    r=await fetchJson(`https://api.monta.app/api/v1/charge_points?charge_point_group_id=${g.id}&size=200`);childrenStatus=r.status;if(r.status===200)children=r.data;
  }else{
    const r=await fetchJson(`https://api.monta.app/api/v1/charge_points/${g.id}`);detailStatus=r.status;if(r.status===200)detail=r.data;
  }
  if(detailStatus!==200)detailErrors++;
  const combined={group:g,detail,children},ids=evseIds(combined);
  const directWaatEvidence=isWaat(g.operator_name)||ids.some(x=>/^FR\*?WA2/i.test(x));
  details.push({key,group:g,detailStatus,childrenStatus,directWaatEvidence,evseIds:ids,pricingFields:priceFields(combined),detail,children});
}

const direct=details.filter(x=>x.directWaatEvidence),directKeys=new Set(direct.map(x=>x.key));
const outputStations=stations.map(s=>{
  const sid=norm(s.stationIdNormalized||s.stationId);
  const m=(matches.get(sid)||[]).filter(x=>directKeys.has(x.key)).map(x=>({key:x.key,distanceM:x.distanceM,name:x.name,operator_name:x.operator_name,price_label:x.price_label}));
  return {stationId:s.stationId,stationIdNormalized:s.stationIdNormalized,stationName:s.stationName,address:s.address,coordinates:s.coordinates,evseIdsIrve:s.evseIds||[],maxPowerKw:s.maxPowerKw,montaMatches:m,rankableDirect:false,blockingReason:m.length?'pricing_normalization_pending':'no_current_direct_waat_monta_match'};
});
const payload={schemaVersion:'2.0.0',dataset:'waat-monta-public-direct-tariffs-france',operator:'WAAT',operatorPrefix:'FR*WA2',country:'FR',generatedAt:new Date().toISOString(),source:{name:'Monta Web Map public guest API',map:'https://maps.monta.app/',api:'https://api.monta.app/api/v1/',auth:'anonymous public web-map guest session; credential never persisted'},scope:{operatorDirectOnly:true,roamingIncluded:false,residentialIncluded:false,guestPublicApi:true,pricesFailClosedUntilNormalized:true},counts:{irveStationCount:stations.length,mapCalls,mapErrors,mapGroupsSeen:groups.size,candidateGroupCount:candidateKeys.size,directWaatGroupCount:direct.length,detailErrors,stationsWithDirectMontaMatch:outputStations.filter(x=>x.montaMatches.length).length},directGroups:direct,stations:outputStations};
fs.mkdirSync('data/national',{recursive:true});fs.mkdirSync('data/reports',{recursive:true});
fs.writeFileSync(OUT,zlib.gzipSync(Buffer.from(JSON.stringify(payload)),{level:9}));
const priceLabels={};for(const x of direct){const p=String(x.group?.price_label??'').trim();if(p)priceLabels[p]=(priceLabels[p]||0)+1}
const report={generatedAt:payload.generatedAt,counts:payload.counts,priceLabels,directGroupSummaries:direct.map(x=>({key:x.key,name:x.group?.name,operator_name:x.group?.operator_name,location:x.group?.location,price_label:x.group?.price_label,evseIds:x.evseIds,pricingFields:x.pricingFields}))};
fs.writeFileSync(REPORT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2).slice(0,120000));
await browser.close();
