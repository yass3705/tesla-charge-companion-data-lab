import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import { performance } from 'node:perf_hooks';
import { DirectElectroverseClient, aliasBatchQuery, SINGLE_LOCATION_QUERY, PAGED_LOCATION_QUERY } from './lib/electroverse_direct_client.mjs';
import { completeLocation } from './lib/electroverse_response_integrity.mjs';
import {summarizeAttempt,boundedTrace} from './lib/electroverse_failure_diagnostics.mjs';
import {isRateLimited, rateLimitPlan, deferUnresolved} from './lib/electroverse_rate_limit_guard.mjs';

const API_KEY=process.env.ELECTROVERSE_API_KEY;
const BATCH_SIZE=Number(process.env.ELECTROVERSE_BATCH_SIZE||5);
const CONCURRENCY=Number(process.env.ELECTROVERSE_CONCURRENCY||2);
const WAVE_PAUSE_MS=Number(process.env.ELECTROVERSE_WAVE_PAUSE_MS||750);
const FALLBACK_INTERVAL_MS=Number(process.env.ELECTROVERSE_FALLBACK_INTERVAL_MS||750);
const SELECTION='reports/electroverse/incremental-selection.json';
const MAPPING='data/electroverse/irve_location_mapping.json';
const DIR='data/electroverse/tariff_cache';
const MANIFEST=`${DIR}/manifest.json`;
const CHECKED=`${DIR}/checked-at.json`;
const FAILURE_DIAGNOSTICS='reports/electroverse/failure-diagnostics.json';
if(!API_KEY) throw new Error('ELECTROVERSE_API_KEY required');

// A window checkpoint holds hard links to the preceding cache generation.
async function replaceJsonFile(path, contents) {
  const temporary = path + '.writing';
  await fs.writeFile(temporary, contents);
  await fs.rename(temporary, path);
}

const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const stable=x=>Array.isArray(x)?x.map(stable):(x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,stable(x[k])])):x);
const hash=x=>crypto.createHash('sha256').update(JSON.stringify(stable(x))).digest('hex');
const nodes=x=>(x?.edges||[]).map(e=>e?.node).filter(Boolean);
const shardFor=pk=>crypto.createHash('sha1').update(String(pk)).digest()[0]%128;
const shardName=i=>`shard-${String(i).padStart(3,'0')}.json`;

function tariffProjection(loc){
  return {
    chargingLocationPk:String(loc?.chargingLocationPk??loc?.pk??''),
    evses:nodes(loc?.evses).map(e=>({
      pk:e?.pk??null, physicalReference:e?.physicalReference??null,
      connectors:nodes(e?.connectors).map(c=>({
        pk:c?.pk??null,kilowatts:c?.kilowatts??null,speed:c?.speed??null,
        isChargingFree:c?.isChargingFree??null,standard:c?.standard??null,
        priceComponents:c?.priceComponents??null,complexPricingDetail:c?.complexPricingDetail??null,
      })).sort((a,b)=>String(a.pk).localeCompare(String(b.pk)))
    })).sort((a,b)=>String(a.pk).localeCompare(String(b.pk)))
  };
}

