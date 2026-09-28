import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import { performance } from 'node:perf_hooks';
import {
  DirectElectroverseClient,
  SINGLE_LOCATION_QUERY,
  PAGED_LOCATION_QUERY
} from './lib/electroverse_direct_client.mjs';

const API_KEY=process.env.ELECTROVERSE_API_KEY;
const REQUEST_INTERVAL_MS=Number(process.env.REQUEST_INTERVAL_MS||1500);
const SELECTION='reports/electroverse/incremental-selection.json';
const MAPPING='data/electroverse/irve_location_mapping.json';
const DIR='data/electroverse/tariff_cache';
const MANIFEST=`${DIR}/manifest.json`;
if(!API_KEY) throw new Error('ELECTROVERSE_API_KEY required');

const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const stable=x=>Array.isArray(x)?x.map(stable):(x&&typeof x==='object'
  ? Object.fromEntries(Object.keys(x).sort().map(k=>[k,stable(x[k])])) : x);
const hash=x=>crypto.createHash('sha256').update(JSON.stringify(stable(x))).digest('hex');
const nodes=x=>(x?.edges||[]).map(e=>e?.node).filter(Boolean);
const shardFor=pk=>crypto.createHash('sha1').update(String(pk)).digest()[0]%128;
const shardName=i=>`shard-${String(i).padStart(3,'0')}.json`;

function tariffProjection(loc){
  return {
    chargingLocationPk:String(loc?.chargingLocationPk??loc?.pk??''),
    evses:nodes(loc?.evses).map(e=>({
      pk:e?.pk??null,
      physicalReference:e?.physicalReference??null,
      connectors:nodes(e?.connectors).map(c=>({
        pk:c?.pk??null,
        kilowatts:c?.kilowatts??null,
        speed:c?.speed??null,
        isChargingFree:c?.isChargingFree??null,
        standard:c?.standard??null,
        priceComponents:c?.priceComponents??null,
        complexPricingDetail:c?.complexPricingDetail??null,
      })).sort((a,b)=>String(a.pk).localeCompare(String(b.pk)))
    })).sort((a,b)=>String(a.pk).localeCompare(String(b.pk)))
  };
}

