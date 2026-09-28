import fs from 'node:fs/promises';
import { performance } from 'node:perf_hooks';
import { DirectElectroverseClient, SINGLE_LOCATION_QUERY } from './lib/electroverse_direct_client.mjs';

const API_KEY=process.env.ELECTROVERSE_API_KEY;
if(!API_KEY) throw new Error('ELECTROVERSE_API_KEY required');
const INTERVALS=(process.env.BENCH_INTERVALS||'1500,1000,750,500').split(',').map(Number);
const SAMPLE=Number(process.env.BENCH_SAMPLE||40);
const mapping=JSON.parse(await fs.readFile('data/electroverse/irve_location_mapping.json','utf8'));
const pks=(mapping.mappings||[]).map(x=>String(x.electroverseLocationPk)).sort().slice(0,SAMPLE);
const client=new DirectElectroverseClient({apiKey:API_KEY});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const results=[];

for(const intervalMs of INTERVALS){
  let next=performance.now(), ok=0, http429=0, otherErrors=0, bytes=0;
  const latencies=[];
  const t0=performance.now();
  for(const pk of pks){
    const wait=Math.max(0,next-performance.now()); if(wait) await sleep(wait);
    next=Math.max(next,performance.now())+intervalMs;
    const q0=performance.now();
    const r=await client.request(SINGLE_LOCATION_QUERY,{pk},{attempts:1});
    latencies.push(performance.now()-q0);
    bytes+=r.bytes||0;
    if(r.status===429) http429++;
    else if(r.status>=200&&r.status<300&&r.json?.data?.chargingLocation) ok++;
    else otherErrors++;
  }
  const elapsedMs=performance.now()-t0;
  const sorted=[...latencies].sort((a,b)=>a-b);
  results.push({
    intervalMs,sample:pks.length,ok,http429,otherErrors,bytes,
    elapsedSeconds:Number((elapsedMs/1000).toFixed(2)),
    effectiveStationsPerMinute:Number((pks.length/(elapsedMs/60000)).toFixed(2)),
    latencyMs:{avg:Number((latencies.reduce((a,b)=>a+b,0)/latencies.length).toFixed(1)),
      p95:Number(sorted[Math.min(sorted.length-1,Math.floor(sorted.length*0.95))].toFixed(1))}
  });
  await sleep(5000);
}
const report={generatedAt:new Date().toISOString(),sampleSize:pks.length,results};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/rate-benchmark.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
