import fs from 'node:fs/promises';
import {DirectElectroverseClient} from './lib/electroverse_direct_client.mjs';
const OUT='reports/electroverse/b-evse-schema-probe.json';
const client=new DirectElectroverseClient({timeoutMs:60000});
const locPk='378568';
const q1=`query($pk:String!){chargingLocation(pk:$pk){evses(first:1){edges{node{__typename pk physicalReference status}}}}}`;
const r1=await client.request(q1,{pk:locPk},{attempts:2});
const typename=r1.json?.data?.chargingLocation?.evses?.edges?.[0]?.node?.__typename||null;
let r2=null;
if(typename){
 const q2=`query($name:String!){__type(name:$name){name kind fields{name description type{kind name ofType{kind name ofType{kind name}}}}}}`;
 r2=await client.request(q2,{name:typename},{attempts:2});
}
const out={
 generatedAt:new Date().toISOString(),locationPk:locPk,typename,
 sampleStatus:r1.status,sampleErrors:(r1.json?.errors||[]).map(e=>e.message),
 introspectionStatus:r2?.status??null,introspectionErrors:(r2?.json?.errors||[]).map(e=>e.message)??[],
 type:r2?.json?.data?.__type??null
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({typename,status:r2?.status??null,errors:out.introspectionErrors,fieldNames:(out.type?.fields||[]).map(x=>x.name)},null,2));
