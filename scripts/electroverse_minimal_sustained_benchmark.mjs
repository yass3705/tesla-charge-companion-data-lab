import fs from 'node:fs/promises';
import {DirectElectroverseClient} from './lib/electroverse_direct_client.mjs';
const client=new DirectElectroverseClient({timeoutMs:60000});
const files=(await fs.readdir('data/electroverse/tariff_cache')).filter(x=>/^shard-.*\.json$/.test(x)).sort();
const pks=[];
for(const f of files){const j=JSON.parse(await fs.readFile('data/electroverse/tariff_cache/'+f,'utf8'));for(const s of Object.values(j.stations||{})){if(s.electroverseLocationPk){pks.push(String(s.electroverseLocationPk));if(pks.length>=500)break}}if(pks.length>=500)break}
const PC='__typename formattedValue';
const F=`chargingLocationPk evses { edges { node { connectors { edges { node { isChargingFree priceComponents { ${PC} } complexPricingDetail { currency restrictions { restrictionTypes timeRestrictions { startTime endTime } durationRestrictions { minDurationSeconds maxDurationSeconds } dateRestrictions { startDate endDate } weekdayRestrictions { daysOfWeek } priceComponents { ${PC} } } } } } } } } }`;
const q=g=>`query Q{ ${g.map((pk,i)=>`s${i}:chargingLocation(pk:${JSON.stringify(pk)}){${F}}`).join('\n')} }`;
const groups=[];for(let i=0;i<pks.length;i+=5)groups.push(pks.slice(i,i+5));
const sleep=ms=>new Promise(r=>setTimeout(r,ms)), rows=[], t0=Date.now();
for(let i=0;i<groups.length;i+=2){
  const wave=groups.slice(i,i+2);
  const rs=await Promise.all(wave.map(async g=>{const r=await client.request(q(g),{}, {attempts:1});const vals=r.json?.data?Object.values(r.json.data).filter(Boolean).length:0;return {status:r.status,ms:r.ms,bytes:r.bytes,ok:r.status===200&&!r.json?.errors?.length&&vals===g.length,returned:vals,expected:g.length,errors:(r.json?.errors||[]).map(e=>e.message)}}));
  rows.push(...rs);
  await sleep(750);
}
const elapsed=Date.now()-t0, sorted=rows.map(x=>x.ms).sort((a,b)=>a-b), returned=rows.reduce((a,x)=>a+x.returned,0);
const report={generatedAt:new Date().toISOString(),stations:pks.length,requests:rows.length,okRequests:rows.filter(x=>x.ok).length,failedRequests:rows.filter(x=>!x.ok).length,returnedStations:returned,elapsedSeconds:+(elapsed/1000).toFixed(2),validatedStationsPerMinute:+(returned/(elapsed/60000)).toFixed(2),avgMs:+(rows.reduce((a,x)=>a+x.ms,0)/rows.length).toFixed(1),p50Ms:sorted[Math.max(0,Math.ceil(sorted.length*.50)-1)],p95Ms:sorted[Math.max(0,Math.ceil(sorted.length*.95)-1)],maxMs:sorted.at(-1),avgBytes:+(rows.reduce((a,x)=>a+x.bytes,0)/rows.length).toFixed(1),errorSamples:[...new Set(rows.flatMap(x=>x.errors||[]))].slice(0,10)};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/minimal-sustained-benchmark.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
