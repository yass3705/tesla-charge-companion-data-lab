import fs from 'node:fs/promises';
import {performance} from 'node:perf_hooks';
import {DirectElectroverseClient,aliasBatchQuery} from './lib/electroverse_direct_client.mjs';
const apiKey=process.env.ELECTROVERSE_API_KEY;if(!apiKey)throw new Error('ELECTROVERSE_API_KEY required');
const batchSize=Number(process.env.BATCH_SIZE||5), stations=Number(process.env.BENCH_STATIONS||250), pauseMs=Number(process.env.BATCH_PAUSE_MS||250);
const mapping=JSON.parse(await fs.readFile('data/electroverse/irve_location_mapping.json','utf8'));
const pks=(mapping.mappings||[]).map(x=>String(x.electroverseLocationPk)).sort().slice(0,stations);
const client=new DirectElectroverseClient({apiKey,timeoutMs:60000});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let okBatches=0,failedBatches=0,returnedStations=0,http429=0,totalBytes=0; const latencies=[], failures=[];
const t0=performance.now();
for(let i=0;i<pks.length;i+=batchSize){
 const group=pks.slice(i,i+batchSize), q0=performance.now();
 const r=await client.request(aliasBatchQuery(group),{}, {attempts:1});
 const ms=performance.now()-q0;latencies.push(ms);totalBytes+=r.bytes||0;
 const returned=Object.values(r.json?.data||{}).filter(Boolean).length;
 if(r.status===200 && returned===group.length && !(r.json?.errors?.length)){okBatches++;returnedStations+=returned;}
 else {failedBatches++;if(r.status===429)http429++;failures.push({offset:i,size:group.length,status:r.status,returned,errors:(r.json?.errors||[]).slice(0,2).map(e=>e.message)});}
 if(i+batchSize<pks.length && pauseMs)await sleep(pauseMs);
}
const elapsedMs=performance.now()-t0, sorted=[...latencies].sort((a,b)=>a-b);
const report={generatedAt:new Date().toISOString(),batchSize,requestedStations:pks.length,batches:Math.ceil(pks.length/batchSize),okBatches,failedBatches,http429,returnedStations,totalBytes,elapsedSeconds:+(elapsedMs/1000).toFixed(2),stationsPerMinute:+(returnedStations/(elapsedMs/60000)).toFixed(2),latencyMs:{avg:+(latencies.reduce((a,b)=>a+b,0)/latencies.length).toFixed(1),p50:+sorted[Math.floor(sorted.length*.5)].toFixed(1),p95:+sorted[Math.min(sorted.length-1,Math.floor(sorted.length*.95))].toFixed(1),max:+sorted.at(-1).toFixed(1)},failures};
await fs.mkdir('reports/electroverse',{recursive:true});await fs.writeFile('reports/electroverse/batch-sustained-benchmark.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
