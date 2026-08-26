#!/usr/bin/env node
import fs from 'node:fs';
import zlib from 'node:zlib';
import { chromium } from 'playwright-core';

const INPUT='data/national/waat_direct_stations_france.json.gz';
const OUTPUT='data/national/waat_monta_direct_tariffs_france.json.gz';
const REPORT='data/reports/waat_monta_national_tariffs_report.json';
const CONCURRENCY=Math.max(1,Math.min(8,Number(process.env.WAAT_CONCURRENCY||6)));
const MAX_MATCH_M=180;
const EXTRA_MATCH_M=30;
const WAAT_RE=/(^|[^a-z0-9])(waat|fr\s*\*?\s*wa2|frwa2)([^a-z0-9]|$)/i;

function gunzipJson(path){return JSON.parse(zlib.gunzipSync(fs.readFileSync(path)));}
function round(n,d=4){const p=10**d;return Math.round(Number(n)*p)/p;}
function loc(o){
  if(!o)return null;
  if(typeof o.location==='string'){
    const p=o.location.split(',').map(Number);
    if(p.length>=2&&p.every(Number.isFinite))return [p[0],p[1]];
  }
  if(Number.isFinite(o.latitude)&&Number.isFinite(o.longitude))return [o.latitude,o.longitude];
  return null;
}
function distM(a,b){
  if(!a||!b)return null;
  const R=6371000,rad=x=>x*Math.PI/180,dLat=rad(b[0]-a[0]),dLon=rad(b[1]-a[1]);
  const h=Math.sin(dLat/2)**2+Math.cos(rad(a[0]))*Math.cos(rad(b[0]))*Math.sin(dLon/2)**2;
  return 2*R*Math.asin(Math.sqrt(h));
}
function singleEur(label){
  const s=String(label||'').replace(/\u00a0/g,' ').trim();
  const m=s.match(/^\s*(\d+(?:[.,]\d+)?)\s*EUR\s*$/i);
  if(!m)return null;
  const v=Number(m[1].replace(',','.'));
  return Number.isFinite(v)?v:null;
}
function compactThresholds(o){
  const out={};
  for(const [k,v] of Object.entries(o||{}))if(/^min_price_by_kw_threshold\./.test(k)&&Number.isFinite(Number(v)))out[k.replace('min_price_by_kw_threshold.','')]=Number(v);
  return out;
}
function connectorKind(o){
  const t=String(o?.type_label||'').toUpperCase();
  if(t==='AC')return 'AC';
  if(t==='DC')return 'DC';
  if(t.includes('AC')&&t.includes('DC'))return 'MIXED';
  const ids=(o?.connectors||[]).map(x=>String(x?.identifier||'').toLowerCase());
  const hasDc=ids.some(x=>x.includes('ccs')||x.includes('chademo'));
  const hasAc=ids.some(x=>x.includes('type2'));
  if(hasAc&&hasDc)return 'MIXED';
  if(hasDc)return 'DC';
  if(hasAc)return 'AC';
  return null;
}
function sanitizeGroup(o,distance){
  const price=singleEur(o?.price_label);
  const dynamic=o?.master_pricing_type_dynamic===true;
  const kind=connectorKind(o);
  let blockingReason=null;
  if(dynamic)blockingReason='dynamic_pricing';
  else if(price==null)blockingReason=String(o?.price_label||'').includes('-')?'price_range':'non_single_eur_price';
  else if(price<=0)blockingReason='zero_price_not_auto_ranked';
  return {
    montaGroupId:Number(o?.id),
    montaIdentifier:o?.identifier||null,
    name:o?.name||null,
    operatorName:o?.operator_name||null,
    operatorId:Number.isFinite(Number(o?.operator_id))?Number(o.operator_id):null,
    coordinates:loc(o),
    distanceM:distance==null?null:round(distance,1),
    visibility:o?.visibility||null,
    connected:o?.connected??null,
    state:o?.state||null,
    minPowerKw:Number.isFinite(Number(o?.min_kw))?Number(o.min_kw):null,
    maxPowerKw:Number.isFinite(Number(o?.max_kw))?Number(o.max_kw):null,
    powerLabel:o?.max_kw_label||null,
    kind,
    typeLabel:o?.type_label||null,
    connectorLabel:o?.connector_label||null,
    connectors:(o?.connectors||[]).map(c=>({identifier:c?.identifier||null,name:c?.name||null})),
    priceLabel:o?.price_label||null,
    directEurPerKwh:price,
    dynamicPricing:dynamic,
    rawMinPriceByKwThreshold:compactThresholds(o),
    rankable:blockingReason==null,
    blockingReason,
  };
}
function physicalKinds(station){
  const kinds=new Set();
  for(const e of station?.evses||[]){
    if(String(e?.comboCcs||'').toLowerCase()==='true'||String(e?.chademo||'').toLowerCase()==='true')kinds.add('DC');
    if(String(e?.type2||'').toLowerCase()==='true')kinds.add('AC');
  }
  return [...kinds];
}
function candidateApplies(group,station){
  if(!group?.rankable)return false;
  const powers=(station?.powerKwValues||[]).map(Number).filter(Number.isFinite);
  if(!powers.length)return true;
  const lo=Number.isFinite(group.minPowerKw)?group.minPowerKw-0.6:-Infinity;
  const hi=Number.isFinite(group.maxPowerKw)?group.maxPowerKw+0.6:Infinity;
  return powers.some(p=>p>=lo&&p<=hi);
}

