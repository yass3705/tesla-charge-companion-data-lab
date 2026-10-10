import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const base='data/platforms/electra/france/';
const norm=x=>String(x??'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const load=async p=>JSON.parse(zlib.gunzipSync(await fs.readFile(p)).toString('utf8'));
const [residual,source,manifest]=await Promise.all([load(base+'residuals.json.gz'),load(base+'source-locations.json.gz'),fs.readFile(base+'manifest.json','utf8').then(JSON.parse)]);
const locById=new Map((source.locations||[]).map(x=>[String(x.id),x]));
const national=await load('data/national/france-irve-static-v9/all.json.gz');
const powerByEvse=new Map();
for(const row of national)for(const cfg of row?.[8]||[])for(const pdc of cfg?.[6]||[]){
 const k=norm(pdc),kw=Number(cfg?.[3]);if(!Number.isFinite(kw)||kw<=0)continue;
 const prev=powerByEvse.get(k);powerByEvse.set(k,prev==null?kw:prev===kw?kw:null);
}
const tariffPowerScope=t=>{
 const restrictions=(t.elements||[]).map(e=>e?.restrictions||{});
 if(!restrictions.length||restrictions.some(r=>r.minPower==null&&r.maxPower==null))return null;
 const lo=Math.max(...restrictions.map(r=>r.minPower==null?0:Number(r.minPower)));
 const hi=Math.min(...restrictions.map(r=>r.maxPower==null?Infinity:Number(r.maxPower)));
 return lo<=hi?{lo,hi}:null;
};
const count=(map,key)=>map[key]=(map[key]||0)+1;
const compType=x=>String(x?.type||'MISSING').toUpperCase();
const supported=new Set(['ENERGY','TIME','FLAT','PARKING_TIME','CONGESTION_TIME']);
const cases=[],blockedBy={},components={},restrictions={},heteroReasons={},reasons={};
for(const row of residual.locations||[]){
  if(!['unsupported_tariff','heterogeneous_location_tariffs','tariff_attribution_missing_evse_evidence','same_power_tariff_assignment_ambiguous','verified_app_partial_attribution_pending'].includes(row.reason))continue;
  count(reasons,row.reason);
  const loc=locById.get(String(row.electraLocationId));
  const tariff=loc?.chargeTariffs||[],issues=new Set(),types=new Set(),restrictionFields=new Set(),tariffSignatures=new Set(),tariffDetails=[];
  for(const t of tariff){
    const sections=[],tsign=[];
    for(const e of t.elements||[]){
      const rr=e.restrictions||{},pcs=e.priceComponents||[];
      for(const [k,v] of Object.entries(rr))if(v!=null&&v!==''&&!(Array.isArray(v)&&!v.length)){restrictionFields.add(k);count(restrictions,k);}
      const min=Number(rr.minDuration);
      const dims=[];
      for(const pc of pcs){
        const k=compType(pc),n=Number(pc.price);types.add(k);count(components,k);
        if(!supported.has(k))issues.add('unknown_component:'+k);
        if(!Number.isFinite(n)||n<0)issues.add('invalid_component_price');
        if(k==='CONGESTION_TIME'&&Number.isFinite(min)&&min>0)issues.add('congestion_duration_band_supported');
        dims.push([k,n]);
      }
      if(!pcs.length)issues.add('empty_tariff_element');
      const s=JSON.stringify({r:rr,p:dims});sections.push(s);tsign.push(s);
    }
    if(!sections.length)issues.add('tariff_without_elements');
    const sig=JSON.stringify(tsign);
    tariffSignatures.add(sig);
    tariffDetails.push({tariffId:t.chargeTariffId||t.id||null,currency:t.currency,
      sections:tsign.slice(0,8),components:[...types]});
  }
  if(row.reason==='unsupported_tariff'&&issues.size===0)issues.add('other_compiler_restriction');
  if(['heterogeneous_location_tariffs','tariff_attribution_missing_evse_evidence','same_power_tariff_assignment_ambiguous','verified_app_partial_attribution_pending'].includes(row.reason)){
    if(tariff.length>1&&tariffSignatures.size>1)count(heteroReasons,'different_tariff_rules_at_location');
    else if(tariff.length>1)count(heteroReasons,'same_raw_tariff_different_compilation');
    else count(heteroReasons,'single_tariff_compilation_mismatch');
  }
  for(const issue of issues)if(issue!=='congestion_duration_band_supported')count(blockedBy,issue);
  const knownPowerGroups={};
  const pendingEVSEs=row.reason==='verified_app_partial_attribution_pending'?(row.evses||[]):(loc?.evses||[]);
  for(const id of pendingEVSEs.map(e=>e.evseId).filter(Boolean)){
    const kw=powerByEvse.get(norm(id));const label=kw==null?'unknown':String(kw);
    (knownPowerGroups[label]??=[]).push(id);
  }
  let provenSamePowerConflict=false,missingPowerEvidence=false;
  const scopes=tariff.map(tariffPowerScope);
  if(scopes.some(x=>!x))missingPowerEvidence=true;
  for(const [kwLabel,evseIds] of Object.entries(knownPowerGroups)){
    if(kwLabel==='unknown'){missingPowerEvidence=true;continue;}
    const power=Number(kwLabel),hits=scopes.map((v,i)=>({v,i})).filter(x=>x.v&&power>=x.v.lo&&power<=x.v.hi);
    const distinct=new Set(hits.map(x=>JSON.stringify((tariff[x.i]?.elements||[]).map(e=>({r:e.restrictions||{},p:(e.priceComponents||[]).map(p=>[compType(p),Number(p.price)])})))));
    if(evseIds.length>=2&&distinct.size>1)provenSamePowerConflict=true;
  }
  // No EVSE -> tariff linkage is exposed by the location-based source.
  // Do not count different station tariffs as a confirmed same-power issue.
  const verdict=provenSamePowerConflict?'same_power_tariff_conflict_evidenced':
      missingPowerEvidence?'tariff_evse_attribution_not_proven':'power_scoped_tariffs_pending_final_validation';
  const item={locationId:String(row.electraLocationId),name:row.name,cpo:row.cpo,powerGroups:knownPowerGroups,samePowerVerdict:verdict,provenSamePowerConflict,missingPowerEvidence,
    reason:row.reason,evseCount:pendingEVSEs.length,
    tariffCount:tariff.length,tariffSignatureCount:tariffSignatures.size,
    components:[...types].sort(),restrictionFields:[...restrictionFields].sort(),issues:[...issues],
    evseIds:pendingEVSEs.map(e=>e.evseId).filter(Boolean),
    examples:tariffDetails.slice(0,3)};
  // Triage by observed station/EVSE evidence. These diagnostics must never
  // substitute a price-to-EVSE attribution when the platform omits that link.
  const validPowers=Object.keys(knownPowerGroups).filter(x=>x!=='unknown');
  const unknownPowerEvses=(knownPowerGroups.unknown||[]).length;
  const distinctPowerCount=validPowers.length;
  const matchedSourceEvses=Object.values(knownPowerGroups).reduce((n,ids)=>n+ids.length,0);
  const componentFingerprint=t=>JSON.stringify((t.elements||[]).flatMap(el=>(el.priceComponents||[])
    .map(pc=>[compType(pc),Number(pc.price)]).filter(([k])=>k==='ENERGY')).sort());
  const nonEnergyFingerprint=t=>JSON.stringify((t.elements||[]).flatMap(el=>(el.priceComponents||[])
    .map(pc=>[compType(pc),Number(pc.price)]).filter(([k])=>k!=='ENERGY')).sort());
  const restrictionFingerprint=t=>JSON.stringify((t.elements||[]).map(el=>el.restrictions||{}).map(r=>JSON.stringify(r)).sort());
  const energyVariantCount=new Set(tariff.map(componentFingerprint)).size;
  const ancillaryVariantCount=new Set(tariff.map(nonEnergyFingerprint)).size;
  const restrictionVariantCount=new Set(tariff.map(restrictionFingerprint)).size;
  const scopeCoverage=scopes.filter(Boolean).length;
  const exclusivePowerAssignment=scopeCoverage===tariff.length&&matchedSourceEvses>0&&
    unknownPowerEvses===0&&Object.entries(knownPowerGroups).every(([kw])=>{
      const p=Number(kw);return scopes.filter(r=>p>=r.lo&&p<=r.hi).length===1;
    });
  const triageClass=exclusivePowerAssignment?'power_scopes_unique_rebuild_required':
    matchedSourceEvses===0?'no_source_evse_ids':
    unknownPowerEvses===matchedSourceEvses?'all_evse_powers_unknown':
    unknownPowerEvses>0?'some_evse_powers_unknown':
    distinctPowerCount===1?'single_known_power_without_tariff_mapping':
    'multiple_known_powers_without_tariff_mapping';
  item.triage={class:triageClass,sourceEvseCount:matchedSourceEvses,
    knownPowerCount:matchedSourceEvses-unknownPowerEvses,unknownPowerCount:unknownPowerEvses,
    distinctKnownPowers:validPowers.map(Number).sort((a,b)=>a-b),
    energyPriceVariation:energyVariantCount>1,ancillaryPriceVariation:ancillaryVariantCount>1,
    restrictionVariation:restrictionVariantCount>1,
    distinctEnergyFingerprints:energyVariantCount,distinctAncillaryFingerprints:ancillaryVariantCount,
    distinctRestrictionFingerprints:restrictionVariantCount,
    tariffPowerScopeCount:scopeCoverage,exclusivePowerAssignment,
    missingSourceEvseTariffLink:true,decision:'hold_electra_emsp_price_unattributed',
    nextEvidence:'operator EVSE/connector-to-chargeTariffId linkage or documented exclusive tariff power restriction'};
  cases.push(item);
}
const triageCounts={},triageByCpo={},variantCounts={energyPriceVariation:0,ancillaryPriceVariation:0,restrictionVariation:0,exclusivePowerAssignment:0,singleEvse:0,unknownPowerEvses:0,sourceEvseIds:0};
for(const item of cases){
  const x=item.triage,cls=x.class;
  count(triageCounts,cls);
  const c=triageByCpo[item.cpo]??={total:0,classes:{},energyPriceVariation:0,ancillaryPriceVariation:0,restrictionVariation:0,unknownPowerEvses:0};
  c.total++;count(c.classes,cls);
  if(x.energyPriceVariation){c.energyPriceVariation++;variantCounts.energyPriceVariation++;}
  if(x.ancillaryPriceVariation){c.ancillaryPriceVariation++;variantCounts.ancillaryPriceVariation++;}
  if(x.restrictionVariation){c.restrictionVariation++;variantCounts.restrictionVariation++;}
  if(x.exclusivePowerAssignment)variantCounts.exclusivePowerAssignment++;
  c.unknownPowerEvses+=x.unknownPowerCount;
  if(x.sourceEvseCount===1)variantCounts.singleEvse++;
  variantCounts.unknownPowerEvses+=x.unknownPowerCount;
  variantCounts.sourceEvseIds+=x.sourceEvseCount;
}
const rankedCpo=Object.fromEntries(Object.entries(triageByCpo).sort((a,b)=>b[1].total-a[1].total));
const summary={schemaVersion:2,generatedAt:new Date().toISOString(),sourceGeneratedAt:manifest.generatedAt,
  counts:{total:cases.length,unsupported:cases.filter(x=>x.reason==='unsupported_tariff').length,
    heterogeneous:cases.filter(x=>['heterogeneous_location_tariffs','tariff_attribution_missing_evse_evidence','same_power_tariff_assignment_ambiguous','verified_app_partial_attribution_pending'].includes(x.reason)).length,
    evidenceRequired:cases.filter(x=>x.missingPowerEvidence).length,
    verifiedPartialLocations:cases.filter(x=>x.reason==='verified_app_partial_attribution_pending').length,
    verifiedAppPublishedEvseOffers:manifest.stats?.verifiedAppEvseOffers??0,
    trueSamePowerConflicts:cases.filter(x=>x.provenSamePowerConflict).length,
    congestionDurationSupported:cases.filter(x=>x.issues.includes('congestion_duration_band_supported')).length},
  residualReasonCounts:manifest.rejected||{},auditedReasonCounts:reasons,
  snapshotStats:{publishedLocations:manifest.stats?.publishedLocations,publishedEvseIds:manifest.stats?.publishedEvseIds,publishedOffers:manifest.stats?.publishedOffers,retainedUnmatchedLocations:manifest.stats?.retainedUnmatchedLocations},
  unresolvedKinds:blockedBy,componentTypes:components,restrictionFields:restrictions,
  triage:{classificationCounts:triageCounts,variationCounts:variantCounts,
    eligibleForAutomaticPublication:0,alreadyPublishedThroughVerifiedAppEvidence:manifest.stats?.verifiedAppEvseOffers??0,
    reason:'Remaining unmatched EVSE have no proven tariff assignment; manually verified EVSE counted separately.'},
  triageByCpo:rankedCpo,
  sampleTriage:cases.slice(0,24).map(({locationId,name,cpo,triage})=>({locationId,name,cpo,triage})),
  heterogeneousPatterns:heteroReasons,
  sampleUnsupported:cases.filter(x=>x.reason==='unsupported_tariff').slice(0,30),
  sampleHeterogeneous:cases.filter(x=>['heterogeneous_location_tariffs','tariff_attribution_missing_evse_evidence','same_power_tariff_assignment_ambiguous','verified_app_partial_attribution_pending'].includes(x.reason)).slice(0,20),
  caseArchive:'reports/france/irve/electra-pricing-residual-cases-2026-10-08.json.gz',
  decisionPolicy:'Tariffs belong to exact EVSE; different prices across distinct powers in the same station are expected. Count a same-power conflict only where explicit EVSE-to-tariff evidence proves it. SOC80 congestion and explicit duration bounds are supported; retain fail-closed unknown associations.'
};
await fs.mkdir('reports/france/irve',{recursive:true});
await fs.writeFile('reports/france/irve/electra-pricing-residual-audit-2026-10-08.json',JSON.stringify(summary,null,2)+'\n');
await fs.writeFile(summary.caseArchive,zlib.gzipSync(Buffer.from(JSON.stringify({schemaVersion:2,cases})),{level:9}));
// One row per blocked location for human verification (not a publishable tariff).
// Use a UTF-8 BOM so Excel opens accented French station and CPO names correctly.
const queuePath='reports/france/irve/electra-pricing-action-queue-latest.csv';
const fields=['locationId','name','cpo','triageClass','sourceEvseCount','knownPowerCount','unknownPowerCount',
 'distinctKnownPowersKw','evseIds','tariffCount','tariffSignatureCount','energyPriceVariation',
 'ancillaryPriceVariation','restrictionVariation','verifiedSamePowerConflict','decision','missingEvidence'];
const quoteCsv=x=>{const v=String(x??'');return v.includes('"')||v.includes(';')||v.includes(String.fromCharCode(10))||v.includes(String.fromCharCode(13))?'"'+v.replaceAll('"','""')+'"':v;};
const queue=[fields.join(';')];
for(const c of cases){const t=c.triage;const r={locationId:c.locationId,name:c.name,cpo:c.cpo,
 triageClass:t.class,sourceEvseCount:t.sourceEvseCount,knownPowerCount:t.knownPowerCount,
 unknownPowerCount:t.unknownPowerCount,distinctKnownPowersKw:t.distinctKnownPowers.join('|'),
 evseIds:c.evseIds.join('|'),tariffCount:c.tariffCount,tariffSignatureCount:c.tariffSignatureCount,
 energyPriceVariation:t.energyPriceVariation,ancillaryPriceVariation:t.ancillaryPriceVariation,
 restrictionVariation:t.restrictionVariation,verifiedSamePowerConflict:c.provenSamePowerConflict,
 decision:t.decision,missingEvidence:t.nextEvidence};
 queue.push(fields.map(k=>quoteCsv(r[k])).join(';'));
}
if(queue.length!==cases.length+1)throw new Error('Electra queue count mismatch');
await fs.writeFile(queuePath,String.fromCharCode(0xFEFF)+queue.join(String.fromCharCode(10))+String.fromCharCode(10),'utf8');
console.log(JSON.stringify({generatedAt:summary.generatedAt,counts:summary.counts,unresolvedKinds:summary.unresolvedKinds,
 heterogeneousPatterns:heteroReasons,componentTypes:components,restrictionFields:restrictions,triage:summary.triage,topCpos:Object.entries(rankedCpo).slice(0,12),
 sampleUnsupported:summary.sampleUnsupported.slice(0,5).map(x=>({name:x.name,cpo:x.cpo,issues:x.issues,components:x.components,restrictions:x.restrictionFields}))}));