const selection=JSON.parse(await fs.readFile(SELECTION,'utf8'));
const mapping=JSON.parse(await fs.readFile(MAPPING,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const manifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
let checkedState={version:1,generatedAt:null,checkedAt:{}};
try {
  checkedState = JSON.parse(await fs.readFile(CHECKED, 'utf8'));
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}
if (!checkedState.checkedAt || typeof checkedState.checkedAt !== 'object' || Array.isArray(checkedState.checkedAt)) {
  throw new Error('Malformed Electroverse checked-at ledger');
}
const selected=(selection.selected||[]).map(x=>String(x.pk));
if(!selected.length){console.log(JSON.stringify({selected:0,note:'Nothing selected'},null,2));process.exit(0)}

const neededShards=[...new Set(selected.map(shardFor))], shardData=new Map(), dirtyShards=new Set();
for(const i of neededShards){
  const data = JSON.parse(await fs.readFile(`${DIR}/${shardName(i)}`, 'utf8'));
  if (data.shard !== i || data.shardCount !== 128 || !data.stations ||
      typeof data.stations !== 'object' || Array.isArray(data.stations)) throw new Error('Malformed Electroverse shard');
  shardData.set(i, data);
}

const client=new DirectElectroverseClient({apiKey:API_KEY});
let requests=0,newCount=0,changed=0,unchanged=0,failures=0,pagedUsed=0,batchRequests=0,fallbackRequests=0;
const failureRows=[],t0=performance.now(),fallbackPks=[],succeeded=new Set(),batchAttempts=new Map(),batchLimited=new Set();
let fallbackNext=performance.now(),rateLimit=null;

try {
  const previous=JSON.parse(await fs.readFile(FAILURE_DIAGNOSTICS,'utf8'));
  if(previous.schemaVersion!==1||!Array.isArray(previous.events))throw Error('Invalid Electroverse diagnostic history');
  const until=previous.events.at(-1)?.rateLimit?.resumeNotBeforeUtc;
  if(until && Number.isFinite(Date.parse(until)) && Date.parse(until)>Date.now()){
    rateLimit={...previous.events.at(-1).rateLimit,phase:'checkpoint_cooldown'};
    console.log('Electroverse cooling down from earlier provider response; zero provider requests');
  }
} catch(error){if(error.code!=='ENOENT')throw error}

function applyLocation(pk,loc,mode='batch',pages=null){
  const m=byPk.get(pk);if(!m){failures++;failureRows.push({pk,error:'missing_mapping'});return false}
  const sh=shardData.get(shardFor(pk)),prev=sh.stations[pk]||null;
  const tariff=tariffProjection(loc),tariffHash=hash(tariff),nowIso=new Date().toISOString();
  checkedState.checkedAt[pk]=nowIso;
  succeeded.add(pk);
  if(!prev)newCount++;
  else if(prev.tariffHash===tariffHash){unchanged++;return true}
  else changed++;
  sh.stations[pk]={electroverseLocationPk:pk,irveStationId:m.irveStationId,irvePdcIds:m.irvePdcIds||[],
    matchConfidence:m.confidence||null,tariffHash,fetchedAt:nowIso,fetchMode:mode,pagedPages:pages,tariff};
  dirtyShards.add(shardFor(pk));return true;
}

async function fallbackPaced(query,vars){
  const now=performance.now(),wait=Math.max(0,fallbackNext-now);
  if(wait)await sleep(wait);
  fallbackNext=Math.max(fallbackNext,performance.now())+FALLBACK_INTERVAL_MS;
  requests++;fallbackRequests++;return client.request(query,vars,{attempts:1});
}
async function fetchSingle(pk){
  let last=null;const diagnostics=[];
  for(let attempt=1;attempt<=2;attempt++){
    if(attempt>1)await sleep(5000);
    last=await fallbackPaced(SINGLE_LOCATION_QUERY,{pk});
    const loc=completeLocation(last,'chargingLocation',pk);
    diagnostics.push(summarizeAttempt(last,{phase:'single',attempt,page:1,complete:!!loc}));
    if(loc)return {loc,mode:'single',attempts:attempt,diagnostics};
    if(isRateLimited(last))return {loc:null,last,error:'rate_limited',rateLimited:true,diagnostics};
  }
  return {loc:null,last,diagnostics};
}
async function fetchPaged(pk){
  const edges=[],cursors=new Set(),evseIds=new Set(),diagnostics=[];let after=null,meta=null,pages=0;
  for(let page=1;page<=500;page++){
    pages=page;let loc=null,last=null;
    for(let attempt=1;attempt<=3&&!loc;attempt++){
      if(attempt>1)await sleep(4000*attempt);
      last=await fallbackPaced(PAGED_LOCATION_QUERY,{pk,first:5,after});
      loc=completeLocation(last,'chargingLocation',pk,{paged:true});
      diagnostics.push(summarizeAttempt(last,{phase:'paged',attempt,page,complete:!!loc}));
      if(!loc&&isRateLimited(last))return {loc:null,pages,last,error:'rate_limited',rateLimited:true,diagnostics};
    }
    if(!loc?.evses)return {loc:null,pages,last,diagnostics};
    for(const edge of loc.evses.edges){
      if(edge.node.pk!=null){
        const id=String(edge.node.pk);
        if(evseIds.has(id))return {loc:null,pages,error:'duplicate_evse_across_pages',diagnostics};
        evseIds.add(id);
      }
    }
    meta??=loc;edges.push(...loc.evses.edges);const pi=loc.evses.pageInfo;
    if(!pi.hasNextPage)return {loc:{...meta,evses:{edges,pageInfo:pi}},pages,mode:'paged',diagnostics};
    if(cursors.has(pi.endCursor))return {loc:null,pages,error:'cursor_not_advancing',diagnostics};
    cursors.add(pi.endCursor);after=pi.endCursor;
  }
  return {loc:null,pages,error:'page_limit',diagnostics};
}

const batchCandidates=[],knownPaged=[];
for(const pk of selected){
  const prev=shardData.get(shardFor(pk))?.stations?.[pk];
  if(prev?.fetchMode==='paged')knownPaged.push(pk);else batchCandidates.push(pk);
}
const groups=[];for(let i=0;i<batchCandidates.length;i+=BATCH_SIZE)groups.push(batchCandidates.slice(i,i+BATCH_SIZE));
if(!rateLimit){
  for(let i=0;i<groups.length;i+=CONCURRENCY){
    const wave=groups.slice(i,i+CONCURRENCY);
    const responses=await Promise.all(wave.map(async g=>{
      requests++;batchRequests++;
      const r=await client.request(aliasBatchQuery(g),{}, {attempts:1});
      for(let k=0;k<g.length;k++){
        const pk=g[k],loc=completeLocation(r,'s'+k,pk);
        if(loc)applyLocation(pk,loc,'batch',null);
        else{
          fallbackPks.push(pk);
          batchAttempts.set(pk,[summarizeAttempt(r,{phase:'batch',attempt:1,page:1,complete:false})]);
          if(isRateLimited(r))batchLimited.add(pk);
        }
      }
      return r;
    }));
    const firstLimited=responses.find(isRateLimited);
    if(firstLimited){
      rateLimit=rateLimitPlan(firstLimited,'batch');
      console.log('Electroverse circuit breaker: rate limit during batch; remaining requests deferred');
      break;
    }
    if((i/CONCURRENCY)%10===0)console.log('batchWave='+Math.floor(i/CONCURRENCY+1)+'/'+Math.ceil(groups.length/CONCURRENCY)+' requests='+requests);
    await sleep(WAVE_PAUSE_MS);
  }
}
if(!rateLimit){
  fallbackPks.push(...knownPaged);
  for(const pk of fallbackPks){
    const prev=shardData.get(shardFor(pk))?.stations?.[pk];
    let result,history=batchAttempts.get(pk)||[];
    if(prev?.fetchMode==='paged')result=await fetchPaged(pk);
    else{
      result=await fetchSingle(pk);
      history=[...history,...(result.diagnostics||[])];
      if(!result.loc&&!result.rateLimited)result=await fetchPaged(pk);
    }
    if(!result.loc){
      failures++;
      failureRows.push({pk,error:result.error||'fetch_failed',pages:result.pages??null,
        diagnostics:boundedTrace([...history,...(result.diagnostics||[])])});
      if(result.rateLimited){
        rateLimit=rateLimitPlan(result.last,prev?.fetchMode==='paged'?'paged':'fallback');
        console.log('Electroverse circuit breaker: rate limit during fallback; remaining requests deferred');
        break;
      }
      continue;
    }
    if(result.mode==='paged')pagedUsed++;
    applyLocation(pk,result.loc,result.mode||'single',result.pages??null);
  }
}
if(rateLimit){
  const already=new Set(failureRows.map(x=>x.pk));
  for(const pk of selected){
    if(succeeded.has(pk)||already.has(pk))continue;
    failures++;
    failureRows.push({pk,error:batchLimited.has(pk)?'rate_limited':'deferred_due_to_rate_limit',
      pages:null,diagnostics:boundedTrace(batchAttempts.get(pk)||[])});
  }
  const unresolved=deferUnresolved(selected,succeeded,failureRows);
  if(unresolved.length!==0)throw Error('Untracked Electroverse rate-limited identity');
}
if(failures!==failureRows.length)throw Error('Electroverse failure count mismatch');

for(const i of dirtyShards){
  const data=shardData.get(i);data.generatedAt=new Date().toISOString();
  await replaceJsonFile(`${DIR}/${shardName(i)}`,JSON.stringify(data,null,2)+'\n');
}
checkedState.generatedAt=new Date().toISOString();await replaceJsonFile(CHECKED,JSON.stringify(checkedState)+'\n');

let totalStations=0,maxShardBytes=0;const updatedMeta=[];
for(let i=0;i<128;i++){
  const path=`${DIR}/${shardName(i)}`;const data=shardData.has(i)?shardData.get(i):JSON.parse(await fs.readFile(path,'utf8'));
  const count=Object.keys(data.stations||{}).length,sizeBytes=(await fs.stat(path)).size;
  totalStations+=count;maxShardBytes=Math.max(maxShardBytes,sizeBytes);updatedMeta.push({shard:i,file:shardName(i),count,sizeBytes});
}
manifest.generatedAt=new Date().toISOString();manifest.totalStations=totalStations;manifest.maxShardBytes=maxShardBytes;manifest.shards=updatedMeta;
manifest.lastIncrementalRefresh={runAt:manifest.generatedAt,method:'hybrid-full-query-batch5x2-single-paged-fallback',selected:selected.length,new:newCount,changed,unchanged,failures,pagedUsed,batchRequests,fallbackRequests,httpRequests:requests,elapsedSeconds:Number(((performance.now()-t0)/1000).toFixed(2)),rateLimit};
await replaceJsonFile(MANIFEST,JSON.stringify(manifest,null,2)+'\n');
await replaceJsonFile('reports/electroverse/hybrid-refresh-failures.json',JSON.stringify({generatedAt:new Date().toISOString(),failures:failureRows},null,2)+'\n');
if(failureRows.length){
  let history={schemaVersion:1,events:[]};
  try{history=JSON.parse(await fs.readFile(FAILURE_DIAGNOSTICS,'utf8'))}
  catch(error){if(error.code!=='ENOENT')throw error}
  if(history.schemaVersion!==1||!Array.isArray(history.events))throw Error('Invalid failure diagnostics history');
  history.events.push({collectedAt:new Date().toISOString(),runId:process.env.GITHUB_RUN_ID||null,
    source:'FR:electroverse_full',rateLimit,failures:failureRows});
  await replaceJsonFile(FAILURE_DIAGNOSTICS,JSON.stringify(history,null,2)+'\n');
}
console.log(JSON.stringify({...manifest.lastIncrementalRefresh,totalStations,maxShardBytes},null,2));
if(failures)process.exitCode=2;