const source=gunzipJson(INPUT);
const stations=(source.stations||[]).filter(s=>Array.isArray(s.coordinates)&&s.coordinates.length>=2);
if(!stations.length)throw new Error('WAAT inventory has no coordinates');

const chromeCandidates=['/usr/bin/google-chrome','/usr/bin/google-chrome-stable','/usr/bin/chromium','/usr/bin/chromium-browser'];
const executablePath=chromeCandidates.find(p=>fs.existsSync(p));
if(!executablePath)throw new Error('No Chromium/Chrome executable found');
const browser=await chromium.launch({executablePath,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const context=await browser.newContext({locale:'fr-FR',userAgent:'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',viewport:{width:1280,height:900}});

// Bootstrap exactly like Monta's public map. Guest authorization is retained only in memory.
const boot=await context.newPage();
let mapHeaders=null;
boot.on('response',async r=>{
  if(r.url().includes('api.monta.app/api/v1/charge_points/map')){
    try{mapHeaders=await r.request().allHeaders();}catch{}
  }
});
const [seedLat,seedLng]=stations[0].coordinates;
await boot.goto(`https://maps.monta.app/?lat=${seedLat}&lng=${seedLng}&zoom=16&locale=fr`,{waitUntil:'domcontentloaded',timeout:60000});
for(let i=0;i<30&&!mapHeaders;i++)await boot.waitForTimeout(500);
if(!mapHeaders)throw new Error('Monta public map did not expose authenticated map request headers');
const safeHeaders={};
for(const [k,v] of Object.entries(mapHeaders)){
  const lk=k.toLowerCase();
  if(['host','content-length','cookie','origin','referer'].includes(lk)||lk.startsWith('sec-')||lk.startsWith(':'))continue;
  safeHeaders[k]=v;
}
if(!Object.keys(safeHeaders).some(k=>k.toLowerCase()==='authorization'))throw new Error('Monta guest Authorization header not observed');
await boot.close();

let cursor=0,completed=0;
const results=new Array(stations.length);
async function worker(workerId){
  const page=await context.newPage();
  await page.setExtraHTTPHeaders(safeHeaders);
  while(true){
    const idx=cursor++; if(idx>=stations.length)break;
    const st=stations[idx], [lat,lng]=st.coordinates;
    const dLat=0.0020,dLon=0.0028;
    const url=`https://api.monta.app/api/v1/charge_points/map?top=${lat+dLat}&bottom=${lat-dLat}&left=${lng-dLon}&right=${lng+dLon}&zoom=17&center_lat=${lat}&center_lng=${lng}&segmented=1&busy_all=1&busy_queue=1&passive=1`;
    let status=null,error=null,items=[];
    try{
      const r=await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000}); status=r?.status()??null;
      const txt=await r?.text(); let j=null; try{j=JSON.parse(txt||'')}catch{}
      if(status===200&&j){
        const raw=[...(j.list||[]),...(j.single_list||[])];
        const dedup=[...new Map(raw.map(x=>[`${x.document||''}:${x.id}`,x])).values()];
        const nearby=dedup.map(x=>({x,d:distM(st.coordinates,loc(x))})).filter(y=>WAAT_RE.test(String(y.x?.operator_name||y.x?.operator||''))&&y.d!=null&&y.d<=MAX_MATCH_M).sort((a,b)=>a.d-b.d);
        if(nearby.length){
          const limit=Math.min(MAX_MATCH_M,Math.max(35,nearby[0].d+EXTRA_MATCH_M));
          items=nearby.filter(y=>y.d<=limit).map(y=>sanitizeGroup(y.x,y.d));
        }
      }else error=`http_${status}`;
    }catch(e){error=String(e).slice(0,300);}
    const unique=[...new Map(items.map(x=>[x.montaGroupId,x])).values()];
    const rankableGroups=unique.filter(g=>candidateApplies(g,st));
    const priceSet=[...new Set(rankableGroups.map(g=>g.directEurPerKwh))];
    const stationRankable=rankableGroups.length>0;
    results[idx]={
      stationId:st.stationId,
      stationIdNormalized:st.stationIdNormalized,
      stationName:st.stationName,
      address:st.address,
      cityCodeInsee:st.cityCodeInsee,
      coordinates:st.coordinates,
      evseIds:(st.evses||[]).map(e=>e.evseIdNormalized),
      powerKwValues:st.powerKwValues||[],
      physicalKinds:physicalKinds(st),
      mapHttpStatus:status,
      mapError:error,
      montaGroups:unique,
      rankableGroups,
      rankableDirect:stationRankable,
      distinctRankablePricesEur:priceSet,
      blockingReason:stationRankable?null:(unique.length?'no_unambiguous_positive_static_eur_group':'no_close_waat_group_found'),
    };
    completed++;
    if(completed%25===0||completed===stations.length)console.log(`WAAT Monta ${completed}/${stations.length}`);
  }
  await page.close();
}
await Promise.all(Array.from({length:CONCURRENCY},(_,i)=>worker(i)));
await browser.close();

