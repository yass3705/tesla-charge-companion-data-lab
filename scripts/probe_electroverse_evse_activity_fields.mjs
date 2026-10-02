import fs from 'node:fs/promises';
import {DirectElectroverseClient} from './lib/electroverse_direct_client.mjs';
const OUT='reports/electroverse/b-evse-activity-field-probe.json';
const client=new DirectElectroverseClient({timeoutMs:60000});
const pk='378568';
const extras=['isActive','lastSessionStartedAt','supportsInAppCharging','capabilities'];
const results=[];
for(const extra of extras){
 const q=`query($pk:String!){chargingLocation(pk:$pk){evses{edges{node{pk physicalReference status ${extra}}}}}}`;
 const r=await client.request(q,{pk},{attempts:1});
 results.push({field:extra,httpStatus:r.status,errors:(r.json?.errors||[]).map(e=>e.message),sample:r.json?.data?.chargingLocation?.evses?.edges?.[0]?.node??null});
}
const out={generatedAt:new Date().toISOString(),pk,results};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
