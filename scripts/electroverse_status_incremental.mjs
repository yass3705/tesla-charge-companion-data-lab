/**
 * Incremental, resumable Electroverse EVSE status collection.
 * Commands:
 *   node scripts/electroverse_status_incremental.mjs collect [partition]
 *   node scripts/electroverse_status_incremental.mjs finalize
 *   node scripts/electroverse_status_incremental.mjs validate
 *
 * Each partition is persisted independently; no national ledger until all
 * partitions are recent, have matching tariff-cache provenance and satisfy QA.
 * API failures are never interpreted as AVAILABLE/CHARGING.
 */
import fs from 'node:fs/promises';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import {DirectElectroverseClient} from './lib/electroverse_direct_client.mjs';

const CACHE='data/electroverse/tariff_cache';
const OUTPUT='data/electroverse/live_statuses';
const PARTS=OUTPUT+'/parts';
const count=16;
const mode=process.argv[2]||'collect',partNum=Number(process.argv[3]||process.env.ELECTROVERSE_STATUS_PARTITION||0);
const maxPerRun=Math.max(30,Number(process.env.ELECTROVERSE_STATUS_RUN_LIMIT||1700));
const attempts=Number(process.env.ELECTROVERSE_STATUS_ATTEMPTS||2);
const failBudget=Math.max(6,Number(process.env.ELECTROVERSE_STATUS_FAILURE_BUDGET||48));
const delay=Math.max(450,Number(process.env.ELECTROVERSE_STATUS_REQUEST_DELAY_MS||800));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const manifest=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const cacheFingerprint=sha(JSON.stringify({date:manifest.generatedAt,shards:manifest.shards?.map(x=>[x.file,x.count,x.sizeBytes])}));
const refs=new Map();
for(const sh of manifest.shards||[]){
 const d=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
 for(const [loc,row] of Object.entries(d.stations||{})){
  refs.set(String(loc),new Set((row.tariff?.evses||[]).map(e=>String(e.pk)).filter(Boolean)));
 }
}
const all=[...refs.keys()].sort((a,b)=>a.localeCompare(b,'en',{numeric:true}));
const partitions=Array.from({length:count},()=>[]);
all.forEach((pk,i)=>partitions[i%count].push(pk));
const sourceTotal=[...refs.values()].reduce((a,s)=>a+s.size,0);
const filename=i=>PARTS+'/part-'+String(i).padStart(2,'0')+'.json';
const fetchPart=async i=>{try{return JSON.parse(await fs.readFile(filename(i),'utf8'))}catch(e){if(e.code==='ENOENT')return null;throw e}};
const client=new DirectElectroverseClient({timeoutMs:19000});
const queryOne='query StatusOne($pk:String!,$after:String,$first:Int!){chargingLocation(pk:$pk){chargingLocationPk evses(first:$first,after:$after){edges{node{pk status}} pageInfo{hasNextPage endCursor}}}}';
const queryBatch=ids=>'query Batch { '+ids.map((pk,i)=>'s'+i+':chargingLocation(pk:'+JSON.stringify(pk)+'){evses(first:10){edges{node{pk status}}pageInfo{hasNextPage endCursor}}}').join(' ')+' }';
let requests=0,pages=0;
const normalized=loc=>(loc?.evses?.edges||[]).map(e=>e?.node).filter(x=>x?.pk!=null).map(e=>[String(e.pk),String(e.status||'UNKNOWN').toUpperCase()]);
async function fullPage(pk,first){
 let rows=normalized(first);
 let pi=first.evses?.pageInfo||{},cursor=pi.endCursor,hasMore=pi.hasNextPage===true;
 let last=null;
 for(let page=1;hasMore&&page<=100;page++){
  if(!cursor||cursor===last)throw Error('pagination_stalled');
  last=cursor;
  pages++;requests++;
  const r=await client.request(queryOne,{pk,after:cursor,first:10},{attempts:2});
  const x=r.json?.data?.chargingLocation;
  if(r.status!==200||!x?.evses)throw Error('page_failed:'+r.status);
  rows.push(...normalized(x));pi=x.evses.pageInfo||{};hasMore=pi.hasNextPage===true;cursor=pi.endCursor;
  await sleep(delay);
 }
 if(hasMore)throw Error('page_over_limit');
 const values={};
 for(const [evse,status] of rows){
  if(values[evse]&&values[evse]!==status)throw Error('duplicate_source_pk_status_collision');
  values[evse]=status;
 }
 return values;
}
async function one(pk){
 for(let attempt=1;attempt<=attempts;attempt++){
  requests++;
  const r=await client.request(queryOne,{pk,after:null,first:10},{attempts:1});
  const loc=r.json?.data?.chargingLocation;
  if(loc?.evses)return{ok:true,statuses:await fullPage(pk,loc)};
  if(attempt<attempts)await sleep(Math.max(1800,delay*3));
 }
 return{ok:false,error:'single_paged_unavailable'};
}
async function collect(i){
 if(!Number.isInteger(i)||i<0||i>=count)throw Error('Partition must be 0..15');
 await fs.mkdir(PARTS,{recursive:true});
 const expected=partitions[i],old=await fetchPart(i);
 const existing=old?.sourceFingerprint===cacheFingerprint&&old?.expectedLocations===expected.length?old:null;
 const entries=existing?.entries||{};
 const bad=existing?.errors||{};
 const started=new Date().toISOString();
 let successful=0,failed=0,batchRequests=0,aliasesFallback=0;
 const todo=expected.filter(pk=>!(pk in entries));
 console.log(JSON.stringify({event:'start',partition:i,sourceLocations:expected.length,previousGood:Object.keys(entries).length,previousErrors:Object.keys(bad).length,remaining:todo.length,runLimit:maxPerRun}));
 let cursor=0;
 async function checkpoint(){
  await fs.writeFile(filename(i),JSON.stringify({schemaVersion:1,partition:i,partitionCount:count,sourceFingerprint:cacheFingerprint,
   sourceCacheDate:manifest.generatedAt,startedAt:existing?.startedAt||started,updatedAt:new Date().toISOString(),
   expectedLocations:expected.length,entries,errors:bad},null,2)+'\n');
 }
 while(cursor<todo.length&&successful+failed<maxPerRun){
  const group=todo.slice(cursor,cursor+2);cursor+=group.length;
  // Only two aliases per request. Broken aliases retry individually, never discard valid neighbors.
  batchRequests++;requests++;
  const response=await client.request(queryBatch(group),{},{attempts:1});
  for(let n=0;n<group.length;n++){
   const pk=group[n];
   let outcome={ok:false,error:'batch_unavailable'};
   const loc=response.json?.data?.['s'+n];
   if(loc?.evses){
    try{outcome={ok:true,statuses:await fullPage(pk,loc)}}catch(e){outcome={ok:false,error:'paged_batch:'+String(e?.message||e)}}
   }
   if(!outcome.ok){aliasesFallback++;outcome=await one(pk)}
   if(outcome.ok){
    entries[pk]=outcome.statuses;delete bad[pk];successful++;
   }else{
    const prior=bad[pk]?.attempts||0;
    bad[pk]={attempts:prior+1,error:outcome.error,at:new Date().toISOString()};
    failed++;
   }
   if(successful+failed>=maxPerRun)break;
  }
  if((successful+failed)%40<2){await checkpoint();console.log(JSON.stringify({event:'progress',partition:i,newGood:successful,newFailed:failed,completed:Object.keys(entries).length,requests,aliasesFallback}));}
  if(failed>=failBudget){console.log(JSON.stringify({event:'error_budget',failed,partition:i}));break;}
  await sleep(delay);
 }
 await checkpoint();
 const remaining=expected.length-Object.keys(entries).length;
 const report={partition:i,sourceFingerprint:cacheFingerprint,at:new Date().toISOString(),startedAt:existing?.startedAt||started,
 expectedLocations:expected.length,verifiedLocations:Object.keys(entries).length,
 newSuccessful:successful,newFailed:failed,persistentErrors:Object.keys(bad).length,
 remaining,requests,batchRequests,pages,aliasesFallback,failureBudgetReached:failed>=failBudget,
 complete:remaining===0,output:filename(i)};
 await fs.mkdir('reports/electroverse',{recursive:true});
 await fs.writeFile('reports/electroverse/status-partition-latest.json',JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({event:'RESULT',...report}));
 // Intentional partial completion: checkpoint is useful and should be committed.
 if(!successful&&failed)process.exitCode=2;
}
async function aggregate(){
 const statuses={},locations={},issues=[],ts=[];
 for(let i=0;i<count;i++){
  const p=await fetchPart(i);
  if(!p||p.sourceFingerprint!==cacheFingerprint||p.expectedLocations!==partitions[i].length){
   issues.push({partition:i,reason:'missing_or_old_checkpoint'});continue;
  }
  const age=Date.now()-Date.parse(p.updatedAt);
  if(!Number.isFinite(age)||age>24*3600000)issues.push({partition:i,reason:'stale_partition',updatedAt:p.updatedAt});
  ts.push(p.updatedAt);
  for(const pk of partitions[i]){
   const found=p.entries?.[pk];
   if(!found){issues.push({partition:i,pk,reason:'unverified_location'});continue;}
   locations[pk]=found;
   for(const st of Object.values(found))statuses[st]=(statuses[st]||0)+1;
  }
 }
 const covered=Object.keys(locations).length,expected=all.length;
 const summary={schemaVersion:2,generatedAt:new Date().toISOString(),
 sourceFingerprint:cacheFingerprint,sourceCacheDate:manifest.generatedAt,
 expectedLocations:expected,completedLocations:covered,failedLocations:expected-covered,
 expectedCachedSourceEvses:sourceTotal,observedEvses:Object.values(statuses).reduce((a,b)=>a+b,0),
 allowedStatuses:['AVAILABLE','CHARGING'],statuses,
 partitionCount:count,partitionUpdatedAtMin:ts.sort()[0]||null,partitionUpdatedAtMax:ts.sort().at(-1)||null,
 completeness:{locations:covered===expected,allPartitionsFresh:issues.every(x=>x.reason!=='stale_partition'),missingCachedSourceEvses:sourceTotal-Object.values(locations).reduce((a,l)=>a+Object.keys(l).length,0)},
 issueCount:issues.length,examples:issues.slice(0,25)
 };
 await fs.mkdir('reports/electroverse',{recursive:true});
 await fs.writeFile('reports/electroverse/status-national-finalization.json',JSON.stringify(summary,null,2)+'\n');
 if(issues.length){
  console.log(JSON.stringify({event:'FINALIZATION_WAITING',summary}));return;
 }
 await fs.mkdir(OUTPUT,{recursive:true});
 const bytes=zlib.gzipSync(Buffer.from(JSON.stringify({schemaVersion:2,generatedAt:summary.generatedAt,locations})),{level:6});
 await fs.writeFile(OUTPUT+'/evses.json.gz',bytes);
 await fs.writeFile(OUTPUT+'/manifest.json',JSON.stringify({...summary,ledger:'evses.json.gz',compressedBytes:bytes.length},null,2)+'\n');
 console.log(JSON.stringify({event:'FINALIZATION_COMPLETE',summary,compressedBytes:bytes.length}));
}
if(mode==='collect')await collect(partNum);
else if(mode==='finalize')await aggregate();
else if(mode==='validate'){
 const m=JSON.parse(await fs.readFile(OUTPUT+'/manifest.json','utf8'));
 if(m.sourceFingerprint!==cacheFingerprint||m.completedLocations!==all.length||!m.completeness.locations||!m.completeness.allPartitionsFresh)
  throw Error('status national evidence invalid');
 console.log(JSON.stringify({valid:true,generatedAt:m.generatedAt,completedLocations:m.completedLocations,statuses:m.statuses}));
}else throw Error('Unknown mode '+mode);
