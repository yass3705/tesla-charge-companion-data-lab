/**
 * Exhaustive, read-only reconciliation of France Electroverse tariff cache,
 * IRVE national static registry and the actually published connector-level overlay.
 * Never publishes an offer or invents a tariff; all rows retain provenance.
 */
import fs from 'node:fs/promises';
import zlib from 'node:zlib';
import path from 'node:path';
import crypto from 'node:crypto';

const ROOT='reports/electroverse/full-reconciliation';
const SOURCE='data/electroverse/tariff_cache';
const OVERLAY='data/platforms/electroverse/france-evse';
const norm=v=>String(v??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const txt=v=>String(v??'').trim();
const fullId=v=>/^FR[A-Z0-9]{7,}$/.test(norm(v));
const read=async f=>JSON.parse(await fs.readFile(f,'utf8'));
const gzread=async f=>JSON.parse(zlib.gunzipSync(await fs.readFile(f)).toString('utf8'));
const hash=v=>crypto.createHash('sha256').update(JSON.stringify(v)).digest('hex').slice(0,16);
const operator=v=>{
 const s=txt(v),p=s.split('*').filter(Boolean);
 if(p.length>=2&&p[0].toUpperCase()==='FR')return p[1].toUpperCase();
 const k=norm(s);const m=k.match(/^FR([A-Z0-9]{1,8})E/);
 return m?m[1]:(/^\d+$/.test(k)?'NUMERIC':k.slice(0,12)||'UNIDENTIFIED');
};
const asArray=v=>Array.isArray(v)?v:[];
const count=(o,k)=>{o[k]=(o[k]||0)+1};
const csv=s=>'"'+String(s??'').replace(/"/g,'""').replace(/\r?\n/g,' ')+'"';
const csvLine=o=>Object.values(o).map(csv).join(',');

await fs.mkdir(ROOT,{recursive:true});
const [sm,om,mm,irve,userHold]=await Promise.all([
 read(SOURCE+'/manifest.json'),read(OVERLAY+'/manifest.json'),
 read('data/electroverse/irve_location_mapping.json'),
 gzread('data/national/france-irve-static-v9/all.json.gz'),
 read('reports/electroverse/ambiguity-disposition-user-confirmed-2026-10-10.json')
]);
const mapping=new Map(asArray(mm.mappings).map(m=>[txt(m.electroverseLocationPk),m]));
const userConflicts=new Map(asArray(userHold.records).map(r=>[norm(r.normalizedIrve),r]));
const irveById=new Map();
for(const st of irve){
 const stationId=txt(st?.[0]);
 for(const cfg of asArray(st?.[8]))for(const id of asArray(cfg?.[6])){
  const k=norm(id);if(!k)continue;
  let v=irveById.get(k);
  if(!v){v={stationIds:new Set(),rawId:txt(id),name:st?.[1],power:cfg?.[3],connector:cfg?.[1]};irveById.set(k,v);}
  v.stationIds.add(stationId);
 }
}
const publishedPk=new Set(),publishedTarget=new Set(),publishedOffersById=new Map();
let publishedOfferCount=0,publishedWithSourcePk=0;
for(const t of asArray(om.tiles)){
 const tile=await gzread(OVERLAY+'/'+t.file);
 for(const o of asArray(tile.emspOffers)){
  publishedOfferCount++;
  const m=o.metadata||{};
  const pks=[...asArray(m.electroverseEvsePks),...asArray(m.electroverseAliasEvsePks),m.electroverseEvsePk].filter(x=>x!=null);
  if(pks.length)publishedWithSourcePk++;
  for(const pk of pks)publishedPk.add(txt(pk));
  for(const id of asArray(o.evseIds)){
   const n=norm(id);if(!n)continue;
   publishedTarget.add(n);
   let v=publishedOffersById.get(n);if(!v){v=new Set();publishedOffersById.set(n,v);}
   v.add(txt(o.id));
  }
 }
}
const locations=new Map(),physicalOwners=new Map(),refGroups=new Map();
const counters={sourceStations:0,sourceEvses:0,sourceConnectors:0,missingPk:0,publishedSourceEvses:0,unpublishedSourceEvses:0,sourceNoConnectors:0,sourceNoPricingPayload:0,distinctTariffSignatures:0,sourceMultiConnectorPower:0,sourceRestrictedConnectors:0,emptyPhysicalReference:0};
const all=[],sigSeen=new Set();
for(const sh of asArray(sm.shards)){
 const doc=await read(SOURCE+'/'+sh.file);
 for(const [dictPk,row] of Object.entries(doc.stations||{})){
  counters.sourceStations++;
  const locPk=txt(row.electroverseLocationPk||dictPk);
  const mapped=mapping.get(locPk)||null;
  const stId=txt(mapped?.irveStationId||row.irveStationId);
  const locals=asArray(mapped?.irvePdcIds?.length?mapped.irvePdcIds:row.irvePdcIds).map(norm).filter(Boolean);
  const localSet=new Set(locals);
  let loc=locations.get(locPk);
  if(!loc){loc={locPk,stId,localSet,sourceCount:0,publishedCount:0,operator:null,sourceName:txt(row?.tariff?.name||row?.tariff?.location?.name||row.name),cacheAt:txt(row.fetchedAt),mapped:!!mapped};locations.set(locPk,loc);}
  for(const e of asArray(row.tariff?.evses)){
   counters.sourceEvses++;loc.sourceCount++;
   const srcPk=txt(e?.pk),ref=txt(e?.physicalReference),refNorm=norm(ref);
   const isPublished=!!srcPk&&publishedPk.has(srcPk);
   if(isPublished){counters.publishedSourceEvses++;loc.publishedCount++;}else counters.unpublishedSourceEvses++;
   if(!srcPk)counters.missingPk++;
   if(!refNorm)counters.emptyPhysicalReference++;
   if(refNorm){
    let claim=physicalOwners.get(refNorm);if(!claim){claim=new Set();physicalOwners.set(refNorm,claim);}
    claim.add(locPk);
   }
   const connectors=asArray(e?.connectors);
   counters.sourceConnectors+=connectors.length;
   if(!connectors.length)counters.sourceNoConnectors++;
   const hasPrice=connectors.some(c=>c?.isChargingFree===true||asArray(c?.priceComponents).length>0||asArray(c?.complexPricingDetail?.restrictions).length>0);
   if(!hasPrice)counters.sourceNoPricingPayload++;
   const values=connectors.map(c=>({
    kw:Number(c?.kilowatts)||0,plug:txt(c?.standard?.name||c?.standard),
    free:c?.isChargingFree===true,components:asArray(c?.priceComponents).map(v=>[v.__typename,v.formattedValue]),
    currency:txt(c?.complexPricingDetail?.currency||'EUR'),
    restrictions:asArray(c?.complexPricingDetail?.restrictions).map(r=>({
      kinds:asArray(r.restrictionTypes),time:r.timeRestrictions||null,days:r.weekdayRestrictions||null,
      duration:r.durationRestrictions||null,date:r.dateRestrictions||null,
      components:asArray(r.priceComponents).map(c=>[c.__typename,c.formattedValue])
    }))
   })).sort((a,b)=>a.kw-b.kw||a.plug.localeCompare(b.plug));
   const signature=hash(values);
   // Separate price semantics from charger hardware/power variants.
   const tariffSignature=hash([...new Set(values.map(v=>JSON.stringify({
    free:v.free,currency:v.currency,components:v.components,restrictions:v.restrictions
   })))].sort());
   sigSeen.add(signature);
   if(new Set(values.map(v=>v.kw+'|'+v.plug)).size>1)counters.sourceMultiConnectorPower++;
   if(values.some(v=>v.restrictions.length))counters.sourceRestrictedConnectors++;
   const k=locPk+'|'+refNorm;
   if(refNorm){let g=refGroups.get(k);if(!g){g=[];refGroups.set(k,g);}g.push({pk:srcPk,sig:signature,tariffSig:tariffSignature,values});}
   const ev={
    locPk,stationId:stId,sourceName:loc.sourceName,operator:operator(ref),
    sourcePk:srcPk,physicalReference:ref,normalizedRef:refNorm,
    published:isPublished,cacheFetchedAt:txt(row.fetchedAt),
    tariffHash:txt(row.tariffHash),connectorCount:connectors.length,
    connectorSummary:values.map(v=>v.plug+':'+v.kw+'kW').join(';'),
    sourcePriceSignature:tariffSignature,sourceTechnicalSignature:signature,hasPrice,hasMultiplePower:new Set(values.map(v=>v.kw+'|'+v.plug)).size>1,
    sourceRestricts:values.some(v=>v.restrictions.length),
    hasPublicIdentityMatch:localSet.has(refNorm),localPdcCount:localSet.size,
    mapped:!!mapped,locationPkClaimCount:0,localSamePrefixCandidates:0,
    nationalOwnerCount:irveById.get(refNorm)?.stationIds.size||0,
    nationalStationIds:[...(irveById.get(refNorm)?.stationIds||[])].slice(0,5),
    uniqueSourcePricesAtSameRef:0,sourceRefsSameSite:0,caseReasons:[],
    sourcePriceComponents:values
   };
   all.push(ev);
  }
 }
}
counters.distinctTariffSignatures=sigSeen.size;
const categoryStats={},priorityStats={},cases=[],byOperator={},byStation={},newConflictCases=[];
const hold27=new Set(userConflicts.keys()),observedHold=new Set();
for(const ev of all){
 const group=refGroups.get(ev.locPk+'|'+ev.normalizedRef)||[];
 const gs=new Set(group.map(x=>x.tariffSig));
 const techVariants=new Set(group.map(x=>x.sig));
 ev.sourceRefsSameSite=group.length;ev.uniqueSourcePricesAtSameRef=gs.size;
 ev.locationPkClaimCount=physicalOwners.get(ev.normalizedRef)?.size||0;
 const loc=locations.get(ev.locPk);
 const local=loc?.localSet||new Set();
 const parentCandidates=[];
 if(ev.normalizedRef&&!local.has(ev.normalizedRef)){
  for(const p of local){
   if(!ev.normalizedRef.startsWith(p)||ev.normalizedRef.length<=p.length)continue;
   if(/^\d{1,2}$/.test(ev.normalizedRef.slice(p.length)))parentCandidates.push(p);
  }
 }
 ev.localSamePrefixCandidates=parentCandidates.length;
 const reasons=[];
 if(hold27.has(ev.normalizedRef)){
  reasons.push('USER_CONFIRMED_AMBIGUITY');observedHold.add(ev.normalizedRef);
 }
 if(ev.normalizedRef&&gs.size>1){
  reasons.push('SOURCE_DUPLICATE_DIFFERENT_PRICING');
  if(!hold27.has(ev.normalizedRef)&&(ev.hasPublicIdentityMatch||ev.nationalOwnerCount===1))newConflictCases.push(ev.normalizedRef);
 }else if(ev.normalizedRef&&techVariants.size>1){
  reasons.push('SOURCE_DUPLICATE_SAME_PRICE_TECHNICAL_VARIANT');
 }
 if(!ev.normalizedRef)reasons.push('MISSING_PHYSICAL_REFERENCE');
 if(!ev.sourcePk)reasons.push('MISSING_SOURCE_PK');
 if(ev.normalizedRef&&fullId(ev.normalizedRef)&&ev.locationPkClaimCount>1)reasons.push('FULL_SOURCE_ID_REUSED_ACROSS_LOCATIONS');
 if(ev.normalizedRef&&ev.nationalOwnerCount>1)reasons.push('NATIONAL_EVSE_MULTIPLE_STATIONS');
 if(parentCandidates.length>1)reasons.push('AMBIGUOUS_PARENT_PDC');
 if(!ev.mapped)reasons.push('SOURCE_LOCATION_NOT_IN_IRVE_MAPPING');
 if(!ev.hasPrice)reasons.push('SOURCE_PRICE_NOT_PRESENT');
 if(!ev.connectorCount)reasons.push('SOURCE_NO_CONNECTORS');
 if(!ev.published&&ev.hasMultiplePower)reasons.push('MULTIPLE_CONNECTOR_POWER_NEEDS_PER_CONNECTOR_MATCH');
 if(!ev.published&&ev.sourceRestricts)reasons.push('COMPLEX_TIME_OR_DURATION_PRICING');
 if(!ev.published){
  if(ev.hasPublicIdentityMatch)reasons.push('UNPUBLISHED_DESPITE_EXACT_LOCAL_IRVE_ID');
  else if(parentCandidates.length===1)reasons.push('UNPUBLISHED_PARENT_UNIQUE_CANDIDATE');
  else if(!parentCandidates.length&&ev.mapped)reasons.push('NO_DETERMINISTIC_LOCAL_IRVE_MATCH');
  reasons.push('UNPUBLISHED_SOURCE_EVSE');
 }
 const priority=hold27.has(ev.normalizedRef)?0:
  (!ev.published&&gs.size>1&&(ev.hasPublicIdentityMatch||ev.nationalOwnerCount===1))?1:
  (!ev.published&&parentCandidates.length>1)?2:
  (!ev.published&&ev.nationalOwnerCount>1)?3:
  (!ev.published&&ev.hasPublicIdentityMatch)?4:
  (!ev.published&&fullId(ev.normalizedRef)&&ev.locationPkClaimCount>1)?5:
  (!ev.published&&ev.mapped&&ev.hasPrice)?6:
  (!ev.published)?7:99;
 ev.priority=priority;ev.caseReasons=reasons;
 if(!ev.published||priority<99)for(const reason of reasons)count(categoryStats,reason);
 if(!ev.published||priority<99){
  count(priorityStats,'P'+priority);
  count(byOperator,ev.operator);
  count(byStation,ev.stationId||'NO_IRVE_STATION');
  cases.push(ev);
 }
}
cases.sort((a,b)=>a.priority-b.priority||a.stationId.localeCompare(b.stationId)||a.locPk.localeCompare(b.locPk)||a.sourcePk.localeCompare(b.sourcePk));
const manualRows=cases.filter(r=>r.priority<=5);
const simplified=ev=>({
  priority:ev.priority,stationId:ev.stationId,sourceName:ev.sourceName,locPk:ev.locPk,operator:ev.operator,
  sourcePk:ev.sourcePk,evse:ev.physicalReference,connectors:ev.connectorSummary,
  cacheAt:ev.cacheFetchedAt,published:ev.published,reason:ev.caseReasons.join('|'),
  sourcePriceSignature:ev.sourcePriceSignature,sourceTechnicalSignature:ev.sourceTechnicalSignature,nationalOwnerCount:ev.nationalOwnerCount,
  nationalStations:ev.nationalStationIds.join('|'),localPdcCount:ev.localPdcCount,
  parentCandidates:ev.localSamePrefixCandidates,refSources:ev.sourceRefsSameSite
});
const headers=Object.keys(simplified(cases[0]||{priority:0,stationId:'',sourceName:'',locPk:'',operator:'',sourcePk:'',evse:'',connectors:'',cacheAt:'',published:false,reason:'',sourcePriceSignature:'',sourceTechnicalSignature:'',nationalOwnerCount:0,nationalStations:'',localPdcCount:0,parentCandidates:0,refSources:0}));
const csvData=rows=>headers.join(',')+'\n'+rows.map(r=>csvLine(simplified(r))).join('\n')+'\n';
const runAt=new Date().toISOString();
const summary={
 schemaVersion:1,generatedAt:runAt,
 scope:'ALL France Electroverse cached source EVSEs, connector tariffs and current overlay; read-only, non-public not promoted',
 timestamps:{cache:sm.generatedAt,overlay:om.generatedAt,irveStatic:txt((await read('data/national/france-irve-static-v9/manifest.json')).generatedAt),userHoldDate:userHold.recordedDate},
 sourceInventory:{cacheStations:sm.totalStations,cacheSourceEvses:counters.sourceEvses,cacheConnectors:counters.sourceConnectors,overlayOffers:publishedOfferCount,overlayOffersWithExplicitSourcePk:publishedWithSourcePk,overlayUniquePublishedSourcePks:publishedPk.size,overlayUniqueTargetIds:publishedTarget.size,sourceSourceCountDistinct:physicalOwners.size,mappingLocations:mapping.size,nationalEvseIds:irveById.size},
 counters,overlayRejected:om.rejected,overlayStats:{
  publishedOffers:om.stats?.publishedOffers,publishedConnectorCount:om.stats?.publishedConnectorCount,
  conflictingTargetsDropped:om.stats?.conflictingTargetsDropped,connectorPowerVariantEvses:om.stats?.connectorPowerVariantEvses,
  validatedResidualHeterogeneousConnectors:om.stats?.validatedResidualHeterogeneousConnectors
 },
 cases:{rows:cases.length,manualReviewRows:manualRows.length,userHoldUniqueEvse:hold27.size,userHoldSeenInCache:observedHold.size,
  newPotentialDuplicateConflictIds:[...new Set(newConflictCases)].filter(k=>!hold27.has(k)).length,
  diagnosticNote:'New source price variants are evidence flags, not app-confirmed tariff contradictions; reconcile exact station/EVSE identity before manual inspection.',
  categories:categoryStats,byPriority:priorityStats,
  topOperatorCounts:Object.entries(byOperator).sort((a,b)=>b[1]-a[1]).slice(0,30),
  topStationCounts:Object.entries(byStation).sort((a,b)=>b[1]-a[1]).slice(0,20)
 },
 preview:cases.slice(0,60).map(simplified),
 auditLimitations:[
 'The 107 parent ambiguities in overlay manifest count rejected processing events; candidate queue groups by source EVSE and can count differently.',
 'A missing national match or unpublished source EVSE is not proof of conflicting numeric tariffs; physical availability, public access and historical aliases need evidence.',
 'Source inventory tile count is not a priced EVSE count; cached mapped locations are a different universe from all nationwide listing IDs.',
 'Connector-rate exceptions must remain per EVSE/power/plug; do not flatten stations.',
 'Captured app tariffs and live Tariff GraphQL responses are not fetched by this offline audit; use user screenshots or approved future refresh to establish current price.',
 'All pricing inconsistencies remain excluded; this audit does not change publication or override manual ambiguity hold.',
 'Published source PK index is evidence from overlay metadata; missing source PK tags can undercount coverage.'
 ]
};
await fs.writeFile(ROOT+'/summary.json',JSON.stringify(summary,null,2)+'\n');
await fs.writeFile(ROOT+'/top-priority-cases.csv',csvData(cases.slice(0,3000)));
await fs.writeFile(ROOT+'/all-unresolved-cases.json.gz',zlib.gzipSync(Buffer.from(JSON.stringify({generatedAt:runAt,total:cases.length,records:cases.map(simplified)})),{level:6}));
await fs.writeFile(ROOT+'/manual-review.csv.gz',zlib.gzipSync(Buffer.from(csvData(manualRows)),{level:6}));
await fs.writeFile(ROOT+'/evidence-by-source-evse.json.gz',zlib.gzipSync(Buffer.from(JSON.stringify({generatedAt:runAt,records:cases.map(r=>({
 sourcePk:r.sourcePk,locPk:r.locPk,stationId:r.stationId,physicalReference:r.physicalReference,
 sourcePriceSignature:r.sourcePriceSignature,sourceTechnicalSignature:r.sourceTechnicalSignature,connectorPrices:r.sourcePriceComponents,reason:r.caseReasons,
 fetchedAt:r.cacheFetchedAt,tariffHash:r.tariffHash
}))})),{level:6}));
console.log(JSON.stringify({generatedAt:runAt,sourceEvses:counters.sourceEvses,published:counters.publishedSourceEvses,unpublished:counters.unpublishedSourceEvses,queue:cases.length,manual:manualRows.length,categoryStats,byPriority:priorityStats,excludedByOverlay:om.rejected},null,2));
