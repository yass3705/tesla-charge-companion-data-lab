// Offline-only three-way benchmark. No imports from canonical collector or network clients.
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {performance} from 'node:perf_hooks';
import {fixtureTransport,validateFixture,runV1Model,runV2,diffInventories} from './model.mjs';
import {runJournal} from './journal_runner.mjs';
const fixture=validateFixture(JSON.parse(await fs.readFile(new URL('./fixtures/archived-24.json',import.meta.url),'utf8')));
const median=a=>[...a].sort((x,y)=>x-y)[Math.floor(a.length/2)];
const tmp=()=>fs.mkdtemp(path.join(os.tmpdir(),'electroverse-v2-'));
const passes=[];
for(let iteration=0;iteration<7;iteration++){
 const run=async(fn)=>{
  const dir=await tmp(),transport=fixtureTransport(fixture),before=process.cpuUsage(),t0=performance.now();
  try{
   const result=await fn(fixture,{outDir:dir,transport});
   const cpu=process.cpuUsage(before),files=await fs.readdir(dir),sizes=await Promise.all(files.map(async f=>(await fs.stat(path.join(dir,f))).size));
   return {result,metrics:{elapsedMs:performance.now()-t0,cpuMs:(cpu.user+cpu.system)/1000,
     requests:transport.metrics().requests,bytesWritten:sizes.reduce((a,b)=>a+b,0),files:files.length}};
  }finally{await fs.rm(dir,{force:true,recursive:true})}
 };
 const v1=await run(runV1Model),v2=await run(runV2),journal=await run(runJournal);
 const exact=Object.values(diffInventories(v2.result.records,journal.result.records)).every(x=>x.missing.length===0&&x.added.length===0);
 if(!exact)throw Error('V2 vs journal archive regression');
 passes.push({v1:v1.metrics,v2:v2.metrics,journal:journal.metrics,exact});
}
const normal={};
for(const kind of ['v1','v2','journal']){
 normal[kind]={};
 for(const metric of ['elapsedMs','cpuMs','requests','bytesWritten','files'])normal[kind][metric]=median(passes.map(x=>x[kind][metric]));
}
const interrupted=async(fn)=>{
 const dir=await tmp(),transport=fixtureTransport(fixture);
 try{
  try{await fn(fixture,{outDir:dir,transport,interruptAfter:2});throw Error('interrupt not raised')}
  catch(e){if(e.code!=='SIMULATED_INTERRUPT')throw e}
  const result=await fn(fixture,{outDir:dir,transport});
  return {requests:transport.metrics().requests,covered:result.metrics.covered,
    exactlyPreserved:Object.values(diffInventories(fixture.stations,result.records)).every(x=>!x.missing.length&&!x.added.length)};
 }finally{await fs.rm(dir,{force:true,recursive:true})}
};
const resume={v2:await interrupted(runV2),journal:await interrupted(runJournal)};
const report={kind:'OFFLINE_THREE_WAY_BENCHMARK_NOT_NETWORK',fixtureStations:fixture.stations.length,
 rounds:7,platform:process.platform,arch:process.arch,node:process.version,
 normal,resume,passes,caveat:'V1 is only a behavioral model. No HTTP latency, API quota, real rate limiting, network or Actions costs. Small archived fixture, not national.'};
console.log(JSON.stringify(report,null,2));
