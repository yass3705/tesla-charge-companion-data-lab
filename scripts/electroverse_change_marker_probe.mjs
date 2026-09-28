import fs from 'node:fs/promises';
import {DirectElectroverseClient} from './lib/electroverse_direct_client.mjs';
const client=new DirectElectroverseClient({timeoutMs:45000});
const manifest=JSON.parse(await fs.readFile('data/electroverse/tariff_cache/manifest.json','utf8'));
const shardFiles=(await fs.readdir('data/electroverse/tariff_cache')).filter(x=>/^shard-.*\.json$/.test(x)).slice(0,8);
const pks=[];
for(const f of shardFiles){const j=JSON.parse(await fs.readFile('data/electroverse/tariff_cache/'+f,'utf8'));for(const s of Object.values(j.stations||{})){if(s.electroverseLocationPk){pks.push(String(s.electroverseLocationPk));if(pks.length>=3)break}}if(pks.length>=3)break}
if(!pks.length)throw new Error('no station ids');
const fields=['updatedAt','modifiedAt','lastUpdated','lastModified','version','revision','priceUpdatedAt','pricingUpdatedAt','tariffUpdatedAt'];
const scopes=[
 ['location',f=>`query Q{chargingLocation(pk:"${pks[0]}"){chargingLocationPk ${f}}}`],
 ['evse',f=>`query Q{chargingLocation(pk:"${pks[0]}"){chargingLocationPk evses{edges{node{pk ${f}}}}}}`],
 ['connector',f=>`query Q{chargingLocation(pk:"${pks[0]}"){chargingLocationPk evses{edges{node{pk connectors{edges{node{pk ${f}}}}}}}}}`]
];
const results=[];
for(const [scope,mk] of scopes)for(const field of fields){const r=await client.request(mk(field),{}, {attempts:1});results.push({scope,field,status:r.status,ms:r.ms,ok:r.status===200&&!r.json?.errors?.length,error:(r.json?.errors||[]).map(e=>e.message).join(' | ').slice(0,240)});}
const report={generatedAt:new Date().toISOString(),stationCount:pks.length,manifestStations:manifest.totalStations,results,accepted:results.filter(x=>x.ok).map(x=>({scope:x.scope,field:x.field,ms:x.ms}))};
await fs.mkdir('reports/electroverse',{recursive:true});await fs.writeFile('reports/electroverse/change-marker-probe.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({accepted:report.accepted,tested:results.length},null,2));
