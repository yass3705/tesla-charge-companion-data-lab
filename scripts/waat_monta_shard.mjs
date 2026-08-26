#!/usr/bin/env node
import fs from 'node:fs';
import zlib from 'node:zlib';
import { chromium } from 'playwright-core';

const INPUT='data/national/waat_direct_stations_france.json.gz';
const SHARD_COUNT=Math.max(1,Number(process.env.WAAT_SHARD_COUNT||4));
const SHARD_INDEX=Math.max(0,Number(process.env.WAAT_SHARD_INDEX||0));
const CONCURRENCY=Math.max(1,Math.min(3,Number(process.env.WAAT_CONCURRENCY||2)));
const MAX_MATCH_M=180;
const EXTRA_MATCH_M=30;
const WAAT_RE=/(^|[^a-z0-9])(waat|fr\s*\*?\s*wa2|frwa2)([^a-z0-9]|$)/i;
if(SHARD_INDEX>=SHARD_COUNT)throw new Error(`invalid shard ${SHARD_INDEX}/${SHARD_COUNT}`);

function gunzipJson(path){return JSON.parse(zlib.gunzipSync(fs.readFileSync(path)));}
function round(n,d=4){const p=10**d;return Math.round(Number(n)*p)/p;}
function sleep(ms){return new Promise(r=>setTimeout(r,ms));}
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
  else if(kind==='MIXED'||!kind)blockingReason='ambiguous_connector_kind';
  return {
    montaGroupId:Number(o?.id), montaIdentifier:o?.identifier||null, name:o?.name||null,
    operatorName:o?.operator_name||null, operatorId:Number.isFinite(Number(o?.operator_id))?Number(o.operator_id):null,
    coordinates:loc(o), distanceM:distance==null?null:round(distance,1), visibility:o?.visibility||null,
    connected:o?.connected??null, state:o?.state||null,
    minPowerKw:Number.isFinite(Number(o?.min_kw))?Number(o.min_kw):null,
    maxPowerKw:Number.isFinite(Number(o?.max_kw))?Number(o.max_kw):null,
    powerLabel:o?.max_kw_label||null, kind, typeLabel:o?.type_label||null,
    connectorLabel:o?.connector_label||null,
    connectors:(o?.connectors||[]).map(c=>({identifier:c?.identifier||null,name:c?.name||null})),
    priceLabel:o?.price_label||null, directEurPerKwh:price, dynamicPricing:dynamic,
    rawMinPriceByKwThreshold:compactThresholds(o), rankable:blockingReason==null, blockingReason,
  };
}
function evseKinds(e){
  const out=[];
  if(String(e?.type2||'').toLowerCase()==='true')out.push('AC');
  if(String(e?.comboCcs||'').toLowerCase()==='true'||String(e?.chademo||'').toLowerCase()==='true')out.push('DC');
  return out;
}
function physicalConfigs(station){
  const m=new Map();
  for(const e of station?.evses||[]){
    const p=Number(e?.powerKw); if(!Number.isFinite(p)||p<=0)continue;
    for(const kind of evseKinds(e))m.set(`${kind}|${p.toFixed(2)}`,{kind,powerKw:p});
  }
  return [...m.values()].sort((a,b)=>a.kind.localeCompare(b.kind)||a.powerKw-b.powerKw);
}
function compatible(group,cfg){
  if(!group?.rankable||group.kind!==cfg.kind)return false;
  const lo=Number.isFinite(group.minPowerKw)?group.minPowerKw-0.6:-Infinity;
  const hi=Number.isFinite(group.maxPowerKw)?group.maxPowerKw+0.6:Infinity;
  return cfg.powerKw>=lo&&cfg.powerKw<=hi;
}
function integrationConfigs(groups,configs){
  return configs.map(cfg=>{
    const hits=groups.filter(g=>compatible(g,cfg));
    const prices=[...new Set(hits.map(g=>Number(g.directEurPerKwh).toFixed(6)))];
    const safe=hits.length>0&&prices.length===1;
    return {...cfg,rankable:safe,directEurPerKwh:safe?Number(prices[0]):null,groupIds:hits.map(g=>g.montaGroupId),blockingReason:safe?null:(hits.length?'conflicting_group_prices':'no_exact_group_match')};
  });
}

const source=gunzipJson(INPUT);
const all=(source.stations||[]).filter(s=>Array.isArray(s.coordinates)&&s.coordinates.length>=2);
const stations=all.filter((_,i)=>i%SHARD_COUNT===SHARD_INDEX);
if(!stations.length)throw new Error('empty shard');

