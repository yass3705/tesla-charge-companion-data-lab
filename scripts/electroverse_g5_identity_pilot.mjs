import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {DirectElectroverseClient} from './lib/electroverse_direct_client.mjs';

const EXPECTED=[{"expectedOperatorId":"21133","physicalReference":"JCFV1","nationalEvseId":"FRFR1EJCFV1","locationPk":"652329","nationalStationId":"FRFR1P8289342808958091411"},{"expectedOperatorId":"64694","physicalReference":"NBKJ1","nationalEvseId":"FRFR1ENBKJ1","locationPk":"943602","nationalStationId":"FRFR1P3954308727827316770"},{"expectedOperatorId":"727","physicalReference":"WAYZ1","nationalEvseId":"FRFR1EWAYZ1","locationPk":"617076","nationalStationId":"FRFR1P2365459661242012003"},{"expectedOperatorId":"3326","physicalReference":"MYKC1","nationalEvseId":"FRFR1EMYKC1","locationPk":"581442","nationalStationId":"FRFR1PVFKUJC"},{"expectedOperatorId":"3527","physicalReference":"RRHD1","nationalEvseId":"FRFR1ERRHD1","locationPk":"1004083","nationalStationId":"FRFR1P5316535057035692011"},{"expectedOperatorId":"3468","physicalReference":"ATEN1","nationalEvseId":"FRFR1EATEN1","locationPk":"574865","nationalStationId":"FRFR1P8704164420360895621"},{"expectedOperatorId":"3353","physicalReference":"DEGM1","nationalEvseId":"FRLE2EDEGM1","locationPk":"592630","nationalStationId":"FRLE2P855251647589442442"},{"expectedOperatorId":"98468","physicalReference":"ADFM1","nationalEvseId":"FRLE2EADFM1","locationPk":"617325","nationalStationId":"FRLE2P6018472125822626667"}];
const ALLOWED={
 location:new Set(['operatorId','operatorPk','networkId','networkPk','networkName','partyId','countryCode','cpoId','cpoName','evseId','ocpiId','locationId']),
 operator:new Set(['pk','id','operatorId','operatorPk','partyId','countryCode','cpoId','cpoName','networkId','networkPk','networkName','ocpiId','code']),
 evse:new Set(['evseId','evseID','evseUid','uid','id','ocpiId','ocpiEvseId','externalId','externalEvseId','nationalEvseId','partyId','countryCode','operatorId','networkId','cpoId','roamingId'])
};
const BASE={location:['__typename','chargingLocationPk','name'],operator:['__typename','name'],evse:['__typename','pk','physicalReference']};
const norm=v=>String(v??'').trim().toUpperCase().replace(/[\s*\-]/g,'');
export function verifyPin(p){
 if(p.purpose!=='g5_electroverse_eight_station_identity_probe_only'||p.maxRequests!==10||p.attemptsPerRequest!==1||p.pauseMs!==3000||p.stopOn429!==true||p.automaticPublication!==false||p.matchingRulesChanged!==false||JSON.stringify(p.targets)!==JSON.stringify(EXPECTED))throw Error('Unapproved scope');
}
export function extraFields(fields,role){
 return (fields||[]).filter(f=>ALLOWED[role].has(f.name)&&['SCALAR','ENUM'].includes(f.type?.kind==='NON_NULL'?f.type?.ofType?.kind:f.type?.kind)&&!(f.args||[]).some(a=>a.type?.kind==='NON_NULL'&&a.defaultValue==null)).map(f=>f.name).sort();
}
export function locationQuery(extras={}){
 const field=r=>[...BASE[r],...(extras[r]||[])].join(' ');
 return `query G5Identity($pk:String!){chargingLocation(pk:$pk){${field('location')} operator{${field('operator')}} evses{edges{node{${field('evse')}}} pageInfo{hasNextPage}}}}`;
}
const shape=`fields{name type{kind name ofType{kind name}} args{name defaultValue type{kind}}}`;
export function schemaQuery(types){
 const selected=Object.entries(types).filter(([,v])=>typeof v==='string'&&/^[A-Za-z_][A-Za-z0-9_]*$/.test(v));
 return selected.length?`query G5IdentitySchema{${selected.map(([role,t])=>`${role}:__type(name:${JSON.stringify(t)}){name ${shape}}`).join(' ')}}`:null;
}
function clean(record,fields){
 if(!record||typeof record!=='object')return null;
 return Object.fromEntries(fields.filter(k=>Object.hasOwn(record,k)).map(k=>[k,typeof record[k]==='string'?record[k].slice(0,300):typeof record[k]==='number'||typeof record[k]==='boolean'||record[k]===null?record[k]:null]));
}
export function project(data,target,extras={}){
 const loc=data?.chargingLocation;
 if(!loc||String(loc.chargingLocationPk)!==target.locationPk)return {status:'LOCATION_MISSING_OR_MISMATCH'};
 const evses=(loc.evses?.edges||[]).map(e=>clean(e?.node,[...BASE.evse,...(extras.evse||[])])).filter(Boolean);
 const matching=evses.filter(e=>norm(e.physicalReference)===norm(target.physicalReference));
 return {status:matching.length===1?'REFERENCE_OBSERVED':matching.length?'REFERENCE_AMBIGUOUS':'REFERENCE_NOT_OBSERVED',location:clean(loc,[...BASE.location,...(extras.location||[])]),operator:clean(loc.operator,[...BASE.operator,...(extras.operator||[])]),evses,matchingReferenceCount:matching.length,hasNextPage:loc.evses?.pageInfo?.hasNextPage??null};
}
export async function probe(client,p,{sleep=ms=>new Promise(r=>setTimeout(r,ms))}={}){
 verifyPin(p);
 const report={generatedAt:new Date().toISOString(),scope:p,requests:[],schema:null,stations:[],stopped:null,newMatches:0,pricesPromoted:0,matchingRulesChanged:false,automaticPublication:false};
 async function call(query,variables,kind){
  if(report.requests.length>=p.maxRequests)throw Error('Budget exceeded');
  if(report.requests.length)await sleep(p.pauseMs);
  const r=await client.request(query,variables,{attempts:1});
  const errors=Array.isArray(r.json?.errors)?r.json.errors.length:0;
  report.requests.push({kind,locationPk:variables.pk??null,status:r.status,ms:r.ms,errorCount:errors,retryAfterPresent:!!r.responseHeaders?.retryAfter});
  if(r.status!==200){report.stopped='HTTP_'+r.status;return null;}
  if(errors){if(kind==='schema'){report.schema={status:'NOT_AVAILABLE',errorCount:errors};return null;}report.stopped='GRAPHQL_LOCATION_ERROR';return null;}
  if(!r.json?.data){report.stopped='MISSING_DATA';return null;}
  return r.json.data;
 }
 const first=p.targets[0];
 const initial=await call(locationQuery(),{pk:first.locationPk},'baseline');
 if(!initial)return report;
 const sample=project(initial,first);
 report.stations.push({target:first,...sample});
 const types={location:sample.location?.__typename,operator:sample.operator?.__typename,evse:sample.evses?.[0]?.__typename};
 const sq=schemaQuery(types);let extras={};
 if(sq){
  const s=await call(sq,{},'schema');
  if(report.stopped)return report;
  if(s){
   report.schema={status:'OBSERVED',types:{}};
   for(const role of Object.keys(types)){
    const fields=s[role]?.fields||[];
    extras[role]=extraFields(fields,role);
    report.schema.types[role]={name:s[role]?.name??null,fieldNames:fields.map(f=>f.name),queriedIdentityFields:extras[role]};
   }
  }
 }
 const hasExtras=Object.values(extras).some(v=>v.length);
 const todo=hasExtras?p.targets:p.targets.slice(1);
 for(const t of todo){
  if(report.stopped)break;
  const data=await call(locationQuery(extras),{pk:t.locationPk},'identity');
  if(!data)break;
  const row={target:t,...project(data,t,extras)};
  const i=report.stations.findIndex(x=>x.target.locationPk===t.locationPk);
  if(i>=0)report.stations[i]=row;else report.stations.push(row);
 }
 return report;
}
async function main(){
 const p=JSON.parse(await fs.readFile(process.argv[2],'utf8'));verifyPin(p);
 const report=await probe(new DirectElectroverseClient({timeoutMs:45000}),p);
 const out=process.argv[3];await fs.mkdir(out,{recursive:true});
 await fs.writeFile(path.join(out,'identity-probe.json'),JSON.stringify(report,null,2)+'\n');
 console.log('G5_IDENTITY_PROBE '+JSON.stringify({requests:report.requests.length,stations:report.stations.length,stopped:report.stopped,schema:report.schema?.status??null,statusCounts:report.stations.reduce((a,x)=>(a[x.status]=(a[x.status]||0)+1,a),{})}));
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)await main();
