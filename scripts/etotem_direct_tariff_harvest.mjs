import fs from 'fs';
import zlib from 'zlib';
import { chromium } from 'playwright-core';

const INVENTORY='data/national/etotem_direct_stations_france.json.gz';
const OUTPUT='data/national/etotem_direct_tariffs_france.json.gz';
const MAP_URL='https://www.e-totem.fr/#/home/ou_se_recharger';
const CONCURRENCY=1;
const MAX_TARGETS_PER_TILE=12;
const MAX_LAT_SPAN=0.28;
const MAX_LON_SPAN=0.38;
const TILE_PADDING=0.025;

function normId(v){return String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');}
function htmlToText(v){
  let s=String(v||'');
  const entities={'&euro;':'€','&amp;':'&','&nbsp;':' ','&apos;':"'",'&quot;':'"','&agrave;':'à','&Agrave;':'À','&eacute;':'é','&Eacute;':'É','&ecirc;':'ê','&acirc;':'â','&ocirc;':'ô','&ucirc;':'û','&icirc;':'î','&ccedil;':'ç','&ugrave;':'ù','&rsquo;':"'"};
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
function direct(e){return String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0';}
function distanceM(a,b){
  const R=6371000,r=Math.PI/180,dLat=(b.lat-a.lat)*r,dLon=(b.lon-a.lon)*r,la1=a.lat*r,la2=b.lat*r;
  const h=Math.sin(dLat/2)**2+Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)**2;
  return 2*R*Math.asin(Math.sqrt(h));
}
function tileBounds(items){
  const lats=items.map(x=>x.latitude),lons=items.map(x=>x.longitude);
  return {minLat:Math.min(...lats),maxLat:Math.max(...lats),minLon:Math.min(...lons),maxLon:Math.max(...lons)};
}
function splitItems(items){
  if(items.length<2)return [items,[]];
  const b=tileBounds(items),latSpan=b.maxLat-b.minLat,lonSpan=b.maxLon-b.minLon;
  const key=lonSpan>=latSpan?'longitude':'latitude';
  const sorted=[...items].sort((a,b)=>a[key]-b[key]);
  const mid=Math.ceil(sorted.length/2);
  return [sorted.slice(0,mid),sorted.slice(mid)];
}
function buildTiles(items,out=[]){
  if(!items.length)return out;
  const b=tileBounds(items),latSpan=b.maxLat-b.minLat,lonSpan=b.maxLon-b.minLon;
  if(items.length<=MAX_TARGETS_PER_TILE&&latSpan<=MAX_LAT_SPAN&&lonSpan<=MAX_LON_SPAN){out.push({targets:items,bounds:b});return out;}
  const [a,bItems]=splitItems(items);buildTiles(a,out);buildTiles(bItems,out);return out;
}

if(!fs.existsSync(INVENTORY)) throw new Error(`Missing ${INVENTORY}`);
const inv=JSON.parse(zlib.gunzipSync(fs.readFileSync(INVENTORY)).toString('utf8'));
const targets=(inv.stations||[]).map((s,i)=>({index:i,stationId:s.stationId,name:s.name,latitude:Number(s.latitude),longitude:Number(s.longitude),maxPowerKw:s.maxPowerKw,pdcCount:s.pdcCount,dataset:s.dataset?.title||null})).filter(t=>Number.isFinite(t.latitude)&&Number.isFinite(t.longitude));
console.log(`[e-Totem] inventory=${targets.length}`);
const initialTiles=buildTiles(targets);
console.log(`[e-Totem] adaptive tiles=${initialTiles.length}; concurrency=${CONCURRENCY}; maxTargets=${MAX_TARGETS_PER_TILE}`);

const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const page=await browser.newPage({locale:'fr-FR',viewport:{width:1440,height:1000}});
let stationHeaders=null;
page.on('request',req=>{
  const u=req.url();
  if(!stationHeaders&&u.includes('/api/Stations?')&&['xhr','fetch'].includes(req.resourceType())) stationHeaders=req.headers();
});
await page.goto(MAP_URL,{waitUntil:'domcontentloaded',timeout:60000});
for(let i=0;i<70&&!stationHeaders;i++)await page.waitForTimeout(500);
if(!stationHeaders){await browser.close();throw new Error('No real Flutter /api/Stations request captured after 35s');}
console.log('[e-Totem] real Flutter Stations headers captured; sensitive values not logged');

const bootstrap=await page.evaluate(async ({headers})=>{
  const keep={};
  for(const [k,v] of Object.entries(headers||{})){
    const lk=k.toLowerCase();
    if(!['host','content-length','origin','referer','sec-fetch-dest','sec-fetch-mode','sec-fetch-site','user-agent'].includes(lk))keep[k]=v;
  }
  const direct=e=>String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0';
  const norm=v=>String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
  const url='/api/Stations?fLatSudOuest=43.05&fLongSudOuest=0.82&fLatNordEst=43.15&fLongNordEst=0.98&bUniquementBornesDisponibles=false&bCompatibleAutocharge=0&nZoom=16&bNePasClusteriser=1&nBornesPrivees=0&bRecupererBorneLaPlusProche=0';
  const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),20000);
  try{
    const r=await fetch(url,{headers:keep,credentials:'include',cache:'no-store',signal:ctl.signal});
    const text=await r.text();let j=null;try{j=JSON.parse(text);}catch{}
    const elements=Array.isArray(j?.aElements)?j.aElements:[];
    const mane=elements.find(e=>norm(e?.sIdPool)==='FRETIP31315A');
    if(r.status!==200||!mane||!direct(mane)||!String(mane?.sWebTexte||mane?.aBornes?.[0]?.sWebTextePool||mane?.aBornes?.[0]?.szWebTexte||'').trim())throw new Error(`Mane sentry failed status=${r.status} count=${elements.length}`);
    window.__ETOTEM_HEADERS=keep;
    return {status:r.status,count:elements.length,directCount:elements.filter(direct).length};
  }finally{clearTimeout(timer);}
},{headers:stationHeaders});
console.log(`[e-Totem] Mane sentry OK: status=${bootstrap.status} elements=${bootstrap.count} direct=${bootstrap.directCount}`);

