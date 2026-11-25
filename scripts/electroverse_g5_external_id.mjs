import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {DirectElectroverseClient} from './lib/electroverse_direct_client.mjs';
const EXPECTED=[{"expectedOperatorId":"21133","physicalReference":"JCFV1","nationalEvseId":"FRFR1EJCFV1","locationPk":"652329","nationalStationId":"FRFR1P8289342808958091411"},{"expectedOperatorId":"64694","physicalReference":"NBKJ1","nationalEvseId":"FRFR1ENBKJ1","locationPk":"943602","nationalStationId":"FRFR1P3954308727827316770"},{"expectedOperatorId":"727","physicalReference":"WAYZ1","nationalEvseId":"FRFR1EWAYZ1","locationPk":"617076","nationalStationId":"FRFR1P2365459661242012003"},{"expectedOperatorId":"3326","physicalReference":"MYKC1","nationalEvseId":"FRFR1EMYKC1","locationPk":"581442","nationalStationId":"FRFR1PVFKUJC"},{"expectedOperatorId":"3527","physicalReference":"RRHD1","nationalEvseId":"FRFR1ERRHD1","locationPk":"1004083","nationalStationId":"FRFR1P5316535057035692011"},{"expectedOperatorId":"3468","physicalReference":"ATEN1","nationalEvseId":"FRFR1EATEN1","locationPk":"574865","nationalStationId":"FRFR1P8704164420360895621"},{"expectedOperatorId":"3353","physicalReference":"DEGM1","nationalEvseId":"FRLE2EDEGM1","locationPk":"592630","nationalStationId":"FRLE2P855251647589442442"},{"expectedOperatorId":"98468","physicalReference":"ADFM1","nationalEvseId":"FRLE2EADFM1","locationPk":"617325","nationalStationId":"FRLE2P6018472125822626667"}];
export const QUERY='query G5StationExternalId($pk:String!){chargingLocation(pk:$pk){chargingLocationPk name externalId address postalCode city operator{pk name} evses{edges{node{pk physicalReference}} pageInfo{hasNextPage}}}}';
export function verifyPin(p){if(p.purpose!=='g5_final_station_and_tariff_evidence_only'||p.liveMaxRequests!==8||p.livePauseMs!==3000||p.automaticPublication!==false||JSON.stringify(p.targets)!==JSON.stringify(EXPECTED))throw Error('Scope');}
const norm=v=>String(v??'').trim().toUpperCase().replace(/[\s*\-]/g,'');
const scalar=v=>typeof v==='string'?v.slice(0,500):typeof v==='number'?v:null;
export function project(data,t){
 const l=data?.chargingLocation;
 if(!l||String(l.chargingLocationPk)!==t.locationPk)return {status:'LOCATION_MISSING_OR_MISMATCH'};
 const externalId=scalar(l.externalId),evses=(l.evses?.edges||[]).map(e=>({pk:scalar(e?.node?.pk),physicalReference:scalar(e?.node?.physicalReference)}));
 const referenceCount=evses.filter(e=>norm(e.physicalReference)===norm(t.physicalReference)).length;
 return {status:referenceCount===1&&l.evses?.pageInfo?.hasNextPage===false?'REFERENCE_OBSERVED_COMPLETE':'REFERENCE_OR_PAGINATION_REVIEW',externalId,externalIdRelation:!norm(externalId)?'MISSING':norm(externalId)===norm(t.nationalStationId)?'EXACT_NATIONAL_STATION_ID':'DIFFERENT_NOT_AUTOMATIC_CONTRADICTION',name:scalar(l.name),address:scalar(l.address),postalCode:scalar(l.postalCode),city:scalar(l.city),operator:{pk:scalar(l.operator?.pk),name:scalar(l.operator?.name)},evses,hasNextPage:l.evses?.pageInfo?.hasNextPage??null};
}
export async function probe(client,p,{sleep=ms=>new Promise(r=>setTimeout(r,ms))}={}){
 verifyPin(p);const report={generatedAt:new Date().toISOString(),scope:p,requests:[],stations:[],stopped:null,newMatches:0,pricesPromoted:0,automaticPublication:false};
 for(const t of p.targets){
  if(report.requests.length)await sleep(p.livePauseMs);
  const r=await client.request(QUERY,{pk:t.locationPk},{attempts:1});
  const errors=Array.isArray(r.json?.errors)?r.json.errors.length:0;
  report.requests.push({locationPk:t.locationPk,status:r.status,errorCount:errors,ms:r.ms,retryAfterPresent:!!r.responseHeaders?.retryAfter});
  if(r.status!==200||errors||!r.json?.data){report.stopped=r.status!==200?'HTTP_'+r.status:errors?'GRAPHQL_ERROR':'MISSING_DATA';break;}
  report.stations.push({target:t,...project(r.json.data,t)});
 }
 return report;
}
async function main(){
 const p=JSON.parse(await fs.readFile(process.argv[2],'utf8'));verifyPin(p);const report=await probe(new DirectElectroverseClient({timeoutMs:45000}),p);
 const out=process.argv[3];await fs.mkdir(out,{recursive:true});await fs.writeFile(path.join(out,'external-id-probe.json'),JSON.stringify(report,null,2)+'\n');
 console.log('G5_EXTERNAL_ID '+JSON.stringify({requests:report.requests.length,stations:report.stations.length,stopped:report.stopped,relations:report.stations.reduce((a,x)=>(a[x.externalIdRelation??x.status]=(a[x.externalIdRelation??x.status]||0)+1,a),{})}));
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)await main();