const chromeCandidates=['/usr/bin/google-chrome','/usr/bin/google-chrome-stable','/usr/bin/chromium','/usr/bin/chromium-browser'];
const executablePath=chromeCandidates.find(p=>fs.existsSync(p));
if(!executablePath)throw new Error('No Chromium/Chrome executable found');
const browser=await chromium.launch({executablePath,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const context=await browser.newContext({locale:'fr-FR',viewport:{width:1280,height:900}});
const boot=await context.newPage();
let mapHeaders=null;
boot.on('response',async r=>{if(r.url().includes('api.monta.app/api/v1/charge_points/map'))try{mapHeaders=await r.request().allHeaders();}catch{}});
const [seedLat,seedLng]=stations[0].coordinates;
await boot.goto(`https://maps.monta.app/?lat=${seedLat}&lng=${seedLng}&zoom=16&locale=fr`,{waitUntil:'domcontentloaded',timeout:60000});
for(let i=0;i<30&&!mapHeaders;i++)await boot.waitForTimeout(500);
if(!mapHeaders)throw new Error('Monta public map did not expose map request headers');
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
async function worker(){
  const page=await context.newPage(); await page.setExtraHTTPHeaders(safeHeaders);
  while(true){
    const idx=cursor++; if(idx>=stations.length)break;
    const st=stations[idx],[lat,lng]=st.coordinates,dLat=0.0020,dLon=0.0028;
    const url=`https://api.monta.app/api/v1/charge_points/map?top=${lat+dLat}&bottom=${lat-dLat}&left=${lng-dLon}&right=${lng+dLon}&zoom=17&center_lat=${lat}&center_lng=${lng}&segmented=1&busy_all=1&busy_queue=1&passive=1`;
    let status=null,error=null,items=[];
    for(let attempt=0;attempt<4;attempt++){
      try{
        const r=await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000}); status=r?.status()??null;
        const txt=await r?.text(); let j=null; try{j=JSON.parse(txt||'')}catch{}
        if(status===200&&j){
          const raw=[...(j.list||[]),...(j.single_list||[])];
          const dedup=[...new Map(raw.map(x=>[`${x.document||''}:${x.id}`,x])).values()];
          const nearby=dedup.map(x=>({x,d:distM(st.coordinates,loc(x))})).filter(y=>WAAT_RE.test(String(y.x?.operator_name||y.x?.operator||''))&&y.d!=null&&y.d<=MAX_MATCH_M).sort((a,b)=>a.d-b.d);
          if(nearby.length){const limit=Math.min(MAX_MATCH_M,Math.max(35,nearby[0].d+EXTRA_MATCH_M));items=nearby.filter(y=>y.d<=limit).map(y=>sanitizeGroup(y.x,y.d));}
          error=null; break;
        }
        error=`http_${status}`;
        if(status!==429)break;
      }catch(e){error=String(e).slice(0,300);}
      await sleep([1500,4000,9000,16000][attempt]||16000);
    }
    const unique=[...new Map(items.map(x=>[x.montaGroupId,x])).values()];
    const configs=physicalConfigs(st);
    const safeConfigs=integrationConfigs(unique,configs);
    const rankableGroups=unique.filter(g=>g.rankable);
    results[idx]={stationId:st.stationId,stationIdNormalized:st.stationIdNormalized,stationName:st.stationName,address:st.address,cityCodeInsee:st.cityCodeInsee,coordinates:st.coordinates,evseIds:(st.evses||[]).map(e=>e.evseIdNormalized),physicalConfigs:configs,mapHttpStatus:status,mapError:error,montaGroups:unique,rankableGroups,integrationConfigs:safeConfigs,rankableDirect:safeConfigs.some(c=>c.rankable),blockingReason:safeConfigs.some(c=>c.rankable)?null:(unique.length?'no_safe_config_match':'no_close_waat_group_found')};
    completed++; if(completed%25===0||completed===stations.length)console.log(`WAAT shard ${SHARD_INDEX}: ${completed}/${stations.length}`);
  }
  await page.close();
}
await Promise.all(Array.from({length:CONCURRENCY},worker));
await browser.close();

const valid=results.filter(Boolean);
const out={schemaVersion:'2.0.0',dataset:'waat-monta-direct-tariffs-shard',operator:'WAAT',country:'FR',generatedAt:new Date().toISOString(),shardIndex:SHARD_INDEX,shardCount:SHARD_COUNT,sourceInventoryStations:all.length,stations:valid};
fs.mkdirSync('data/shards',{recursive:true});
const path=`data/shards/waat_monta_shard_${SHARD_INDEX}.json.gz`;
fs.writeFileSync(path,zlib.gzipSync(Buffer.from(JSON.stringify(out))));
const statuses={}; for(const s of valid){const k=String(s.mapHttpStatus);statuses[k]=(statuses[k]||0)+1;}
console.log(JSON.stringify({shardIndex:SHARD_INDEX,stations:valid.length,statuses,mapErrors:valid.filter(s=>s.mapError).length,rankableStations:valid.filter(s=>s.rankableDirect).length},null,2));
