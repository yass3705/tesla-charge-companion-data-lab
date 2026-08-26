#!/usr/bin/env node
import fs from 'node:fs';
import zlib from 'node:zlib';
import { chromium } from 'playwright-core';

const inventoryPath='data/national/waat_direct_stations_france.json.gz';
const outPath='data/national/waat_monta_public_tariffs_france.json.gz';
const reportPath='data/reports/waat_monta_public_tariffs_report.json';

const inv=JSON.parse(zlib.gunzipSync(fs.readFileSync(inventoryPath)).toString('utf8'));
const stations=(inv.stations||[]).filter(x=>Array.isArray(x.coordinates)&&x.coordinates.length>=2);

const chromeCandidates=['/usr/bin/google-chrome','/usr/bin/google-chrome-stable','/usr/bin/chromium','/usr/bin/chromium-browser'];
const executablePath=chromeCandidates.find(p=>fs.existsSync(p));
if(!executablePath) throw new Error('No Chromium/Chrome executable found');

const browser=await chromium.launch({executablePath,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const context=await browser.newContext({
  locale:'fr-FR',
  userAgent:'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
  viewport:{width:1280,height:900}
});
const page=await context.newPage();
let apiHeaders=null;
page.on('request',req=>{
  const u=req.url();
  if(apiHeaders||!u.includes('api.monta.app/api/v1/charge_points/map')) return;
  const h=req.headers();
  const keep=['authorization','operator','application','application-version','accept','origin','referer','accept-language'];
  apiHeaders=Object.fromEntries(keep.filter(k=>h[k]).map(k=>[k,h[k]]));
});
await page.goto('https://maps.monta.app/?lat=46.5&lng=2.2&zoom=6&locale=fr',{waitUntil:'domcontentloaded',timeout:60000});
for(let i=0;i<40&&!apiHeaders;i++) await page.waitForTimeout(500);
if(!apiHeaders?.authorization) throw new Error('Public Monta guest authorization header was not observed');

const fetchJson=async(url)=>{
  const r=await fetch(url,{headers:apiHeaders});
  const txt=await r.text();
  let data=null; try{data=JSON.parse(txt);}catch{}
  return {status:r.status,data,text:txt};
};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const norm=s=>String(s??'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const isWaatText=s=>/WAAT|FR\*?WA2/i.test(String(s??''));
const haversine=(a,b)=>{
  const R=6371000,toRad=x=>x*Math.PI/180;
  const dLat=toRad(b[0]-a[0]),dLon=toRad(b[1]-a[1]);
  const la1=toRad(a[0]),la2=toRad(b[0]);
  const q=Math.sin(dLat/2)**2+Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)**2;
  return 2*R*Math.asin(Math.sqrt(q));
};
const locationOf=g=>{
  const m=String(g?.location||'').match(/(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)/);
  return m?[Number(m[1]),Number(m[2])]:null;
};
const extractEvseIds=obj=>{
  const out=new Set();
  const visit=x=>{
    if(Array.isArray(x)) return x.forEach(visit);
    if(!x||typeof x!=='object') return;
    for(const [k,v] of Object.entries(x)){
      if(typeof v==='string' && /(evse|custom.*evse|identifier)/i.test(k) && /^FR\*?WA2/i.test(v)) out.add(v);
      if(typeof v==='object'&&v) visit(v);
    }
  };visit(obj);return [...out];
};
const pricingFields=obj=>{
  const out={};
  const visit=(x,path='$')=>{
    if(Array.isArray(x)) return x.forEach((v,i)=>visit(v,`${path}[${i}]`));
    if(!x||typeof x!=='object') return;
    for(const [k,v] of Object.entries(x)){
      const p=`${path}.${k}`;
      if(/pric|tariff|fee|currency|kwh|minute|session|parking|idle|time/i.test(k)){
        out[p]=typeof v==='object'&&v!==null?JSON.parse(JSON.stringify(v)):v;
      }
      if(typeof v==='object'&&v) visit(v,p);
    }
  };visit(obj);return out;
};

const groups=new Map();
const stationMatches=new Map();
let mapCalls=0,mapErrors=0;
const concurrency=8;
let cursor=0;
async function worker(){
  while(true){
    const idx=cursor++; if(idx>=stations.length) return;
    const st=stations[idx], [lat,lng]=st.coordinates;
    const dlat=0.012, dlng=0.018;
    const q=new URLSearchParams({top:String(lat+dlat),bottom:String(lat-dlat),left:String(lng-dlng),right:String(lng+dlng),zoom:'15',center_lat:String(lat),center_lng:String(lng),segmented:'1',busy_all:'1',busy_queue:'1',passive:'1'});
    let res;
    for(let attempt=0;attempt<3;attempt++){
      res=await fetchJson('https://api.monta.app/api/v1/charge_points/map?'+q);
      mapCalls++;
      if(res.status===200) break;
      if([429,500,502,503,504].includes(res.status)){await sleep(350*(attempt+1));continue;}
      break;
    }
    if(res?.status!==200){mapErrors++;continue;}
    const items=[...(res.data?.list||[]),...(res.data?.single_list||[])];
    const seen=new Set();
    const nearby=[];
    for(const g of items){
      const key=`${g.document||'group'}:${g.id}`;if(seen.has(key))continue;seen.add(key);
      const loc=locationOf(g);const dist=loc?haversine([lat,lng],loc):null;
      if(dist!=null&&dist>1800)continue;
      const compact={document:g.document,id:g.id,identifier:g.identifier,name:g.name,operator_name:g.operator_name,operator_id:g.operator_id,team_id:g.team_id,location:g.location,address1:g.address1,city:g.city,zip:g.zip,max_kw:g.max_kw,min_kw:g.min_kw,type_label:g.type_label,price_label:g.price_label,kwh_sales_fixed_prices:g.kwh_sales_fixed_prices,currency:g.currency,country:g.country,visibility:g.visibility,effective_driver_support_visibility:g.effective_driver_support_visibility,distanceM:dist};
      groups.set(key,groups.has(key)?groups.get(key):compact);
      if(isWaatText(g.operator_name)||dist<=120) nearby.push({...compact,key});
    }
    stationMatches.set(norm(st.stationIdNormalized||st.stationId),nearby.sort((a,b)=>(a.distanceM??1e9)-(b.distanceM??1e9)).slice(0,8));
  }
}
await Promise.all(Array.from({length:concurrency},worker));

// Candidate groups: explicit WAAT operator text, plus closest <=120m to a known FR*WA2 IRVE station.
const candidateKeys=new Set();
for(const [key,g] of groups){if(isWaatText(g.operator_name))candidateKeys.add(key);}
for(const matches of stationMatches.values()) for(const m of matches) if((m.distanceM??Infinity)<=120) candidateKeys.add(m.key);

const details=[];
let detailErrors=0;
for(const key of candidateKeys){
  const g=groups.get(key); if(!g) continue;
  const endpoints=[];
  if(g.document==='charge_point_group') endpoints.push(`https://api.monta.app/api/v1/charge_point_groups/${g.id}`);
  if(g.document==='charge_point') endpoints.push(`https://api.monta.app/api/v1/charge_points/${g.id}`);
  let detail=null,detailStatus=null,detailUrl=null;
  for(const u of endpoints){
    const r=await fetchJson(u); detailStatus=r.status;detailUrl=u;if(r.status===200){detail=r.data;break;}
  }
  let children=null,childrenStatus=null;
  if(g.document==='charge_point_group'){
    const u=`https://api.monta.app/api/v1/charge_points?charge_point_group_id=${encodeURIComponent(g.id)}&size=200`;
    const r=await fetchJson(u);childrenStatus=r.status;if(r.status===200)children=r.data;
  }
  if(!detail&&detailStatus!==200) detailErrors++;
  const combined={group:g,detail,children};
  const evseIds=extractEvseIds(combined);
  const directEvidence=isWaatText(g.operator_name)||evseIds.some(x=>/^FR\*?WA2/i.test(x));
  details.push({
    key,group:g,detailStatus,detailUrl,childrenStatus,
    directWaatEvidence:directEvidence,
    evseIds,
    pricingFields:pricingFields(combined),
    detail,children
  });
}

const direct=details.filter(x=>x.directWaatEvidence);
const directIds=new Set(direct.map(x=>x.key));
const outputStations=[];
for(const st of stations){
  const sid=norm(st.stationIdNormalized||st.stationId);
  const matches=(stationMatches.get(sid)||[]).map(m=>({key:m.key,distanceM:m.distanceM,name:m.name,operator_name:m.operator_name,price_label:m.price_label}));
  const directMatches=matches.filter(m=>directIds.has(m.key));
  outputStations.push({
    stationId:st.stationId,stationIdNormalized:st.stationIdNormalized,stationName:st.stationName,address:st.address,coordinates:st.coordinates,evseIdsIrve:st.evseIds||[],maxPowerKw:st.maxPowerKw,
    montaMatches:directMatches,
    rankableDirect:false,
    blockingReason:directMatches.length?'pricing_normalization_pending':'no_current_direct_waat_monta_match'
  });
}

const payload={
  schemaVersion:'2.0.0',dataset:'waat-monta-public-direct-tariffs-france',operator:'WAAT',operatorPrefix:'FR*WA2',country:'FR',generatedAt:new Date().toISOString(),
  source:{name:'Monta Web Map public guest API',map:'https://maps.monta.app/',api:'https://api.monta.app/api/v1/',auth:'anonymous guest session generated by public web map; credentials never persisted'},
  scope:{operatorDirectOnly:true,roamingIncluded:false,residentialIncluded:false,guestPublicApi:true,pricesFailClosedUntilNormalized:true},
  counts:{irveStationCount:stations.length,mapCalls,mapErrors,mapGroupsSeen:groups.size,candidateGroupCount:candidateKeys.size,directWaatGroupCount:direct.length,detailErrors,stationsWithDirectMontaMatch:outputStations.filter(x=>x.montaMatches.length).length},
  directGroups:direct,
  stations:outputStations
};
fs.mkdirSync('data/national',{recursive:true});fs.mkdirSync('data/reports',{recursive:true});
fs.writeFileSync(outPath,zlib.gzipSync(Buffer.from(JSON.stringify(payload)),{level:9}));
const priceLabels={};
for(const x of direct){const p=String(x.group?.price_label??'').trim();if(p)priceLabels[p]=(priceLabels[p]||0)+1;}
const pricingPaths={};
for(const x of direct) for(const k of Object.keys(x.pricingFields||{})) pricingPaths[k]=(pricingPaths[k]||0)+1;
const report={generatedAt:payload.generatedAt,counts:payload.counts,priceLabels,pricingPaths,directGroupSummaries:direct.map(x=>({key:x.key,name:x.group?.name,operator_name:x.group?.operator_name,location:x.group?.location,price_label:x.group?.price_label,evseIds:x.evseIds,pricingFields:x.pricingFields}))};
fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2).slice(0,120000));
await browser.close();
