/**
 * Diagnose IRVE ↔ Electra/Electroverse identifiers at EVSE granularity.
 * Read only: no station, offer or price is modified.
 * Only full alphanumeric identifiers count as exact matches. Numeric ordinals,
 * suffix guesses, multiple national owners, multiple source owners and already
 * published target IDs fail closed.
 */
import fs from 'node:fs/promises';
import zlib from 'node:zlib';
import path from 'node:path';

const norm=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const fullId=k=>/^FR[A-Z0-9]{7,}$/.test(k);
const reportPath='reports/france/irve/alphanumeric-residual-audit-2026-10-08.json';
const casesPath='reports/france/irve/alphanumeric-residual-cases-2026-10-08.json.gz';
const load=async file=>JSON.parse(await fs.readFile(file,'utf8'));
const unzip=async file=>JSON.parse(zlib.gunzipSync(await fs.readFile(file)).toString('utf8'));
const claim=(map,k,owner)=>{if(!k)return;let set=map.get(k);if(!set){set=new Set();map.set(k,set);}set.add(String(owner));};
const haversine=(a,b,c,d)=>{const v=[a,b,c,d].map(Number);if(!v.every(Number.isFinite))return null;
 const [x,y,p,q]=v,r=Math.PI/180,dl=(p-x)*r,dn=(q-y)*r;
 const t=Math.sin(dl/2)**2+Math.cos(x*r)*Math.cos(p*r)*Math.sin(dn/2)**2;return 6371000*2*Math.asin(Math.min(1,Math.sqrt(t)));
};
const buckets=(items,key)=>items.reduce((obj,item)=>{const k=key(item);obj[k]=(obj[k]||0)+1;return obj;},{});
const first=(arr,max=100)=>arr.slice(0,max);
const national=await unzip('data/national/france-irve-static-v9/all.json.gz');
const nationalByKey=new Map(),nationalClaims=new Map();
for(const row of national){
 for(const cfg of row?.[8]||[])for(const id of cfg?.[6]||[]){
   const k=norm(id);if(!k)continue;
   claim(nationalClaims,k,row[0]);
   if(!nationalByKey.has(k))nationalByKey.set(k,[]);
   const arr=nationalByKey.get(k);
   if(!arr.some(x=>String(x.id)===String(id)&&String(x.stationId)===String(row[0])))
    arr.push({id:String(id),stationId:String(row[0]),name:row[1],address:row[2],lat:row[3],lon:row[4],operator:row[5],powerKw:cfg[3],connector:cfg[1]});
 }
}
const electraBase='data/platforms/electra/france';
const [electraSource,electraResidual,electraManifest]=await Promise.all([
 unzip(electraBase+'/source-locations.json.gz'),
 unzip(electraBase+'/residuals.json.gz'),
 load(electraBase+'/manifest.json')
]);
const alternateClaims=new Map(),exactClaims=new Map();
for(const loc of electraSource.locations||[]){
 for(const e of loc.evses||[]){
   claim(alternateClaims,norm(e.physicalReference),loc.id);
   claim(alternateClaims,norm(e.id),loc.id);
   claim(exactClaims,norm(e.evseId),loc.id);
 }
}
const electraCases=[],electraCandidates=[];
for(const loc of electraResidual.locations||[]){
 if(loc.reason!=='no_national_evse')continue;
 const matches=[],unmatched=[],obstacles=[];
 for(const evse of loc.evses||[]){
   const probes=[['physicalReference',evse.physicalReference],['id',evse.id],['evseId',evse.evseId]]
     .map(([field,value])=>({field,raw:String(value??''),key:norm(value)}))
     .filter(p=>fullId(p.key));
   const candidates=[];
   for(const probe of probes){
     const targets=nationalByKey.get(probe.key)||[];
     if(!targets.length)continue;
     const owners=nationalClaims.get(probe.key);
     const srcOwners=probe.field==='evseId'?exactClaims.get(probe.key):alternateClaims.get(probe.key);
     if(owners?.size!==1){obstacles.push('national_normalized_id_collision');continue;}
     if(srcOwners?.size!==1){obstacles.push('electra_source_identifier_collision');continue;}
     if(exactClaims.has(probe.key)&&![...exactClaims.get(probe.key)].includes(String(loc.electraLocationId))){
       obstacles.push('already_claimed_by_different_electra_location');continue;
     }
     const target=targets[0];
     const distance=haversine(loc.coordinates?.latitude,loc.coordinates?.longitude,target.lat,target.lon);
     if(distance==null||distance>15){obstacles.push('geographic_mismatch_or_missing_coordinates');continue;}
     candidates.push({sourceField:probe.field,sourceId:probe.raw,targetId:target.id,
       targetStationId:target.stationId,targetName:target.name,
       targetOperator:target.operator,distanceMeters:+distance.toFixed(2),evseId:evse.evseId??null,
       sourcePhysicalReference:evse.physicalReference??null});
   }
   const distinct=[...new Map(candidates.map(c=>[norm(c.targetId),c])).values()];
   if(distinct.length===1)matches.push(distinct[0]);
   else{unmatched.push({id:evse.evseId||evse.id||null,physicalReference:evse.physicalReference||null,
      reason:distinct.length>1?'multiple_different_irve_targets':'no_unique_alphanumeric_target'});
     if(distinct.length>1)obstacles.push('multiple_different_irve_targets');
   }
 }
 const nationalIds=matches.map(x=>norm(x.targetId));
 const stationIds=new Set(matches.map(x=>x.targetStationId));
 const bijective=matches.length>0&&matches.length===(loc.evses||[]).length&&new Set(nationalIds).size===matches.length&&stationIds.size===1;
 const outcome=bijective?'review_ready_full_evse_bijection':matches.length?'partial_strict_match_review':'no_unique_exact_alphanumeric_match';
 const item={source:'Electra',electraLocationId:loc.electraLocationId,name:loc.name,cpo:loc.cpo,
   reason:loc.reason,outcome,evseCount:loc.evses?.length||0,matches,unmatched,
   obstacles:[...new Set(obstacles)]};
 electraCases.push(item);if(bijective)electraCandidates.push(item);
}
const electroverseBase='data/platforms/electroverse/france-evse';
const em=await load(electroverseBase+'/manifest.json');
const publishedPks=new Set(),publishedNational=new Set();
for(const tile of em.tiles||[]){
 const doc=await unzip(path.join(electroverseBase,tile.file));
 for(const offer of doc.emspOffers||[]){
   for(const key of ['electroverseEvsePks','electroverseAliasEvsePks']){
     for(const pk of offer?.metadata?.[key]||[])publishedPks.add(String(pk));
   }
   if(offer?.metadata?.electroverseEvsePk!=null)publishedPks.add(String(offer.metadata.electroverseEvsePk));
   for(const id of offer.evseIds||[])publishedNational.add(norm(id));
 }
}
const mapping=await load('data/electroverse/irve_location_mapping.json');
const mappingByPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const localClaims=new Map();
for(const m of mapping.mappings||[])for(const id of m.irvePdcIds||[])claim(localClaims,norm(id),m.irveStationId);
const cache=await load('data/electroverse/tariff_cache/manifest.json');
const electroverseRaw=[],refOwners=new Map();
for(const shard of cache.shards||[]){
 const doc=await load('data/electroverse/tariff_cache/'+shard.file);
 for(const row of Object.values(doc.stations||{})){
   const pk=String(row.electroverseLocationPk),owner=mappingByPk.get(pk),localIds=owner?.irvePdcIds?.length?owner.irvePdcIds:(row.irvePdcIds||[]);
   const local=new Map(localIds.map(id=>[norm(id),id]).filter(([k])=>k));
   for(const e of row?.tariff?.evses||[]){
     const k=norm(e.physicalReference);
     claim(refOwners,k,pk);
     if(e.pk==null||publishedPks.has(String(e.pk)))continue;
     electroverseRaw.push({locationPk:pk,sourceEvsePk:String(e.pk),physicalReference:String(e.physicalReference??''),
       normalizedReference:k,local,localStationId:owner?.irveStationId??row.irveStationId??null});
   }
 }
}
const electroverseCases=[],electroverseCandidates=[],targetHits=new Map();
for(const e of electroverseRaw){
 const rawTarget=e.local.get(e.normalizedReference)||null;
 const knownNational=rawTarget&&nationalByKey.get(e.normalizedReference);
 let reason;
 if(!fullId(e.normalizedReference))reason='generic_or_incomplete_source_reference';
 else if(!rawTarget)reason='normalized_id_absent_from_local_irve';
 else if((localClaims.get(e.normalizedReference)||new Set()).size!==1)reason='multiple_national_station_owners';
 else if(!knownNational)reason='no_current_irve_identifier';
 else if(publishedNational.has(e.normalizedReference))reason='national_target_already_published';
 else if(refOwners.get(e.normalizedReference)?.size!==1)reason='electroverse_identifier_shared_by_locations';
 else reason='review_ready_strict_unpublished_evse';
 const item={source:'Electroverse',locationPk:e.locationPk,sourceEvsePk:e.sourceEvsePk,
   physicalReference:e.physicalReference,normalizedReference:e.normalizedReference,
   irveStationId:e.localStationId,candidateIrvePdc:rawTarget||null,reason};
 electroverseCases.push(item);
 if(reason==='review_ready_strict_unpublished_evse'){electroverseCandidates.push(item);claim(targetHits,e.normalizedReference,e.sourceEvsePk);}
}
for(const item of electroverseCandidates){
 if(targetHits.get(item.normalizedReference)?.size!==1)item.reason='multiple_source_evse_claims_same_target';
}
const goodElectroverse=electroverseCandidates.filter(x=>x.reason==='review_ready_strict_unpublished_evse');
const aggregate={
 schemaVersion:1,generatedAt:new Date().toISOString(),
 description:'Strict alphanumeric normalization and identity evidence only; review candidates, no automatic joins or inferred tariff. Every unresolved case appears in separate gz.',
 inputs:{nationalPdcCount:170568,electraSnapshotAt:electraManifest.generatedAt,electroverseSnapshotAt:em.generatedAt,cacheAt:cache.generatedAt},
 policy:{normalization:"NFKD+uppercase+retain [A-Z0-9]; strip * / backslash ; separators",
  exactMatch:"full normalized EVSE ID; no suffix, ordinal-only or proximity joins",
  electra:"national identifier unique; secondary identifier unique over source; no conflicting full-ID source; location <=15m; all EVSEs map bijectively to one IRVE station; review required before promoting",
  electroverse:"source ref globally unique, local exact unique national identifier, unused PDC, source EVSE not already published; review required before promoting"},
 stats:{
  electra:{sourceResidualLocations:electraResidual.locations.length,noNationalEvse:electraCases.length,
    matchedExactSecondaryFullLocations:electraCandidates.length,
    matchedPartialLocations:electraCases.filter(x=>x.outcome==='partial_strict_match_review').length,
    pendingNoSafeMatch:electraCases.filter(x=>x.outcome==='no_unique_exact_alphanumeric_match').length,
    byOutcome:buckets(electraCases,x=>x.outcome)},
  electroverse:{cacheResidualEvse:electroverseCases.length,reviewReadyDistinctCandidates:goodElectroverse.length,
    reasons:buckets(electroverseCases,x=>x.reason)},
  national:{distinctNormalizedEvseIds:nationalByKey.size,ambiguousNormalizedIds:[...nationalClaims.values()].filter(x=>x.size>1).length}
 },
 reviewCandidates:{electra:electraCandidates.slice(0,500),electroverse:goodElectroverse.slice(0,500)},
 firstCases:{electra:electraCases.slice(0,50),electroverse:electroverseCases.filter(x=>x.reason!=='generic_or_incomplete_source_reference').slice(0,60)},
 caseArchive:{path:casesPath,electraCases:electraCases.length,electroverseCases:electroverseCases.length}
};
await fs.mkdir(path.dirname(reportPath),{recursive:true});
await fs.writeFile(reportPath,JSON.stringify(aggregate,null,2)+'\n');
await fs.writeFile(casesPath,zlib.gzipSync(Buffer.from(JSON.stringify({schemaVersion:1,generatedAt:aggregate.generatedAt,electra:electraCases,electroverse:electroverseCases})),{level:9}));
console.log(JSON.stringify({generatedAt:aggregate.generatedAt,inputs:aggregate.inputs,stats:aggregate.stats,
 reviewSamples:{electra:first(electraCandidates,8).map(x=>({name:x.name,cpo:x.cpo,matches:x.matches})),
 electroverse:first(goodElectroverse,8)}}));
