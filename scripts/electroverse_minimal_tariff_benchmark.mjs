import fs from 'node:fs/promises';
import {DirectElectroverseClient,SINGLE_LOCATION_QUERY} from './lib/electroverse_direct_client.mjs';
const client=new DirectElectroverseClient({timeoutMs:60000});
const files=(await fs.readdir('data/electroverse/tariff_cache')).filter(x=>/^shard-.*\.json$/.test(x)).sort();
const pks=[];
for(const f of files){const j=JSON.parse(await fs.readFile('data/electroverse/tariff_cache/'+f,'utf8'));for(const s of Object.values(j.stations||{})){if(s.electroverseLocationPk){pks.push(String(s.electroverseLocationPk));if(pks.length>=50)break}}if(pks.length>=50)break}
const PC='__typename formattedValue';
const MIN_FIELDS=`chargingLocationPk evses { edges { node { connectors { edges { node { isChargingFree priceComponents { ${PC} } complexPricingDetail { currency restrictions { restrictionTypes timeRestrictions { startTime endTime } durationRestrictions { minDurationSeconds maxDurationSeconds } dateRestrictions { startDate endDate } weekdayRestrictions { daysOfWeek } priceComponents { ${PC} } } } } } } } } }`;
const singleMin=()=>`query Q($pk:String!){chargingLocation(pk:$pk){${MIN_FIELDS}}}`;
const batchMin=pks=>`query Q{ ${pks.map((pk,i)=>`s${i}:chargingLocation(pk:${JSON.stringify(pk)}){${MIN_FIELDS}}`).join('\n')} }`;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function runSingles(kind,qf,count=20,pause=750){const rows=[];const t0=Date.now();for(const pk of pks.slice(0,count)){const {query,variables}=qf(pk);const r=await client.request(query,variables,{attempts:1});rows.push({status:r.status,ms:r.ms,bytes:r.bytes,ok:r.status===200&&!r.json?.errors?.length,errors:(r.json?.errors||[]).map(e=>e.message)});await sleep(pause)}return summarize(kind,rows,count,Date.now()-t0)}
async function runBatches(kind,qf,batchSize=5,total=50,concurrency=2,pause=750){const groups=[];for(let i=0;i<total;i+=batchSize)groups.push(pks.slice(i,i+batchSize));const rows=[];const t0=Date.now();for(let i=0;i<groups.length;i+=concurrency){const wave=groups.slice(i,i+concurrency);const rs=await Promise.all(wave.map(async g=>{const r=await client.request(qf(g),{}, {attempts:1});const vals=r.json?.data?Object.values(r.json.data).filter(Boolean).length:0;return {status:r.status,ms:r.ms,bytes:r.bytes,ok:r.status===200&&!r.json?.errors?.length&&vals===g.length,returned:vals,expected:g.length,errors:(r.json?.errors||[]).map(e=>e.message)}}));rows.push(...rs);await sleep(pause)}return summarize(kind,rows,total,Date.now()-t0,batchSize)}
function summarize(kind,rows,stations,elapsed,batchSize=1){const ok=rows.filter(x=>x.ok).length,sorted=rows.map(x=>x.ms).sort((a,b)=>a-b);const returned=rows.reduce((a,x)=>a+(x.returned??(x.ok?1:0)),0);return {kind,stations,requests:rows.length,okRequests:ok,failedRequests:rows.length-ok,returnedStations:returned,elapsedSeconds:+(elapsed/1000).toFixed(2),validatedStationsPerMinute:+(returned/(elapsed/60000)).toFixed(2),avgMs:+(rows.reduce((a,x)=>a+x.ms,0)/rows.length).toFixed(1),p95Ms:sorted[Math.max(0,Math.ceil(sorted.length*.95)-1)],avgBytes:+(rows.reduce((a,x)=>a+x.bytes,0)/rows.length).toFixed(1),batchSize,errorSamples:[...new Set(rows.flatMap(x=>x.errors||[]))].slice(0,3)}}
const results=[];
results.push(await runSingles('current-single',pk=>({query:SINGLE_LOCATION_QUERY,variables:{pk}}),20,750));
results.push(await runSingles('minimal-single',pk=>({query:singleMin(),variables:{pk}}),20,750));
results.push(await runBatches('minimal-batch5-concurrency2',batchMin,5,50,2,750));
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/minimal-tariff-benchmark.json',JSON.stringify({generatedAt:new Date().toISOString(),results},null,2)+'\n');
console.log(JSON.stringify(results,null,2));
