// Read-only inspection of the publicly exposed Electra GraphQL contract.
// No authentication, no mutation, no speculative EVSE pricing inference.
import fs from 'node:fs/promises';
const OUT='reports/france/electra/graphql-evse-tariff-contract-latest.json';
const ENDPOINT='https://emsp.go-electra.com/graphql';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function request(query,variables={}){
  let err=null;
  for(let attempt=1;attempt<=3;attempt++){
    try{
      const r=await fetch(ENDPOINT,{method:'POST',headers:{'content-type':'application/json','accept':'application/json','user-agent':'TCC/1.0-public-readonly-contract-audit'},
       body:JSON.stringify({query,variables}),signal:AbortSignal.timeout(24000)});
      const b=await r.text();let data=null;try{data=JSON.parse(b)}catch{}
      if(r.ok)return {httpStatus:r.status,data:data?.data??null,errors:data?.errors?.map(e=>e.message)?.slice(0,8)??[],rawError:!data?b.slice(0,240):null};
      err={httpStatus:r.status,error:data?.errors?.map(e=>e.message)?.slice(0,6)??b.slice(0,250)};
    }catch(e){err={error:String(e)}}
    await sleep(attempt*1000);
  }return err;
}
const out={schemaVersion:1,generatedAt:new Date().toISOString(),endpoint:ENDPOINT,
 method:'GraphQL introspection plus public location sample',publicReadOnly:true};
const discovered=await request('query PublicTypes { __schema { types { name kind } } }');
out.schemaInspection={httpStatus:discovered.httpStatus,errors:discovered.errors||discovered.error||[],typesTotal:discovered.data?.__schema?.types?.length??null};
const all=discovered.data?.__schema?.types??[];
const names=all.filter(t=>/evse|tariff|connector|location|power|price|charge/i.test(t.name||'')&&!t.name.startsWith('__')).map(t=>t.name).slice(0,75);
out.relevantTypes=names;
if(names.length){
 const gqlType='name kind ofType { name kind ofType { name kind ofType { name kind } } }';
 const selection=names.slice(0,55).map((name,i)=>'t'+i+': __type(name:'+JSON.stringify(name)+'){name kind fields{name args{name type{'+gqlType+'}} type{'+gqlType+'}} inputFields{name type{'+gqlType+'}} enumValues{name}}').join(' ');
 const fields=await request('query TypeFields { '+selection+' }');
 out.fieldProbe={httpStatus:fields.httpStatus,errors:fields.errors||fields.error||[]};
 out.types=Object.fromEntries(Object.entries(fields.data||{}).filter(([k,v])=>v).map(([k,v])=>[v.name,v]));
}
const sampleId='81f45fef-3f7d-49c5-bf74-06327e73952c';
const one=await request('query LocationTariffSample($id:ID!){location(id:$id){id name maxPower cpo{name} evses{id evseId physicalReference connectors{id}} chargeTariffs{chargeTariffId currentPricePerKwh currency elements{restrictions{minPower maxPower minDuration maxDuration startTime endTime dayOfWeek} priceComponents{type price}}}}}',{id:sampleId});
out.sample={requestedLocationId:sampleId,httpStatus:one.httpStatus,errors:one.errors||one.error||[],station:one.data?.location??null};
const typeFields=Object.values(out.types||{});
const possibleLinks=[];
for(const t of typeFields){for(const f of t.fields||[]){if(/tariff|price|evse|connector|power|rate|product|group|offer|restriction/i.test(f.name))possibleLinks.push({type:t.name,field:f.name,shape:f.type});}}
out.possibleLinkFields=possibleLinks;
out.determination=out.schemaInspection.typesTotal==null?'introspection_not_available':possibleLinks.some(x=>/evse|connector/i.test(x.type)&&/tariff|price|rate|offer|product/i.test(x.field))?'candidate_explicit_link_in_public_schema':'no_evse_tariff_link_observed_in_examined_schema';
await fs.mkdir('reports/france/electra',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({result:OUT,determination:out.determination,typeCount:out.schemaInspection.typesTotal,interesting:possibleLinks.length,sampleErrors:out.sample.errors,errors:out.schemaInspection.errors}).slice(0,3500));
