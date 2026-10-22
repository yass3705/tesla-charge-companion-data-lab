import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {validateFixture,fixtureTransport,runV1Model,runV2,diffInventories,inventory} from './model.mjs';
const config=JSON.parse(await fs.readFile(new URL('./config.json',import.meta.url),'utf8'));
if(config.schemaVersion!==1||config.offline!==true||config.maxNetworkRequests!==0||config.batchSize>5)throw Error('unsafe experimental configuration');
const fixture=validateFixture(JSON.parse(await fs.readFile(new URL('./fixtures/archived-24.json',import.meta.url),'utf8')));
const temp=()=>fs.mkdtemp(path.join(os.tmpdir(),'electroverse-v2-'));
const median=values=>[...values].sort((a,b)=>a-b)[Math.floor(values.length/2)];
const runs=[];
for(let n=0;n<5;n++){
  const v1=await runV1Model(fixture,{outDir:await temp(),transport:fixtureTransport(fixture),batchSize:config.batchSize});
  const v2=await runV2(fixture,{outDir:await temp(),transport:fixtureTransport(fixture),batchSize:config.batchSize});
  runs.push({v1:v1.metrics,v2:v2.metrics});
}
const summary={};
for(const mode of ['v1','v2'])summary[mode]={
  requests:median(runs.map(r=>r[mode].requests)),responseBytes:median(runs.map(r=>r[mode].responseBytes)),
  elapsedMsMedian:median(runs.map(r=>r[mode].elapsedMs)),cpuMsMedian:median(runs.map(r=>r[mode].cpuMs)),
  rssBytesObservedMax:Math.max(...runs.map(r=>r[mode].rssBytes)),
  writes:median(runs.map(r=>r[mode].writes)),covered:median(runs.map(r=>r[mode].covered))};
const interruptedTransport=fixtureTransport(fixture),v2Dir=await temp();
try{await runV2(fixture,{outDir:v2Dir,transport:interruptedTransport,interruptAfter:2});}catch(e){if(e.code!=='SIMULATED_INTERRUPT')throw e;}
const v2Resume=await runV2(fixture,{outDir:v2Dir,transport:interruptedTransport});
const v1First=fixtureTransport(fixture);
try{await runV1Model(fixture,{outDir:await temp(),transport:v1First,interruptAfter:2});}catch(e){if(e.code!=='SIMULATED_INTERRUPT')throw e;}
const v1RestartTransport=fixtureTransport(fixture);
const v1Restart=await runV1Model(fixture,{outDir:await temp(),transport:v1RestartTransport});
const difference=diffInventories(v1Restart.records,v2Resume.records);
const exact=Object.values(difference).every(row=>!row.missing.length&&!row.added.length);
const counts=Object.fromEntries(Object.entries(inventory(fixture.stations)).map(([key,values])=>[key,values.length]));
const benchmark={kind:'OFFLINE_SIMULATION_NOT_NETWORK',sourceSha:fixture.source.gitSha,fixturePath:'experiments/electroverse-v2/fixtures/archived-24.json',
  commands:['node --test experiments/electroverse-v2/test/model.test.mjs','node experiments/electroverse-v2/benchmark.mjs'],
  hardware:{platform:process.platform,arch:process.arch,node:process.version,cpus:os.cpus().length},
  sample:counts,iterations:5,normal:summary,runs,
  interruption:{afterBatches:2,v1TotalRequests:v1First.metrics().requests+v1Restart.metrics.requests,
    v2TotalRequests:interruptedTransport.metrics().requests,v1Covered:v1Restart.metrics.covered,v2Covered:v2Resume.metrics.covered},
  caveat:'V1 is a local behavioral model, not the canonical script execution. In-process memory maxima are not independent peak RSS measurements. No API latency, throttling or Actions cost was measured.'};
const regression={kind:'ARCHIVED_SAMPLE_EXACT_MULTISET',sourceSha:fixture.source.gitSha,counts,difference,exact,
  tariffHashesEqual:v1Restart.records.map(x=>x.tariffHash).sort().join('|')===v2Resume.records.map(x=>x.tariffHash).sort().join('|')};
await fs.mkdir('reports/electroverse-v2',{recursive:true});
await fs.writeFile('reports/electroverse-v2/benchmark.json',JSON.stringify(benchmark,null,2)+'\n');
await fs.writeFile('reports/electroverse-v2/regression.json',JSON.stringify(regression,null,2)+'\n');
console.log(JSON.stringify({normal:summary,interruption:benchmark.interruption,exact,counts},null,2));
