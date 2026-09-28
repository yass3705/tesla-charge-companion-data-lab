import fs from 'node:fs/promises';
import {performance} from 'node:perf_hooks';
import {DirectElectroverseClient,aliasBatchQuery} from './lib/electroverse_direct_client.mjs';
const API_KEY=process.env.ELECTROVERSE_API_KEY;if(!API_KEY)throw new Error('ELECTROVERSE_API_KEY required');
const sizes=(process.env.BATCH_SIZES||'2,5,10,20,40').split(',').map(Number);
const mapping=JSON.parse(await fs.readFile('data/electroverse/irve_location_mapping.json','utf8'));
const all=(mapping.mappings||[]).map(x=>String(x.electroverseLocationPk)).sort();
const client=new DirectElectroverseClient({apiKey:API_KEY,timeoutMs:60000});
const results=[];
for(const size of sizes){
 const pks=all.slice(0,size), q=aliasBatchQuery(pks), t0=performance.now();
 const r=await client.request(q,{}, {attempts:1});
 const data=r.json?.data||{};
 const returned=Object.values(data).filter(Boolean).length;
 const errors=r.json?.errors||[];
 results.push({batchSize:size,status:r.status,elapsedMs:Math.round(performance.now()-t0),bytes:r.bytes||0,returned,errorCount:errors.length,errors:errors.slice(0,3).map(e=>e.message),rateLimit:r.responseHeaders||null});
 await new Promise(x=>setTimeout(x,3000));
}
const report={generatedAt:new Date().toISOString(),results};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/batch-benchmark.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
