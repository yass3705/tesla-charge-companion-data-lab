import fs from 'node:fs/promises';
import {performance} from 'node:perf_hooks';
import {DirectElectroverseClient,aliasBatchQuery} from './lib/electroverse_direct_client.mjs';
const mapping=JSON.parse(await fs.readFile('data/electroverse/irve_location_mapping.json','utf8'));
const all=(mapping.mappings||[]).map(x=>String(x.electroverseLocationPk)).sort();
const client=new DirectElectroverseClient({timeoutMs:60000});
const batchSize=5, stationsPerTest=150, wavePauseMs=750;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const results=[];
for(const concurrency of [2,3]){
 const pks=all.slice((concurrency-2)*stationsPerTest,(concurrency-1)*stationsPerTest);
 const groups=[]; for(let i=0;i<pks.length;i+=batchSize) groups.push(pks.slice(i,i+batchSize));
 let ok=0,failed=0,returned=0,http429=0; const lat=[],failures=[]; const t0=performance.now();
 for(let i=0;i<groups.length;i+=concurrency){
   const wave=groups.slice(i,i+concurrency);
   const rs=await Promise.all(wave.map(async(group)=>{
     const q0=performance.now(); const r=await client.request(aliasBatchQuery(group),{}, {attempts:1});
     return {group,r,ms:performance.now()-q0};
   }));
   for(const {group,r,ms} of rs){
     lat.push(ms); const n=Object.values(r.json?.data||{}).filter(Boolean).length;
     if(r.status===200&&n===group.length&&!(r.json?.errors?.length)){ok++;returned+=n;}
     else{failed++;if(r.status===429)http429++;failures.push({status:r.status,returned:n,size:group.length});}
   }
   if(i+concurrency<groups.length) await sleep(wavePauseMs);
 }
 const elapsed=performance.now()-t0, sorted=[...lat].sort((a,b)=>a-b);
 results.push({concurrency,batchSize,requestedStations:pks.length,batches:groups.length,okBatches:ok,failedBatches:failed,http429,returnedStations:returned,elapsedSeconds:+(elapsed/1000).toFixed(2),stationsPerMinute:+(returned/(elapsed/60000)).toFixed(2),latencyMs:{avg:+(lat.reduce((a,b)=>a+b,0)/lat.length).toFixed(1),p95:+sorted[Math.min(sorted.length-1,Math.floor(sorted.length*.95))].toFixed(1),max:+sorted.at(-1).toFixed(1)},failures});
 await sleep(5000);
}
const report={generatedAt:new Date().toISOString(),wavePauseMs,results};
await fs.mkdir('reports/electroverse',{recursive:true});await fs.writeFile('reports/electroverse/batch-concurrency-benchmark.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
