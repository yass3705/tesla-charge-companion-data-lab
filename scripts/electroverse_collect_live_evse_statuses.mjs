/**
 * Full-France EVSE status evidence from official Electroverse GraphQL.
 * Stages snapshots without changing prices or mappings.
 */
import fs from 'node:fs/promises';
import zlib from 'node:zlib';
import {DirectElectroverseClient} from './lib/electroverse_direct_client.mjs';

const SOURCE='data/electroverse/tariff_cache';
const OUT='data/electroverse/live_statuses';
const REPORT='reports/electroverse/live-status-refresh-2026-10-10.json';
const limit=Number(process.env.ELECTROVERSE_SAMPLE_LIMIT||0);
const cfg={batchSize:Math.min(5,Math.max(1,Number(process.env.ELECTROVERSE_STATUS_BATCH_SIZE||4))),
 concurrency:Math.min(8,Math.max(1,Number(process.env.ELECTROVERSE_STATUS_CONCURRENCY||5))),
 pageSize:15,maxPages:120,attempts:2};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const manifest=JSON.parse(await fs.readFile(SOURCE+'/manifest.json','utf8'));
const cachePK=new Map();
for(const sh of manifest.shards||[]){
 const data=JSON.parse(await fs.readFile(SOURCE+'/'+sh.file,'utf8'));
 for(const [locationPk,row] of Object.entries(data.stations||{})){
  cachePK.set(String(locationPk),new Set((row.tariff?.evses||[]).map(e=>String(e.pk)).filter(Boolean)));
 }
}
let keys=[...cachePK.keys()].sort((a,b)=>a.localeCompare(b,'en',{numeric:true}));
if(limit>0)keys=keys.slice(0,limit);
const groups=[];for(let i=0;i<keys.length;i+=cfg.batchSize)groups.push(keys.slice(i,i+cfg.batchSize));
const entries={};const failures=[],statuses={},missingSource=[];
let requests=0,completed=0,paged=0;
const state={next:0};
const statusQuery=ids=>'query StatusBatch { '+ids.map((pk,i)=>'s'+i+':chargingLocation(pk:'+JSON.stringify(pk)+'){chargingLocationPk evses(first:'+cfg.pageSize+'){edges{node{pk status}} pageInfo{hasNextPage endCursor}}}').join(' ')+' }';
const pageQuery='query PageStatus($pk: String!,$after: String,$first: Int!){chargingLocation(pk:$pk){chargingLocationPk evses(first:$first,after:$after){edges{node{pk status}} pageInfo{hasNextPage endCursor}}}}';
const getRows=loc=>(loc?.evses?.edges||[]).map(x=>x?.node).filter(e=>e?.pk!=null).map(e=>({pk:String(e.pk),status:String(e.status||'UNKNOWN').toUpperCase()}));
async function fetchPages(pk,loc){
 const combined=getRows(loc);
 let after=loc?.evses?.pageInfo?.endCursor,hasNext=loc?.evses?.pageInfo?.hasNextPage===true,lastCursor='';
 let count=1;
 while(hasNext&&count<cfg.maxPages){
  if(!after||after===lastCursor)throw Error('page cursor stalled '+pk);
  lastCursor=after;count++;requests++;paged++;
  const r=await client.request(pageQuery,{pk,after,first:cfg.pageSize},{attempts:cfg.attempts});
  const more=r.json?.data?.chargingLocation;
  if(r.status!==200||!more?.evses)throw Error('page fetch failed '+pk+' http '+r.status);
  combined.push(...getRows(more));
  hasNext=more.evses.pageInfo?.hasNextPage===true;
  after=more.evses.pageInfo?.endCursor;
 }
 if(hasNext)throw Error('max pages reached '+pk);
 return combined;
}
const client=new DirectElectroverseClient({timeoutMs:25000});
async function saveLocation(pk,loc){
 const rows=await fetchPages(pk,loc);
 const unique=new Map();
 for(const row of rows){
  if(unique.has(row.pk)&&unique.get(row.pk)!==row.status)throw Error('same source PK has conflicting live statuses '+row.pk);
  unique.set(row.pk,row.status);
 }
 const item={};for(const [evsePk,status] of unique){item[evsePk]=status;statuses[status]=(statuses[status]||0)+1;}
 for(const expected of cachePK.get(pk)||[])if(!unique.has(expected))missingSource.push({locationPk:pk,evsePk:expected});
 entries[pk]=item;completed++;
}
async function work(){
 while(state.next<groups.length){
  const batch=groups[state.next++];if(!batch)break;
  requests++;
  const reply=await client.request(statusQuery(batch),{},{attempts:cfg.attempts});
  if(reply.status!==200||!reply.json?.data){
    failures.push({pks:batch,code:reply.status,reason:'batch HTTP/GraphQL failure'});
    continue;
  }
  for(const [i,pk] of batch.entries()){
   const loc=reply.json.data['s'+i];
   if(!loc?.evses){failures.push({pk,reason:'missing location in batch',errors:reply.json.errors?.map(e=>e.message)});continue;}
   try{await saveLocation(pk,loc)}catch(e){failures.push({pk,reason:String(e.message||e)})}
  }
  if(completed%2000<cfg.batchSize)console.log(JSON.stringify({completed,total:keys.length,requests,paged,failures:failures.length}));
  await sleep(150);
 }
}
await Promise.all(Array.from({length:cfg.concurrency},work));
const runAt=new Date().toISOString();
const sample=limit>0;
const totalSource=[...cachePK.values()].reduce((a,v)=>a+v.size,0);
const summary={
 schemaVersion:1,generatedAt:runAt,sample,sourceCacheAt:manifest.generatedAt,
 cacheLocations:cachePK.size,requestedLocations:keys.length,completedLocations:completed,failedLocations:failures.length,
 expectedCachedSourceEvses:totalSource,observedEvses:Object.values(statuses).reduce((a,b)=>a+b,0),
 missingCachedSourceEvses:missingSource.length,httpRequests:requests,paginationRequests:paged,
 statuses,allowedStatuses:['AVAILABLE','CHARGING'],
 policy:'Retain only AVAILABLE or CHARGING source EVSEs; exclude UNKNOWN, OUTOFORDER and other or missing statuses',
 failures:failures.slice(0,150),missingCachedExamples:missingSource.slice(0,150)
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(sample?'reports/electroverse/live-status-preflight-2026-10-10.json':REPORT,JSON.stringify(summary,null,2)+'\n');
if(failures.length>0||completed!==keys.length){
 console.log(JSON.stringify({ERROR:'incomplete census; ledger not published',summary}));
 process.exitCode=2;
}else if(sample){
 console.log(JSON.stringify({PREFLIGHT_OK:true,summary}));
}else{
 await fs.mkdir(OUT,{recursive:true});
 const payload=Buffer.from(JSON.stringify({schemaVersion:1,generatedAt:runAt,locations:entries}));
 const compressed=zlib.gzipSync(payload,{level:6});
 await fs.writeFile(OUT+'/evses.json.gz',compressed);
 await fs.writeFile(OUT+'/manifest.json',JSON.stringify({...summary,ledger:'evses.json.gz',compressedBytes:compressed.length,
   completeness:{locations:completed===cachePK.size,missingCachedSourceEvses:missingSource.length}},null,2)+'\n');
 console.log(JSON.stringify({SUCCESS:true,summary,compressedBytes:compressed.length}));
}
