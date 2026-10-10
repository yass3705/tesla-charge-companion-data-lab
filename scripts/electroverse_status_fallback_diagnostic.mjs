import fs from 'node:fs/promises';
import {DirectElectroverseClient} from './lib/electroverse_direct_client.mjs';
const pks=['345808','345826','345938','345949','346626','346699','346701','346704','1991854','721397'];
const client=new DirectElectroverseClient({timeoutMs:15000});
const single='query StatusSingle($pk: String!){ chargingLocation(pk:$pk){ chargingLocationPk evses(first:5){edges{node{pk status}}pageInfo{hasNextPage endCursor}} } }';
const basic='query StatusBasic($pk:String!){chargingLocation(pk:$pk){chargingLocationPk evses{edges{node{pk status}}}}}';
const batched=(pk)=>'query { a:chargingLocation(pk:'+JSON.stringify(pk)+'){chargingLocationPk evses(first:5){edges{node{pk status}} pageInfo{hasNextPage endCursor}}}}';
const cases=[];
for(const pk of pks){
 const x={pk,tests:[]};
 for(const [kind,query,vars] of [['single-paged5',single,{pk}],['batch-one',batched(pk),{}]]){
 const res=await client.request(query,vars,{attempts:1});
 const loc=res.json?.data?.chargingLocation||res.json?.data?.a;
 x.tests.push({kind,status:res.status,ok:!!loc?.evses,n:(loc?.evses?.edges||[]).length,more:loc?.evses?.pageInfo?.hasNextPage||false,errorNames:(res.json?.errors||[]).map(e=>e.message).slice(0,3),durationMs:res.ms});
 await new Promise(r=>setTimeout(r,1250));
 }
 if(!x.tests.some(t=>t.ok)){
  const res=await client.request(basic,{pk},{attempts:1});
  x.tests.push({kind:'nonpaged-basic',status:res.status,ok:!!res.json?.data?.chargingLocation?.evses,n:res.json?.data?.chargingLocation?.evses?.edges?.length||0,errorNames:(res.json?.errors||[]).map(e=>e.message).slice(0,3)});
 }
 cases.push(x);
 console.log(JSON.stringify(x));
}
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/status-fallback-diagnostic-2026-10-10.json',JSON.stringify({generatedAt:new Date().toISOString(),cases},null,2)+'\n');
