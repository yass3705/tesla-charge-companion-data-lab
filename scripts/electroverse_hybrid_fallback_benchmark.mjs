import fs from 'node:fs/promises';
import {DirectElectroverseClient,SINGLE_LOCATION_QUERY} from './lib/electroverse_direct_client.mjs';
const client=new DirectElectroverseClient({timeoutMs:60000});
const files=(await fs.readdir('data/electroverse/tariff_cache')).filter(x=>/^shard-.*\.json$/.test(x)).sort();
const pks=[];
for(const f of files){const j=JSON.parse(await fs.readFile('data/electroverse/tariff_cache/'+f,'utf8'));for(const s of Object.values(j.stations||{})){if(s.electroverseLocationPk){pks.push(String(s.electroverseLocationPk));if(pks.length>=500)break}}if(pks.length>=500)break}
const PC='__typename formattedValue';
const F=`chargingLocationPk evses { edges { node { connectors { edges { node { isChargingFree priceComponents { ${PC} } complexPricingDetail { currency restrictions { restrictionTypes timeRestrictions { startTime endTime } durationRestrictions { minDurationSeconds maxDurationSeconds } dateRestrictions { startDate endDate } weekdayRestrictions { daysOfWeek } priceComponents { ${PC} } } } } } } } } }`;
const batchQ=g=>`query Q{ ${g.map((pk,i)=>`s${i}:chargingLocation(pk:${JSON.stringify(pk)}){${F}}`).join('\n')} }`;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const groups=[];for(let i=0;i<pks.length;i+=5)groups.push(pks.slice(i,i+5));
const batchRows=[], failedPks=[], t0=Date.now();
for(let i=0;i<groups.length;i+=2){
 const wave=groups.slice(i,i+2);
 const rs=await Promise.all(wave.map(async g=>{
   const r=await client.request(batchQ(g),{}, {attempts:1});
   const data=r.json?.data||{};
   const vals=Object.values(data).filter(Boolean).length;
   const ok=r.status===200&&!r.json?.errors?.length&&vals===g.length;
   if(!ok){for(let k=0;k<g.length;k++){if(!data['s'+k])failedPks.push(g[k])}}
   return {status:r.status,ms:r.ms,bytes:r.bytes,ok,returned:vals,expected:g.length,errors:(r.json?.errors||[]).map(e=>e.message)}
 }));
 batchRows.push(...rs); await sleep(750);
}
const uniqueFailed=[...new Set(failedPks)], singleRows=[];
for(const pk of uniqueFailed){
 const r=await client.request(SINGLE_LOCATION_QUERY,{pk},{attempts:2});
 singleRows.push({pk,status:r.status,ms:r.ms,bytes:r.bytes,ok:r.status===200&&!r.json?.errors?.length&&!!r.json?.data?.chargingLocation,errors:(r.json?.errors||[]).map(e=>e.message)});
 await sleep(750);
}
const elapsed=Date.now()-t0;
const firstReturned=batchRows.reduce((a,x)=>a+x.returned,0);
const fallbackOk=singleRows.filter(x=>x.ok).length;
const finalValidated=firstReturned+fallbackOk;
const allMs=[...batchRows,...singleRows].map(x=>x.ms).sort((a,b)=>a-b);
const report={generatedAt:new Date().toISOString(),stations:pks.length,batchRequests:batchRows.length,batchOkRequests:batchRows.filter(x=>x.ok).length,batchFailedRequests:batchRows.filter(x=>!x.ok).length,batchReturnedStations:firstReturned,fallbackCandidates:uniqueFailed.length,fallbackRequests:singleRows.length,fallbackOk,fallbackFailed:singleRows.length-fallbackOk,finalValidatedStations:finalValidated,finalCoveragePct:+(finalValidated/pks.length*100).toFixed(2),elapsedSeconds:+(elapsed/1000).toFixed(2),validatedStationsPerMinute:+(finalValidated/(elapsed/60000)).toFixed(2),p95Ms:allMs[Math.max(0,Math.ceil(allMs.length*.95)-1)],maxMs:allMs.at(-1),errorSamples:[...new Set([...batchRows,...singleRows].flatMap(x=>x.errors||[]))].slice(0,10)};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/hybrid-fallback-benchmark.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