const tilePayload=initialTiles.map((tile,id)=>({id,targets:tile.targets.map(t=>({index:t.index,stationId:t.stationId,latitude:t.latitude,longitude:t.longitude})),bounds:tile.bounds}));
const harvest=await page.evaluate(async ({tiles,concurrency,padding})=>{
  const norm=v=>String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
  const isDirect=e=>String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0';
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  let requestCount=0,errorCount=0,emptyCount=0,retries=0,refreshed=0;
  const elementsById=new Map();
  const elementKey=e=>norm(e?.sIdPool)||norm(e?.sIdPoolUnique)||`${e?.fLatitude}|${e?.fLongitude}|${e?.sLibelle||''}`;
  async function refreshAuth(){
    try{
      const r=await fetch('/api/ConnexionAnonyme',{method:'POST',headers:{Accept:'application/json'},credentials:'include',cache:'no-store'});
      const j=await r.json();
      if(r.ok&&j?.bSucces===true&&j?.szToken){
        const h=window.__ETOTEM_HEADERS||{};
        const key=Object.keys(h).find(k=>k.toLowerCase()==='authorization')||'authorization';
        h[key]='Bearer '+j.szToken;window.__ETOTEM_HEADERS=h;refreshed++;return true;
      }
    }catch{}
    return false;
  }
  function paramsFor(bounds){
    const latSpan=bounds.maxLat-bounds.minLat,lonSpan=bounds.maxLon-bounds.minLon;
    const pad=Math.max(padding,Math.min(0.06,Math.max(latSpan,lonSpan)*0.12));
    return new URLSearchParams({fLatSudOuest:String(bounds.minLat-pad),fLongSudOuest:String(bounds.minLon-pad),fLatNordEst:String(bounds.maxLat+pad),fLongNordEst:String(bounds.maxLon+pad),bUniquementBornesDisponibles:'false',bCompatibleAutocharge:'0',nZoom:'16',bNePasClusteriser:'1',nBornesPrivees:'0',bRecupererBorneLaPlusProche:'0'});
  }
  async function query(tile,attempt=0){
    const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),18000);
    try{
      requestCount++;
      const r=await fetch('/api/Stations?'+paramsFor(tile.bounds).toString(),{headers:window.__ETOTEM_HEADERS||{},credentials:'include',cache:'no-store',signal:ctl.signal});
      if(r.status===401&&attempt<2){await refreshAuth();retries++;await sleep(500);return query(tile,attempt+1);}
      const text=await r.text();
      if(!r.ok)throw new Error(`http_${r.status}`);
      const j=JSON.parse(text),all=Array.isArray(j?.aElements)?j.aElements:[];
      if(all.length===0)emptyCount++;
      for(const e of all.filter(isDirect))elementsById.set(elementKey(e),e);
      return {ok:true,count:all.length,direct:all.filter(isDirect).length};
    }catch(e){
      if(attempt<2){retries++;await sleep(attempt===0?700:1800);return query(tile,attempt+1);}
      errorCount++;return {ok:false,error:String(e)};
    }finally{clearTimeout(timer);}
  }
  const results=new Array(tiles.length);let next=0;
  async function worker(){
    while(true){
      const i=next++;if(i>=tiles.length)return;
      results[i]=await query(tiles[i]);
      await sleep(250);
    }
  }
  await Promise.all(Array.from({length:concurrency},()=>worker()));
  const elements=[...elementsById.values()];
  return {results,elements,stats:{requestCount,errorCount,emptyCount,retries,refreshed,uniqueDirectElements:elements.length,successfulTiles:results.filter(r=>r?.ok).length,failedTiles:results.filter(r=>!r?.ok).length}};
},{tiles:tilePayload,concurrency:CONCURRENCY,padding:TILE_PADDING});
console.log('[e-Totem] tile harvest',JSON.stringify(harvest.stats));