const valid=results.filter(Boolean);
const allGroups=[...new Map(valid.flatMap(s=>s.montaGroups.map(g=>[g.montaGroupId,g])).map(x=>x)).values()];
const allRankableGroups=[...new Map(valid.flatMap(s=>s.rankableGroups.map(g=>[g.montaGroupId,g])).map(x=>x)).values()];
const counts={
  inventoryStations:Number(source.counts?.franceStationCount||source.stations?.length||0),
  queriedStations:valid.length,
  stationsWithMontaGroup:valid.filter(s=>s.montaGroups.length).length,
  rankableStations:valid.filter(s=>s.rankableDirect).length,
  unresolvedStations:valid.filter(s=>!s.rankableDirect).length,
  uniqueMontaGroups:allGroups.length,
  rankableMontaGroups:allRankableGroups.length,
  priceRangeGroups:allGroups.filter(g=>g.blockingReason==='price_range').length,
  dynamicGroups:allGroups.filter(g=>g.blockingReason==='dynamic_pricing').length,
  zeroPriceGroups:allGroups.filter(g=>g.blockingReason==='zero_price_not_auto_ranked').length,
  mapErrors:valid.filter(s=>s.mapError).length,
};
const tariffDistribution={};
for(const g of allRankableGroups){const k=Number(g.directEurPerKwh).toFixed(3);tariffDistribution[k]=(tariffDistribution[k]||0)+1;}
const payload={
  schemaVersion:'1.0.0',dataset:'waat-monta-direct-tariffs-france',operator:'WAAT',country:'FR',generatedAt:new Date().toISOString(),
  source:{type:'monta-public-web-map-guest-browser',mapUrl:'https://maps.monta.app/',apiBase:'https://api.monta.app',note:'Guest authorization used only in browser memory; credentials are not persisted.'},
  scope:{directCpoOnly:true,operatorPrefix:'FR*WA2',roamingIncluded:false,stationSpecificPricing:true,unresolvedCasesNeverRankable:true,zeroPriceAutoRanked:false,dynamicPricingAutoRanked:false,rangePricingAutoRanked:false},
  counts,tariffDistribution,stations:valid,
};
fs.mkdirSync('data/national',{recursive:true});fs.mkdirSync('data/reports',{recursive:true});
fs.writeFileSync(OUTPUT,zlib.gzipSync(Buffer.from(JSON.stringify(payload))));
const report={generatedAt:payload.generatedAt,counts,tariffDistribution,examples:{rankable:valid.filter(s=>s.rankableDirect).slice(0,15).map(s=>({stationId:s.stationIdNormalized,name:s.stationName,address:s.address,powers:s.powerKwValues,groups:s.rankableGroups.map(g=>({id:g.montaGroupId,name:g.name,kind:g.kind,minKw:g.minPowerKw,maxKw:g.maxPowerKw,eurPerKwh:g.directEurPerKwh,priceLabel:g.priceLabel,distanceM:g.distanceM}))})),unresolved:valid.filter(s=>!s.rankableDirect).slice(0,15).map(s=>({stationId:s.stationIdNormalized,name:s.stationName,address:s.address,powers:s.powerKwValues,reason:s.blockingReason,groups:s.montaGroups.map(g=>({id:g.montaGroupId,name:g.name,priceLabel:g.priceLabel,reason:g.blockingReason,distanceM:g.distanceM}))}))}};
fs.writeFileSync(REPORT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({counts,tariffDistribution,examples:report.examples},null,2));
