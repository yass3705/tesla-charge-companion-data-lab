import fs from 'node:fs/promises';
import crypto from 'node:crypto';
const dir='data/platforms/electroverse/validated-mappings/';
const evidence=JSON.parse(await fs.readFile(dir+'app-evidence-four-extra-exact-2026-10-11.json','utf8'));
const priority=JSON.parse(await fs.readFile('reports/electroverse/full-reconciliation/priority-review-evidence.json','utf8'));
const mapping=JSON.parse(await fs.readFile('data/electroverse/irve_location_mapping.json','utf8'));
const manifest=JSON.parse(await fs.readFile('data/electroverse/tariff_cache/manifest.json','utf8'));
const norm=v=>String(v??'').replace(/[^A-Z0-9]/ig,'').toUpperCase();
const errors=[],matches=[],unverified=[],unmatchedAppScreenshots=[];
const byLocation=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const distanceMeters=(a,b)=>{
 const n=[a?.lat,a?.lon,b?.lat,b?.lon].map(Number);
 if(n.some(x=>!Number.isFinite(x)))return null;
 const [la1,lo1,la2,lo2]=n.map(x=>x*Math.PI/180),dlat=la2-la1,dlon=lo2-lo1;
 return 2*6371000*Math.asin(Math.sqrt(Math.sin(dlat/2)**2+Math.cos(la1)*Math.cos(la2)*Math.sin(dlon/2)**2));
};
const byTarget=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
 const k=norm(p);const a=byTarget.get(k)||new Set();a.add(m.irveStationId);byTarget.set(k,a);
}
async function location(pk){
 const shard=crypto.createHash('sha1').update(String(pk)).digest()[0]%128;
 const file='data/electroverse/tariff_cache/shard-'+String(shard).padStart(3,'0')+'.json';
 const j=JSON.parse(await fs.readFile(file,'utf8'));
 return {row:j.stations?.[String(pk)]||null,shard:file};
}
for(const input of evidence.confirmedMatches){
 const loc=String(input.sourceLocationPk),expected=norm(input.appId),cache=await location(loc);
 const evses=cache.row?.tariff?.evses||[];
 const es=evses.filter(e=>String(e.pk)===String(input.sourceEvsePk));
 const local=byLocation.get(loc);
 const localTargets=(local?.irvePdcIds||[]).filter(p=>norm(p)===expected);
 const owners=byTarget.get(expected)||new Set();
 const matchedOwnershipLocations=(mapping.mappings||[]).filter(m=>(m.irvePdcIds||[]).some(p=>norm(p)===expected));
 const ownerDetails=matchedOwnershipLocations.map(m=>({
   stationId:m.irveStationId,sourceLocationPk:String(m.electroverseLocationPk),
   mappingSource:m.source||m.mappingMode||null,
   name:m.electroverse?.name||m.irve?.name||m.irveStationName||null,
   irve:m.irve||null,electroverse:m.electroverse||null,
   mappedPdcCount:m.irvePdcIds?.length||0
 }));
 const scoredOwners=ownerDetails.map(o=>({
  stationId:o.stationId,sourceLocationPk:o.sourceLocationPk,
  metersToIrve:distanceMeters(cache.row?local?.electroverse:null,o.irve),
  isCanonical:o.stationId===input.stationId&&o.sourceLocationPk===loc
 }));
 const canonicalScores=scoredOwners.filter(o=>o.isCanonical&&o.metersToIrve!==null&&o.metersToIrve<=10);
 const otherScores=scoredOwners.filter(o=>!o.isCanonical);
 const deterministicGpsOwner=canonicalScores.length===1&&otherScores.length>0&&otherScores.every(o=>
  o.metersToIrve!==null&&o.metersToIrve>20
 );
 const reportRows=(priority.extraExact||[]).filter(x=>String(x.sourcePk)===String(input.sourceEvsePk));
 const prices=reportRows.flatMap(x=>x.price||[]);
 const info={appId:input.appId,locationPk:loc,sourcePk:input.sourceEvsePk,
  shard:cache.shard,cacheEvses:es.length,cacheRef:es[0]?.physicalReference??null,
  cacheMatching:es.length===1&&norm(es[0].physicalReference)===expected,
  sourceConnectorProfiles:es.flatMap(e=>(e.connectors||[]).map(c=>({kw:c.kilowatts,standard:String(c.standard?.name||c.standard||''),
   pricingDetailPresent:!!c.complexPricingDetail,hasSimplePriceComponents:Array.isArray(c.priceComponents)}))),
  exactLocalIrvePdcs:localTargets,uniqueLocalIrve:localTargets.length===1,
  globalOwnerCount:owners.size,globalStations:[...owners],ownerDetails,
  scoredOwners,deterministicGpsOwner,geoRule:'Canonical exact source location within 10m of IRVE and all other national ownership sites >20m away',
  sourcePricingReport:prices.map(p=>({kw:p.kw,rateComponents:p.components,complexRestrictions:p.restrictions})),
  evidenceDisplayStatus:input.appStatus,needsNationalStatusGate:true};
 const check=info.cacheMatching&&info.uniqueLocalIrve&&owners.has(input.stationId)&&
  (owners.size===1||deterministicGpsOwner)&&
  es.some(e=>(e.connectors||[]).some(c=>Math.abs(Number(c.kilowatts)-input.maxKw)<.001))&&
  prices.length&&prices.every(p=>p.kw===input.maxKw&&
     p.components.some(c=>c[0]==='ConsumptionRate'&&String(c[1]).includes('€'+input.eurPerKwh.toFixed(2))) );
 info.validated=!!check;
 if(!check)errors.push({appId:input.appId,reason:'Source cache / exact national IRVE identity / tariff did not match',info});
 matches.push(info);
}
for(const input of evidence.stillUnverified){
 const loc=String(input.sourceLocationPk),cache=await location(loc);
 const exists=(cache.row?.tariff?.evses||[]).some(e=>String(e.pk)===String(input.sourceEvsePk)&&norm(e.physicalReference)===norm(input.expectedAppId));
 unverified.push({...input,cacheSourceExists:exists,appProofAbsent:true});
}
for(const input of evidence.otherScreenshots){
 const matchesInIrve=(mapping.mappings||[]).filter(m=>(m.irvePdcIds||[]).some(p=>norm(p)===input.identityNormalized));
 unmatchedAppScreenshots.push({...input,nationalIrveMatches:matchesInIrve.map(m=>({locationPk:m.electroverseLocationPk,stationId:m.irveStationId})),
  cannotBeSubstitutedForMissingAllegoSoissons:true});
}
const output={schemaVersion:1,generatedAt:new Date().toISOString(),mode:'READ_ONLY_NO_OVERLAY_WRITE',
 coverage:{confirmedScreenshots:evidence.confirmedMatches.length,confirmedExactSourceMatches:matches.filter(x=>x.validated).length,
  expectedUnpublishedResiduals:4,matchingScreenEvidence:3,stillUnverified:unverified.length,otherScreenshotCount:unmatchedAppScreenshots.length},
 matches,unverified,unmatchedAppScreenshots,errors,
 publicationBlocked:true,
 publicationRequirements:['Source PK live AVAILABLE/CHARGING', 'All exact physical references one-to-one in current IRVE', 'No conflicting active eMSP offers', 'National status ledger complete']};
const outfile='reports/electroverse/app-extra-exact-evidence-audit-2026-10-11.json';
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(outfile,JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify({event:'RESULT',report:outfile,coverage:output.coverage,errorCount:errors.length,other:unmatchedAppScreenshots}));
if(errors.length){
 for(const e of errors)console.log(JSON.stringify({event:'MISMATCH',appId:e.appId,cacheEvses:e.info.cacheEvses,
 cacheRef:e.info.cacheRef,cacheMatching:e.info.cacheMatching,sourceConnectorProfiles:e.info.sourceConnectorProfiles,
 localPdcs:e.info.exactLocalIrvePdcs,globalOwnerCount:e.info.globalOwnerCount,globalStations:e.info.globalStations,
 scoredOwners:e.info.scoredOwners,deterministicGpsOwner:e.info.deterministicGpsOwner,
 sourcePricingReport:e.info.sourcePricingReport?.map(p=>({kw:p.kw,rate:p.rateComponents?.filter(c=>c[0]==='ConsumptionRate')}))}));
 process.exitCode=2;
}