const apiElements=(harvest.elements||[]).filter(direct);
const byId=new Map();
for(const e of apiElements){
  for(const id of [normId(e?.sIdPool),normId(e?.sIdPoolUnique)])if(id)byId.set(id,e);
}
const matched=new Map();
let exact=0,coordFallback=0;
for(const target of targets){
  const wanted=normId(target.stationId);let e=byId.get(wanted),method='id',d=0;
  if(!e){
    let nearest=null;
    for(const candidate of apiElements){const lat=Number(candidate?.fLatitude),lon=Number(candidate?.fLongitude);if(!Number.isFinite(lat)||!Number.isFinite(lon))continue;const dm=distanceM({lat:target.latitude,lon:target.longitude},{lat,lon});if(dm<=150&&(!nearest||dm<nearest.d))nearest={d:dm,e:candidate};}
    if(nearest){e=nearest.e;method='coordinates';d=Math.round(nearest.d);}
  }
  if(e){matched.set(target.index,{element:e,matchMethod:method,distanceM:d});if(method==='id')exact++;else coordFallback++;}
}
console.log(`[e-Totem] after tiled matching resolved=${matched.size}/${targets.length}; exact=${exact}; coordinate=${coordFallback}`);

const unresolvedTargets=targets.filter(t=>!matched.has(t.index));
let fallbackStats={requestCount:0,errorCount:0,resolved:0};
if(unresolvedTargets.length&&unresolvedTargets.length<=260){
  const fallback=await page.evaluate(async ({targets})=>{
    const norm=v=>String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
    const isDirect=e=>String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0';
    const dist=(a,b)=>{const R=6371000,r=Math.PI/180,dLat=(b.lat-a.lat)*r,dLon=(b.lon-a.lon)*r,la1=a.lat*r,la2=b.lat*r;const h=Math.sin(dLat/2)**2+Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.sqrt(h));};
    const sleep=ms=>new Promise(r=>setTimeout(r,ms));
    const out=[];let requests=0,errors=0;
    for(const t of targets){
      const p=new URLSearchParams({fLatSudOuest:String(t.latitude-.06),fLongSudOuest:String(t.longitude-.06),fLatNordEst:String(t.latitude+.06),fLongNordEst:String(t.longitude+.06),bUniquementBornesDisponibles:'false',bCompatibleAutocharge:'0',nZoom:'16',bNePasClusteriser:'1',nBornesPrivees:'0',bRecupererBorneLaPlusProche:'0'});
      let elements=[];
      for(let attempt=0;attempt<2;attempt++){
        const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),15000);
        try{requests++;const r=await fetch('/api/Stations?'+p.toString(),{headers:window.__ETOTEM_HEADERS||{},credentials:'include',cache:'no-store',signal:ctl.signal});const text=await r.text();if(!r.ok)throw new Error(`http_${r.status}`);const j=JSON.parse(text);elements=(Array.isArray(j?.aElements)?j.aElements:[]).filter(isDirect);break;}catch(e){if(attempt===1)errors++;else await sleep(900);}finally{clearTimeout(timer);}
      }
      const wanted=norm(t.stationId);let e=elements.find(x=>norm(x?.sIdPool)===wanted||norm(x?.sIdPoolUnique)===wanted),method='id',distanceM=0;
      if(!e){let nearest=null;for(const c of elements){const lat=Number(c?.fLatitude),lon=Number(c?.fLongitude);if(!Number.isFinite(lat)||!Number.isFinite(lon))continue;const d=dist({lat:t.latitude,lon:t.longitude},{lat,lon});if(d<=150&&(!nearest||d<nearest.d))nearest={d,e:c};}if(nearest){e=nearest.e;method='coordinates';distanceM=Math.round(nearest.d);}}
      if(e)out.push({index:t.index,element:e,matchMethod:method,distanceM});
      await sleep(450);
    }
    return {out,requests,errors};
  },{targets:unresolvedTargets.map(t=>({index:t.index,stationId:t.stationId,latitude:t.latitude,longitude:t.longitude}))});
  fallbackStats={requestCount:fallback.requests,errorCount:fallback.errors,resolved:fallback.out.length};
  for(const r of fallback.out){if(!matched.has(r.index)){matched.set(r.index,r);if(r.matchMethod==='id')exact++;else coordFallback++;}}
  console.log('[e-Totem] targeted fallback',JSON.stringify(fallbackStats));
}
await page.evaluate(()=>{delete window.__ETOTEM_HEADERS;});
await browser.close();

