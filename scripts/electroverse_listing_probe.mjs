import fs from 'node:fs/promises';
import {DirectElectroverseClient, CONNECTOR_FIELDS} from './lib/electroverse_direct_client.mjs';
const client=new DirectElectroverseClient({timeoutMs:60000});
const candidates=[
 {name:'chargingLocations',query:`query Probe($first:Int!){ chargingLocations(first:$first){ edges{ node{ chargingLocationPk evses{ edges{ node{ pk connectors{ edges{ node{ ${CONNECTOR_FIELDS} } } } } } } } } pageInfo{hasNextPage endCursor} } }`},
 {name:'chargingLocationConnection',query:`query Probe($first:Int!){ chargingLocationConnection(first:$first){ edges{ node{ chargingLocationPk evses{ edges{ node{ pk connectors{ edges{ node{ ${CONNECTOR_FIELDS} } } } } } } } pageInfo{hasNextPage endCursor} } }`}
];
const results=[];
for(const c of candidates){
 const r=await client.request(c.query,{first:5},{attempts:1});
 const data=r.json?.data||null;
 results.push({name:c.name,status:r.status,ms:r.ms,bytes:r.bytes,errors:(r.json?.errors||[]).map(e=>e.message),dataKeys:data?Object.keys(data):[],sample:data});
 if(r.status===200 && data && !(r.json?.errors?.length)) break;
}
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/listing-probe.json',JSON.stringify({generatedAt:new Date().toISOString(),results},null,2)+'\n');
console.log(JSON.stringify({results:results.map(x=>({name:x.name,status:x.status,ms:x.ms,bytes:x.bytes,errors:x.errors,dataKeys:x.dataKeys}))},null,2));