const selection=JSON.parse(await fs.readFile(SELECTION,'utf8'));
const mapping=JSON.parse(await fs.readFile(MAPPING,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const manifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const selected=(selection.selected||[]).map(x=>String(x.pk));
if(!selected.length){
  console.log(JSON.stringify({selected:0,note:'Nothing due'},null,2));
  process.exit(0);
}

const neededShards=[...new Set(selected.map(shardFor))];
const shardData=new Map();
for(const i of neededShards){
  const path=`${DIR}/${shardName(i)}`;
  let data={version:1,shard:i,shardCount:128,generatedAt:new Date().toISOString(),stations:{}};
  try{data=JSON.parse(await fs.readFile(path,'utf8'));}catch{}
  data.stations??={};
  shardData.set(i,data);
}

const client=new DirectElectroverseClient({apiKey:API_KEY});
let next=performance.now(),requests=0;
async function paced(query,vars){
  const now=performance.now(),wait=Math.max(0,next-now);if(wait)await sleep(wait);
  next=Math.max(next,performance.now())+REQUEST_INTERVAL_MS;
  requests++;
  return client.request(query,vars,{attempts:1});
}
async function fetchSingle(pk){
  let last=null;
  for(let attempt=1;attempt<=2;attempt++){
    if(attempt>1)await sleep(5000);
    last=await paced(SINGLE_LOCATION_QUERY,{pk});
    const loc=last.json?.data?.chargingLocation||null;
    if(loc)return{loc,mode:'single',attempts:attempt};
  }
  return{loc:null,last};
}
async function fetchPaged(pk){
  const edges=[];let after=null,meta=null,lastCursor=null,pages=0;
  for(let page=1;page<=500;page++){
    pages=page;let loc=null,last=null;
    for(let attempt=1;attempt<=3&&!loc;attempt++){
      if(attempt>1)await sleep(4000*attempt);
      last=await paced(PAGED_LOCATION_QUERY,{pk,first:5,after});
      loc=last.json?.data?.chargingLocation||null;
    }
    if(!loc?.evses)return{loc:null,pages,last};
    meta??=loc;edges.push(...(loc.evses.edges||[]));
    const pi=loc.evses.pageInfo||{};
    if(!pi.hasNextPage)return{loc:{...meta,evses:{edges,pageInfo:pi}},pages,mode:'paged'};
    if(!pi.endCursor||pi.endCursor===lastCursor)return{loc:null,pages,error:'cursor_not_advancing'};
    lastCursor=pi.endCursor;after=pi.endCursor;
  }
  return{loc:null,pages,error:'page_limit'};
}

let newCount=0,changed=0,unchanged=0,failures=0,pagedUsed=0;
const failureRows=[],t0=performance.now();

for(let i=0;i<selected.length;i++){
  const pk=selected[i],m=byPk.get(pk);
  if(!m){failures++;failureRows.push({pk,error:'missing_mapping'});continue;}
  const sh=shardData.get(shardFor(pk));
  const prev=sh.stations[pk]||null;
  let result;
  if(prev?.fetchMode==='paged'){
    result=await fetchPaged(pk);
  }else{
    result=await fetchSingle(pk);
    if(!result.loc)result=await fetchPaged(pk);
  }
  if(!result.loc){
    failures++;failureRows.push({pk,error:result.error||'fetch_failed',pages:result.pages??null});continue;
  }
  if(result.mode==='paged')pagedUsed++;
  const tariff=tariffProjection(result.loc),tariffHash=hash(tariff);
  if(!prev)newCount++;else if(prev.tariffHash===tariffHash)unchanged++;else changed++;
  sh.stations[pk]={
    electroverseLocationPk:pk,
    irveStationId:m.irveStationId,
    irvePdcIds:m.irvePdcIds||[],
    matchConfidence:m.confidence||null,
    tariffHash,
    fetchedAt:new Date().toISOString(),
    fetchMode:result.mode||'single',
    pagedPages:result.pages??null,
    tariff
  };
  if((i+1)%50===0||i===selected.length-1)
    console.log(`processed=${i+1}/${selected.length} new=${newCount} changed=${changed} unchanged=${unchanged} failures=${failures} paged=${pagedUsed} requests=${requests}`);
}

for(const [i,data] of shardData){
  data.generatedAt=new Date().toISOString();
  await fs.writeFile(`${DIR}/${shardName(i)}`,JSON.stringify(data,null,2)+'\n');
}

let totalStations=0,maxShardBytes=0;
const updatedMeta=[];
for(let i=0;i<128;i++){
  const path=`${DIR}/${shardName(i)}`;
  let data;
  if(shardData.has(i))data=shardData.get(i);
  else data=JSON.parse(await fs.readFile(path,'utf8'));
  const count=Object.keys(data.stations||{}).length;
  const sizeBytes=(await fs.stat(path)).size;
  totalStations+=count;maxShardBytes=Math.max(maxShardBytes,sizeBytes);
  updatedMeta.push({shard:i,file:shardName(i),count,sizeBytes});
}
manifest.generatedAt=new Date().toISOString();
manifest.totalStations=totalStations;
manifest.maxShardBytes=maxShardBytes;
manifest.shards=updatedMeta;
manifest.lastIncrementalRefresh={
  runAt:manifest.generatedAt,selected:selected.length,new:newCount,changed,unchanged,failures,pagedUsed,
  httpRequests:requests,elapsedSeconds:Number(((performance.now()-t0)/1000).toFixed(2))
};
await fs.writeFile(MANIFEST,JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({...manifest.lastIncrementalRefresh,totalStations,maxShardBytes},null,2));
if(failures)process.exitCode=2;