const stations=[];let unresolved=0,withTariff=0;
for(const target of targets){
  const r=matched.get(target.index);
  if(!r?.element||!direct(r.element)){unresolved++;stations.push({...target,resolved:false});continue;}
  const match=r.element,tariffHtml=String(match.sWebTexte||match.aBornes?.[0]?.sWebTextePool||match.aBornes?.[0]?.szWebTexte||''),tariffText=htmlToText(tariffHtml),signature=tariffSignature(tariffText);if(tariffText)withTariff++;
  stations.push({...target,resolved:true,matchMethod:r.matchMethod,distanceM:r.distanceM??null,api:{sIdPool:match.sIdPool,sIdPoolUnique:match.sIdPoolUnique,sOrigine:match.sOrigine,sLibelle:match.sLibelle,sNomReseau:match.sNomReseau,sTypeBorne:match.sTypeBorne,bOcpi:match.bOcpi,bGireve:match.bGireve,bItinerance:match.bItinerance,nIdPool:match.nIdPool},tariffHtml,tariffText,tariffSignature:signature,tariffHints:parseHints(tariffText),apiPdc:(match.aBornes||[]).flatMap(b=>(b.aPdc||[]).map(p=>({nIdPdc:p.nIdPdc,nIdBorne:p.nIdBorne,nConnectorId:p.nConnectorId,status:p.szStatus,types:p.szTypePrises||[]})))});
}
const profileMap=new Map();
for(const s of stations.filter(s=>s.resolved&&s.tariffText)){if(!profileMap.has(s.tariffSignature))profileMap.set(s.tariffSignature,{count:0,text:s.tariffText,hints:s.tariffHints,exampleStations:[]});const p=profileMap.get(s.tariffSignature);p.count++;if(p.exampleStations.length<8)p.exampleStations.push({stationId:s.stationId,name:s.name,network:s.api?.sNomReseau,maxPowerKw:s.maxPowerKw});}
const profiles=[...profileMap.values()].sort((a,b)=>b.count-a.count);
const output={schemaVersion:'2.0.0',generatedAt:new Date().toISOString(),operator:'e-Totem',country:'FR',scope:{physicalCpoDirectOnly:true,roamingIncluded:false,source:'public e-Totem Flutter map API joined to strict e-Totem IRVE inventory',nativeFilter:'bOcpi=0 AND bGireve=0 AND bItinerance=0',noGuessedFallback:true},harvest:{strategy:'real Flutter headers + Mane sentry + adaptive geographic tiles + local ID/coordinate join + bounded targeted fallback',concurrency:CONCURRENCY,initialTileCount:initialTiles.length,tileStats:harvest.stats,fallbackStats},counts:{inventoryStations:targets.length,resolvedStations:exact+coordFallback,exactIdMatches:exact,coordinateFallbackMatches:coordFallback,unresolvedStations:unresolved,resolvedWithTariffText:withTariff,uniqueTariffProfiles:profiles.length},tariffProfiles:profiles,stations};
fs.mkdirSync('data/national',{recursive:true});fs.writeFileSync(OUTPUT,zlib.gzipSync(Buffer.from(JSON.stringify(output),'utf8'),{level:9}));
console.log(JSON.stringify({harvest:output.harvest,counts:output.counts},null,2));
console.log(JSON.stringify(profiles.slice(0,30).map((p,i)=>({rank:i+1,count:p.count,text:p.text.slice(0,900),hints:p.hints,examples:p.exampleStations.slice(0,3)})),null,2));
