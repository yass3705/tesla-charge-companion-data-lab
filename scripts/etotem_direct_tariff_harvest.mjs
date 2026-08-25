import fs from 'fs';
import zlib from 'zlib';
import { chromium } from 'playwright-core';

const INVENTORY='data/national/etotem_direct_stations_france.json.gz';
const OUTPUT='data/national/etotem_direct_tariffs_france.json.gz';
const PORTAL='https://www.e-totem.fr/#/home/ou_se_recharger';
const TILE=0.35;
const PAD=0.018;

function normId(v){return String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');}
function htmlToText(v){
  let s=String(v||'');
  const entities={'&euro;':'€','&amp;':'&','&nbsp;':' ','&#039;':"'",'&apos;':"'",'&quot;':'"','&agrave;':'à','&Agrave;':'À','&eacute;':'é','&Eacute;':'É','&ecirc;':'ê','&acirc;':'â','&ocirc;':'ô','&ucirc;':'û','&icirc;':'î','&ccedil;':'ç','&ugrave;':'ù','&rsquo;':"'"};
  for(let round=0;round<3;round++) s=s.replace(/&(euro|amp|nbsp|apos|quot|agrave|Agrave|eacute|Eacute|ecirc|acirc|ocirc|ucirc|icirc|ccedil|ugrave|rsquo);/g,m=>entities[m]||m).replace(/&#0*39;/g,"'").replace(/&#0*34;/g,'"').replace(/&#0*160;/g,' ').replace(/&#x0*27;/gi,"'").replace(/&#x0*a0;/gi,' ');
  return s.replace(/<br\s*\/?\s*>/gi,'\n').replace(/<\/p\s*>/gi,'\n').replace(/<[^>]+>/g,' ').replace(/\r/g,'').replace(/[ \t]+/g,' ').replace(/ *\n+ */g,'\n').trim();
}
function tariffSignature(text){return String(text||'').toLowerCase().replace(/\s+/g,' ').trim();}
function num(v){const n=Number(String(v).replace(',','.'));return Number.isFinite(n)?n:null;}
function parseHints(text){
  const t=String(text||''); const kwh=[],timeFees=[],grace=[],powerThresholds=[];
  for(const m of t.matchAll(/(\d+(?:[.,]\d+)?)\s*€\s*(?:\/|par)?\s*kwh/gi)){const n=num(m[1]);if(n!==null&&!kwh.includes(n))kwh.push(n);}
  for(const m of t.matchAll(/(\d+(?:[.,]\d+)?)\s*€\s*(?:\/|par\s+tranche(?:\s+entam[eé]e)?\s+de)?\s*(\d+)\s*min/gi)){const item={eur:num(m[1]),minutes:Number(m[2]),raw:m[0]};if(!timeFees.some(x=>x.eur===item.eur&&x.minutes===item.minutes))timeFees.push(item);}
  for(const m of t.matchAll(/(\d+)\s*(min|h(?:eure)?s?)\s+gratuite?s?/gi)){let minutes=Number(m[1]);if(/^h/i.test(m[2]))minutes*=60;if(!grace.includes(minutes))grace.push(minutes);}
  for(const m of t.matchAll(/(?:jusqu(?:'|’|\s)?(?:a|à)|au[- ]del[aà]|de|point de charge)\s*([^\n]{0,50}?)(\d+(?:[.,]\d+)?)\s*kw/gi)){const n=num(m[2]);if(n!==null&&!powerThresholds.includes(n))powerThresholds.push(n);}
  return {pricePerKwhCandidatesEur:kwh,timeFeeCandidates:timeFees,freeGraceMinutesCandidates:grace,powerThresholdCandidatesKw:powerThresholds};
}
function haversine(a,b){const R=6371000,toR=x=>x*Math.PI/180,dLat=toR(b.latitude-a.latitude),dLon=toR(b.longitude-a.longitude),la1=toR(a.latitude),la2=toR(b.latitude);const h=Math.sin(dLat/2)**2+Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.sqrt(h));}
function direct(e){return String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0';}
function keyFor(lat,lon){return `${Math.floor(lat/TILE)},${Math.floor(lon/TILE)}`;}

if(!fs.existsSync(INVENTORY)) throw new Error(`Missing ${INVENTORY}`);
const inv=JSON.parse(zlib.gunzipSync(fs.readFileSync(INVENTORY)).toString('utf8'));
const targets=inv.stations.map((s,i)=>({index:i,stationId:s.stationId,name:s.name,latitude:Number(s.latitude),longitude:Number(s.longitude),maxPowerKw:s.maxPowerKw,pdcCount:s.pdcCount,dataset:s.dataset?.title||null}));

const tiles=new Map();
for(const t of targets){if(!Number.isFinite(t.latitude)||!Number.isFinite(t.longitude))continue;const k=keyFor(t.latitude,t.longitude);if(!tiles.has(k))tiles.set(k,[]);tiles.get(k).push(t);}
const tileQueries=[...tiles.entries()].map(([key,items])=>({key,indices:items.map(x=>x.index),south:Math.min(...items.map(x=>x.latitude))-PAD,north:Math.max(...items.map(x=>x.latitude))+PAD,west:Math.min(...items.map(x=>x.longitude))-PAD,east:Math.max(...items.map(x=>x.longitude))+PAD}));

const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const page=await browser.newPage({locale:'fr-FR',viewport:{width:1440,height:1000}});
let stationHeaders=null;
page.on('request',req=>{if(!stationHeaders&&req.url().includes('/api/Stations?')&&['xhr','fetch'].includes(req.resourceType()))stationHeaders=req.headers();});
await page.goto(PORTAL,{waitUntil:'domcontentloaded',timeout:60000});
for(let i=0;i<40&&!stationHeaders;i++)await page.waitForTimeout(500);
if(!stationHeaders){await browser.close();throw new Error('Could not capture public anonymous Stations request headers');}

const harvested=await page.evaluate(async ({tileQueries,headers})=>{
  const keep={};for(const [k,v] of Object.entries(headers||{})){const lk=k.toLowerCase();if(!['host','content-length','origin','referer','sec-fetch-dest','sec-fetch-mode','sec-fetch-site','user-agent'].includes(lk))keep[k]=v;}
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  async function query(q,attempt=0){
    const p=new URLSearchParams({fLatSudOuest:String(q.south),fLongSudOuest:String(q.west),fLatNordEst:String(q.north),fLongNordEst:String(q.east),bUniquementBornesDisponibles:'false',bCompatibleAutocharge:'0',nZoom:'16',bNePasClusteriser:'1',nBornesPrivees:'0',bRecupererBorneLaPlusProche:'0'});
    const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),10000);
    try{const r=await fetch('/api/Stations?'+p.toString(),{headers:keep,signal:ctl.signal});const text=await r.text();if(!r.ok)throw new Error('http_'+r.status);const j=JSON.parse(text);return {key:q.key,status:r.status,elements:Array.isArray(j?.aElements)?j.aElements:[]};}
    catch(e){if(attempt<2){await sleep(250*(attempt+1));return query(q,attempt+1);}return {key:q.key,error:String(e),elements:[]};}
    finally{clearTimeout(timer);}
  }
  const results=new Array(tileQueries.length);let next=0;
  async function worker(){while(true){const i=next++;if(i>=tileQueries.length)return;results[i]=await query(tileQueries[i]);await sleep(35);}}
  await Promise.all(Array.from({length:10},()=>worker()));
  return results;
},{tileQueries,headers:stationHeaders});

let allElements=[];for(const r of harvested)for(const e of (r?.elements||[]))if(direct(e))allElements.push(e);
const byId=new Map();for(const e of allElements){const k=normId(e.sIdPool);if(k&&!byId.has(k))byId.set(k,e);}
let initiallyMissed=targets.filter(t=>!byId.has(normId(t.stationId)));

// Tight, concurrent fallback only for IDs not found in the tile pass.
if(initiallyMissed.length){
  const fallback=await page.evaluate(async ({targets,headers})=>{
    const keep={};for(const [k,v] of Object.entries(headers||{})){const lk=k.toLowerCase();if(!['host','content-length','origin','referer','sec-fetch-dest','sec-fetch-mode','sec-fetch-site','user-agent'].includes(lk))keep[k]=v;}
    async function one(t){
      if(!Number.isFinite(t.latitude)||!Number.isFinite(t.longitude))return {index:t.index,error:'missing_coordinates'};
      for(const d of [0.012,0.035]){const p=new URLSearchParams({fLatSudOuest:String(t.latitude-d),fLongSudOuest:String(t.longitude-d),fLatNordEst:String(t.latitude+d),fLongNordEst:String(t.longitude+d),bUniquementBornesDisponibles:'false',bCompatibleAutocharge:'0',nZoom:'17',bNePasClusteriser:'1',nBornesPrivees:'0',bRecupererBorneLaPlusProche:'0'});const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),8000);try{const r=await fetch('/api/Stations?'+p.toString(),{headers:keep,signal:ctl.signal});const j=JSON.parse(await r.text());const elements=Array.isArray(j?.aElements)?j.aElements:[];if(elements.length)return {index:t.index,elements};}catch{}finally{clearTimeout(timer);}}
      return {index:t.index,elements:[]};
    }
    const out=new Array(targets.length);let next=0;async function worker(){while(true){const i=next++;if(i>=targets.length)return;out[i]=await one(targets[i]);}}await Promise.all(Array.from({length:10},()=>worker()));return out;
  },{targets:initiallyMissed,headers:stationHeaders});
  for(const r of fallback)for(const e of (r?.elements||[]))if(direct(e)){allElements.push(e);const k=normId(e.sIdPool);if(k&&!byId.has(k))byId.set(k,e);}
}
await browser.close();

const nativeUnique=[...new Map(allElements.map(e=>[normId(e.sIdPool)||String(e.sIdPoolUnique||Math.random()),e])).values()];
const stations=[];const profileCounts=new Map();let exact=0,coordFallback=0,unresolved=0,withTariff=0;
for(const target of targets){
  const wanted=normId(target.stationId);let match=byId.get(wanted)||null,matchMethod='id',distanceM=null;
  if(!match&&Number.isFinite(target.latitude)&&Number.isFinite(target.longitude)){
    const candidates=nativeUnique.map(e=>({e,d:haversine(target,{latitude:Number(e.fLatitude),longitude:Number(e.fLongitude)})})).filter(x=>Number.isFinite(x.d)).sort((a,b)=>a.d-b.d);
    if(candidates[0]&&candidates[0].d<=120){match=candidates[0].e;distanceM=Math.round(candidates[0].d);matchMethod='coordinates';}
  }
  if(!match){unresolved++;stations.push({...target,resolved:false});continue;}
  if(matchMethod==='id')exact++;else coordFallback++;
  const tariffHtml=String(match.sWebTexte||match.aBornes?.[0]?.sWebTextePool||match.aBornes?.[0]?.szWebTexte||''),tariffText=htmlToText(tariffHtml),signature=tariffSignature(tariffText);
  if(tariffText){withTariff++;profileCounts.set(signature,(profileCounts.get(signature)||0)+1);}
  stations.push({...target,resolved:true,matchMethod,distanceM,api:{sIdPool:match.sIdPool,sIdPoolUnique:match.sIdPoolUnique,sOrigine:match.sOrigine,sLibelle:match.sLibelle,sNomReseau:match.sNomReseau,sTypeBorne:match.sTypeBorne,bOcpi:match.bOcpi,bGireve:match.bGireve,bItinerance:match.bItinerance,nIdPool:match.nIdPool},tariffHtml,tariffText,tariffSignature:signature,tariffHints:parseHints(tariffText),apiPdc:(match.aBornes||[]).flatMap(b=>(b.aPdc||[]).map(p=>({nIdPdc:p.nIdPdc,nIdBorne:p.nIdBorne,nConnectorId:p.nConnectorId,status:p.szStatus,types:p.szTypePrises||[]})))});
}
const profileMap=new Map();for(const s of stations.filter(s=>s.resolved&&s.tariffText)){if(!profileMap.has(s.tariffSignature))profileMap.set(s.tariffSignature,{count:0,text:s.tariffText,hints:s.tariffHints,exampleStations:[]});const p=profileMap.get(s.tariffSignature);p.count++;if(p.exampleStations.length<8)p.exampleStations.push({stationId:s.stationId,name:s.name,network:s.api?.sNomReseau,maxPowerKw:s.maxPowerKw});}
const profiles=[...profileMap.values()].sort((a,b)=>b.count-a.count);
const output={schemaVersion:'1.1.0',generatedAt:new Date().toISOString(),operator:'e-Totem',country:'FR',scope:{physicalCpoDirectOnly:true,roamingIncluded:false,source:'public anonymous e-Totem /api/Stations joined to strict e-Totem IRVE inventory',nativeFilter:'bOcpi=0 AND bGireve=0 AND bItinerance=0',noGuessedFallback:true},harvest:{strategy:'occupied geographic tiles + targeted fallback',tileDegrees:TILE,tileQueries:tileQueries.length,initiallyMissed:initiallyMissed.length,nativeElementsUnique:nativeUnique.length},counts:{inventoryStations:targets.length,resolvedStations:exact+coordFallback,exactIdMatches:exact,coordinateFallbackMatches:coordFallback,unresolvedStations:unresolved,resolvedWithTariffText:withTariff,uniqueTariffProfiles:profiles.length},tariffProfiles:profiles,stations};
fs.mkdirSync('data/national',{recursive:true});fs.writeFileSync(OUTPUT,zlib.gzipSync(Buffer.from(JSON.stringify(output),'utf8'),{level:9}));console.log(JSON.stringify({harvest:output.harvest,counts:output.counts},null,2));console.log(JSON.stringify(profiles.slice(0,30).map((p,i)=>({rank:i+1,count:p.count,text:p.text.slice(0,900),hints:p.hints,examples:p.exampleStations.slice(0,3)})),null,2));