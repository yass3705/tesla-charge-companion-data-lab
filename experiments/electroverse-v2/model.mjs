// Offline-only research model. No imports from the canonical collector and no HTTP client.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import {performance} from 'node:perf_hooks';

export const stable=value=>Array.isArray(value)?value.map(stable):value&&typeof value==='object'?
  Object.fromEntries(Object.keys(value).sort().map(key=>[key,stable(value[key])])):value;
export const sha=value=>crypto.createHash('sha256').update(JSON.stringify(stable(value))).digest('hex');
export const pkOf=record=>String(record?.electroverseLocationPk??'');
export function validateRecord(record){
  const pk=pkOf(record),tariff=record?.tariff;
  if(!pk||!tariff||String(tariff.chargingLocationPk)!==pk||!Array.isArray(tariff.evses))throw Error('invalid station schema '+pk);
  if(record.tariffHash!==sha(tariff))throw Error('tariff SHA mismatch '+pk);
  const evses=new Set(),connectors=new Set();
  for(const evse of tariff.evses){
    if(evse.pk==null||evses.has(String(evse.pk))||!Array.isArray(evse.connectors))throw Error('invalid EVSE '+pk);
    evses.add(String(evse.pk));
    for(const connector of evse.connectors){
      if(connector.pk==null||connectors.has(String(connector.pk))||!Array.isArray(connector.priceComponents))throw Error('invalid connector '+pk);
      connectors.add(String(connector.pk));
      if(connector.complexPricingDetail!=null&&typeof connector.complexPricingDetail!=='object')throw Error('invalid restrictions '+pk);
    }
  }
  return record;
}
export function validateFixture(fixture){
  if(fixture?.fixtureVersion!==1||!Array.isArray(fixture.stations))throw Error('invalid fixture');
  const ids=new Set();
  for(const record of fixture.stations){validateRecord(record);const pk=pkOf(record);if(ids.has(pk))throw Error('duplicate station '+pk);ids.add(pk);}
  return fixture;
}
export function inventory(records){
  const stationIds=[],evseIds=[],connectors=[],mapping=[],components=[];
  for(const record of records){stationIds.push(pkOf(record));mapping.push([pkOf(record),record.irveStationId,record.irvePdcIds,record.matchConfidence]);
    for(const evse of record.tariff.evses){evseIds.push(String(evse.pk));for(const c of evse.connectors){
      connectors.push([pkOf(record),String(evse.pk),String(c.pk),c.standard,c.kilowatts,c.speed,c.isChargingFree]);
      components.push([String(c.pk),c.priceComponents,c.complexPricingDetail]);
    }}
  }
  const sort=a=>a.map(stable).map(x=>JSON.stringify(x)).sort();
  return{stations:sort(stationIds),evses:sort(evseIds),connectors:sort(connectors),mapping:sort(mapping),components:sort(components)};
}
export function diffInventories(a,b){
  const left=inventory(a),right=inventory(b),out={};
  for(const key of Object.keys(left)){
    const counts=new Map();for(const value of left[key])counts.set(value,(counts.get(value)||0)+1);
    for(const value of right[key])counts.set(value,(counts.get(value)||0)-1);
    out[key]={old:left[key].length,new:right[key].length,missing:[],added:[]};
    for(const [value,count] of counts){if(count>0)out[key].missing.push({value,count});if(count<0)out[key].added.push({value,count:-count});}
  }
  return out;
}
function safeDir(outDir){
  const resolved=path.resolve(outDir),temp=path.resolve(os.tmpdir())+path.sep;
  if(!resolved.startsWith(temp)||!path.basename(resolved).startsWith('electroverse-v2-'))throw Error('output must be /tmp/electroverse-v2-*');
  return resolved;
}
async function readJson(file,fallback){try{return JSON.parse(await fs.readFile(file,'utf8'));}catch(error){if(error.code==='ENOENT')return fallback;throw Error('corrupt JSON '+file);}}
async function atomic(file,value){const tmp=file+'.tmp-'+process.pid+'-'+crypto.randomBytes(4).toString('hex');await fs.writeFile(tmp,JSON.stringify(value));await fs.rename(tmp,file);}
export function fixtureTransport(fixture,{faults={}}={}){
  const source=new Map(fixture.stations.map(r=>[pkOf(r),r]));let calls=0,bytes=0;
  const hits=new Map();
  async function request(keys,kind){
    calls++;const records={};let status=200;
    for(const pk of keys){const key=kind+':'+pk,n=(hits.get(key)||0)+1;hits.set(key,n);const fault=faults[pk]?.[kind]?.[n-1];
      if(typeof fault==='number'){status=fault;continue;}
      if(fault==='timeout'){status=0;continue;}
      if(fault==='partial')continue;
      if(fault==='missing'){records[pk]=null;continue;}
      if(fault==='pagination_incomplete'||fault==='cursor_stuck'){records[pk]={...source.get(pk),complete:false,reason:fault};continue;}
      records[pk]=source.get(pk)||null;
    }
    bytes+=Buffer.byteLength(JSON.stringify(records));return{status,records};
  }
  return{request,metrics:()=>({requests:calls,responseBytes:bytes})};
}
export async function runV2(fixture,{outDir,transport=fixtureTransport(fixture),batchSize=5,interruptAfter=null}={}){
  validateFixture(fixture);const root=safeDir(outDir);await fs.mkdir(root,{recursive:true});
  if(!Number.isInteger(batchSize)||batchSize<1||batchSize>5)throw Error('batch size exceeds archived validated limit 5');
  const sourceHash=sha(fixture.stations.map(r=>[pkOf(r),r.tariffHash]));
  const stateFile=path.join(root,'last-good.json'),checkpointFile=path.join(root,'checkpoint.json');
  const state=await readJson(stateFile,{version:1,stations:{}}),checkpoint=await readJson(checkpointFile,{version:1,sourceHash,completed:[]});
  if(state.version!==1||typeof state.stations!=='object'||checkpoint.version!==1||!Array.isArray(checkpoint.completed))throw Error('invalid state schema');
  for(const [pk,record] of Object.entries(state.stations)){validateRecord(record);if(pkOf(record)!==pk)throw Error('state key mismatch');}
  if(checkpoint.sourceHash!==sourceHash)checkpoint.completed=[];
  for(const pk of checkpoint.completed)if(!state.stations[pk])throw Error('checkpoint references missing verified station '+pk);
  const complete=new Set(checkpoint.completed),pending=fixture.stations.map(pkOf).filter(pk=>!complete.has(pk));
  const started=performance.now(),cpuStart=process.cpuUsage(),errors=[],metrics={batches:0,singleFallbacks:0,writes:0,unchanged:0,changed:0,new:0};
  let dirty=false;
  async function accept(pk,record){
    if(!record||record.complete===false){errors.push({pk,reason:record?.reason||'missing_or_partial'});return false;}
    try{validateRecord(record);}catch(error){errors.push({pk,reason:error.message});return false;}
    const old=state.stations[pk];if(!old)metrics.new++;else if(old.tariffHash===record.tariffHash)metrics.unchanged++;else metrics.changed++;
    if(!old||old.tariffHash!==record.tariffHash){state.stations[pk]=record;dirty=true;}
    complete.add(pk);return true;
  }
  for(let i=0;i<pending.length;i+=batchSize){
    const group=pending.slice(i,i+batchSize);metrics.batches++;
    let response=await transport.request(group,'batch');
    // Offline backoff is represented as retry count; no wall-clock sleep or HTTP.
    if([0,429,500,502,503,504].includes(response.status))response=await transport.request(group,'batch');
    if(response.status!==200){
      for(const pk of group)errors.push({pk,reason:'batch_'+response.status});
      await atomic(checkpointFile,{version:1,sourceHash,completed:[...complete].sort()});metrics.writes++;
      if(interruptAfter!=null&&metrics.batches===interruptAfter)throw Object.assign(Error('simulated interruption'),{code:'SIMULATED_INTERRUPT'});
      continue;
    }
    const unresolved=[];
    for(const pk of group){const record=response.status===200?response.records?.[pk]:null;
      if(!record||record.complete===false||!(await accept(pk,record)))unresolved.push(pk);
    }
    for(const pk of unresolved){metrics.singleFallbacks++;const single=await transport.request([pk],'single');
      if(single.status===200&&single.records?.[pk])await accept(pk,single.records[pk]);
      else errors.push({pk,reason:'single_'+single.status});
    }
    if(dirty){await atomic(stateFile,state);metrics.writes++;dirty=false;}
    await atomic(checkpointFile,{version:1,sourceHash,completed:[...complete].sort()});metrics.writes++;
    if(interruptAfter!=null&&metrics.batches===interruptAfter)throw Object.assign(Error('simulated interruption'),{code:'SIMULATED_INTERRUPT'});
  }
  const cpu=process.cpuUsage(cpuStart),elapsedMs=performance.now()-started;
  return{records:Object.values(state.stations),errors,metrics:{...metrics,...transport.metrics(),elapsedMs:Number(elapsedMs.toFixed(3)),cpuMs:Number(((cpu.user+cpu.system)/1000).toFixed(3)),rssBytes:process.memoryUsage().rss,covered:complete.size,expected:fixture.stations.length}};
}
export async function runV1Model(fixture,{outDir,transport=fixtureTransport(fixture),interruptAfter=null}={}){
  // Behavioral offline model of hybrid_refresh's happy path. This does not run
  // the canonical collector or claim to reproduce its network/API timings.
  validateFixture(fixture);const root=safeDir(outDir);await fs.mkdir(root,{recursive:true});
  const started=performance.now(),cpuStart=process.cpuUsage(),result={},errors=[];
  let batches=0,fallbacks=0;
  const ids=fixture.stations.map(pkOf);
  for(let i=0;i<ids.length;i+=5){
    const group=ids.slice(i,i+5),batch=await transport.request(group,'batch');batches++;
    for(const pk of group){let record=batch.status===200?batch.records?.[pk]:null;
      if(!record){fallbacks++;const single=await transport.request([pk],'single');record=single.status===200?single.records?.[pk]:null;}
      if(record){validateRecord(record);result[pk]=record;}else errors.push({pk,reason:'unresolved'});
    }
    if(interruptAfter!=null&&batches===interruptAfter)throw Object.assign(Error('simulated V1 interruption'),{code:'SIMULATED_INTERRUPT'});
  }
  await atomic(path.join(root,'v1-cache-model.json'),{version:1,stations:result});
  const cpu=process.cpuUsage(cpuStart);
  return{records:Object.values(result),errors,metrics:{...transport.metrics(),batches,singleFallbacks:fallbacks,writes:1,
    elapsedMs:Number((performance.now()-started).toFixed(3)),cpuMs:Number(((cpu.user+cpu.system)/1000).toFixed(3)),rssBytes:process.memoryUsage().rss,
    covered:Object.keys(result).length,expected:ids.length}};
}
