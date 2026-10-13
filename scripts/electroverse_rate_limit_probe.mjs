// Single bounded, read-only probe. Stops on the first failure; never retries a rate error.
import fs from 'node:fs/promises';
import {performance} from 'node:perf_hooks';
import {DirectElectroverseClient,SINGLE_LOCATION_QUERY} from './lib/electroverse_direct_client.mjs';

const MAX_REQUESTS=60, INTERVAL_MS=1000;
const output=process.env.PILOT_RATE_REPORT||'reports/emsp-pilots/electroverse-rate-limit.json';
const mapping=JSON.parse(await fs.readFile('data/electroverse/irve_location_mapping.json','utf8'));
const ids=[...new Set((mapping.mappings||[]).map(x=>String(x.electroverseLocationPk||'')).filter(Boolean))].sort();
if(ids.length<MAX_REQUESTS)throw Error('insufficient distinct known location IDs');
const chosen=Array.from({length:MAX_REQUESTS},(_,i)=>ids[Math.floor((i+0.5)*ids.length/MAX_REQUESTS)]);
const client=new DirectElectroverseClient({timeoutMs:20000});
const rows=[],started=performance.now();
for(let i=0;i<chosen.length;i++){
  const wait=i*INTERVAL_MS-(performance.now()-started);
  if(wait>0)await new Promise(resolve=>setTimeout(resolve,wait));
  const response=await client.request(SINGLE_LOCATION_QUERY,{pk:chosen[i]},{attempts:1});
  const graphqlErrors=(response.json?.errors||[]).map(x=>String(x.message||'').slice(0,160));
  const ok=response.status===200&&!graphqlErrors.length&&Boolean(response.json?.data?.chargingLocation);
  rows.push({ordinal:i+1,status:response.status,ok,ms:response.ms,bytes:response.bytes,
    retryAfter:response.responseHeaders?.retryAfter||null,
    rateLimitLimit:response.responseHeaders?.rateLimitLimit||null,
    rateLimitRemaining:response.responseHeaders?.rateLimitRemaining||null,
    rateLimitReset:response.responseHeaders?.rateLimitReset||null,
    graphqlErrors});
  if(!ok)break;
}
const successes=rows.filter(x=>x.ok).length,firstFailure=rows.find(x=>!x.ok)||null;
const report={generatedAt:new Date().toISOString(),scope:'distinct known FR locations, metadata-only bounded request-rate probe',
  maxRequests:MAX_REQUESTS,intervalMs:INTERVAL_MS,attemptsPerRequest:1,
  elapsedSeconds:Number(((performance.now()-started)/1000).toFixed(2)),requests:rows.length,successes,
  firstFailure,observedLimit:firstFailure?.status===429?'HTTP 429 at ordinal '+firstFailure.ordinal:
    firstFailure?'first failure is not an explicit rate limit; no numerical API limit proven':
      'no limit observed through '+rows.length+' requests at this interval; lower bound only',
  rows};
await fs.mkdir('reports/emsp-pilots',{recursive:true});
await fs.writeFile(output,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({requests:report.requests,successes,firstFailure,observedLimit:report.observedLimit}));
if(firstFailure)process.exitCode=2;
