/**
 * G5 independent evidence review, not an operator-name crosswalk.
 *
 * Provider operatorId is numeric; IRVE operator is free text. A statistical
 * majority or similar spelling CANNOT establish supplier/operator equality.
 * Existing spatial mutual-nearest mapping allowed up to 15 metres: distances
 * over 10m require a separate exact-ID proof or a reviewed address/GPS +
 * operator + EVSE-scope decision. Neither is assumed by this audit.
 */
export const normG5Id = value => String(value ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '');
export const normG5Name = value => String(value ?? '')
  .normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toUpperCase()
  .replace(/[^A-Z0-9]/g, '');

export function classifyG5Evidence(offer, mapping, officialTechnical=new Map()) {
  const md=offer?.metadata || {};
  const locationPk=String(md.electroverseLocationPk ?? '');
  const row=mapping?.get(locationPk);
  if(!row) return {locationPk,status:'missing_source_location',exactSourcePdc:false};
  const targets=(Array.isArray(offer.evseIds)?offer.evseIds:[]).map(normG5Id).filter(Boolean);
  const refs=[...(Array.isArray(md.physicalReferences)?md.physicalReferences:[]),md.physicalReference]
    .filter(x=>x!=null).map(normG5Id).filter(Boolean);
  const exactSourcePdc=targets.length>0 && targets.every(t=>refs.includes(t));
  const distance=row.evidence?.distanceM;
  const beyond10m=typeof distance==='number' && Number.isFinite(distance) && distance>10;
  const supplierOperatorId=String(row.electroverse?.operatorId??'');
  const nationalOperator=String(row.irve?.operator??'');
  // An exact source EVSE ID can establish the target regardless of an older
  // GPS-to-station tolerance, but it does not validate the supplier CPO ID.
  const isDocumentedPD1Group=md.identityMode==='strict_pd1_official_technical_homogeneous_group' &&
    normG5Name(row.irve?.operator)==='POWERDOTFRANCE' && md.operator==='PD1' &&
    String(md.source??'').includes('Powerdot official technical inventory');
  const metadataPlugTypes=(Array.isArray(md.plugTypes)?md.plugTypes:[]).map(normG5Id);
  const officialTechnicalIdentityProved=!exactSourcePdc && isDocumentedPD1Group &&
    targets.length>0 && metadataPlugTypes.length>0 &&
    Number.isFinite(Number(md.powerKwClass)) &&
    targets.every(t=>{
      const row=officialTechnical.get(t);
      return row && Number(row.powerKw)===Number(md.powerKwClass) &&
        Array.isArray(row.plugs) &&
        row.plugs.map(normG5Id).some(p=>metadataPlugTypes.includes(p));
    });
  const identityEvidence=exactSourcePdc?'exact_source_pdc_id':
    officialTechnicalIdentityProved?'official_powerdot_inventory_target_power_and_plug':
    isDocumentedPD1Group?'claimed_official_technical_group_needs_independent_review':
    'indirect_method_needs_review';
  return {
    locationPk,
    distanceM:typeof distance==='number'?distance:null,
    beyond10m,
    stationId:String(row.irveStationId??''),
    stationName:row.irve?.name??null,
    matchMethod:row.matchMethod??null,
    supplierOperatorId,
    nationalOperator,
    nationalOperatorPresent:!!normG5Name(nationalOperator),
    exactSourcePdc,
    officialTechnicalIdentityProved,
    identityEvidence,
    identityMode:md.identityMode??'UNKNOWN',
    offerId:String(offer.id??''),
    evseTargets:offer.evseIds??[],
    sourcePhysicalReferences:[...(Array.isArray(md.physicalReferences)?md.physicalReferences:[]),
      ...(md.physicalReference!=null?[md.physicalReference]:[])],
    operatorEquivalence:'NOT_INDEPENDENTLY_PROVED',
    gpsDecision:beyond10m?(exactSourcePdc?
      'EXACT_SOURCE_PDC_EVIDENCE_OPERATOR_PENDING':
      'REQUIRES_INDEPENDENT_OPERATOR_AND_ADDRESS_OR_GPS_PROOF'):
      'WITHIN_SOURCE_DISTANCE_OR_NOT_APPLICABLE',
  };
}

export function auditG5OperatorGps(offers, mappings, officialTechnicalRows=[]) {
  if(!Array.isArray(mappings)||!Array.isArray(offers))
    throw Error('G5 audit requires source mappings and final offers');
  const map=new Map();
  for(const row of mappings){
    const key=String(row?.electroverseLocationPk??'');
    if(!key||map.has(key))throw Error('G5 duplicate or missing source location mapping '+key);
    map.set(key,row);
  }
  const technical=new Map(officialTechnicalRows.map(x=>[normG5Id(x.evseId),x]));
  const byOperatorId=new Map(),locationReviews=new Map(),modes={};
  const bad=[],pairCounts=new Map();
  let outlierOfferCount=0,exactOutlierOfferCount=0,indirectOutlierOfferCount=0;
  let technicallyCorroboratedOutlierOffers=0,indirectStillUnprovedOutlierOffers=0;
  let missingSupplierOperatorId=0,missingNationalOperator=0;
  for(const offer of offers){
    const evidence=classifyG5Evidence(offer,map,technical);
    if(evidence.status==='missing_source_location'){bad.push(evidence);continue;}
    if(!evidence.supplierOperatorId)missingSupplierOperatorId++;
    if(!evidence.nationalOperatorPresent)missingNationalOperator++;
    const k=evidence.supplierOperatorId;
    const labelKey=normG5Name(evidence.nationalOperator)||'__MISSING__';
    const labels=byOperatorId.get(k)||new Map();
    labels.set(labelKey,(labels.get(labelKey)||0)+1);
    byOperatorId.set(k,labels);
    const pkey=k+'|'+labelKey;
    pairCounts.set(pkey,(pairCounts.get(pkey)||0)+1);
    if(!evidence.beyond10m)continue;
    outlierOfferCount++;
    if(evidence.exactSourcePdc)exactOutlierOfferCount++;
    else {
      indirectOutlierOfferCount++;
      if(evidence.officialTechnicalIdentityProved)technicallyCorroboratedOutlierOffers++;
      else indirectStillUnprovedOutlierOffers++;
    }
    modes[evidence.identityMode]=(modes[evidence.identityMode]||0)+1;
    let l=locationReviews.get(evidence.locationPk);
    if(!l){
      l={
        locationPk:evidence.locationPk,stationId:evidence.stationId,
        stationName:evidence.stationName,distanceM:evidence.distanceM,
        sourceMatchMethod:evidence.matchMethod,
        supplierOperatorId:evidence.supplierOperatorId,
        nationalOperator:evidence.nationalOperator,
        offers:0,exactPdcOffers:0,indirectOffers:0,
        corroboratedTechnicalOffers:0,indirectUnprovenOffers:0,
        identityModes:{},
        sampleIndirectOffers:[],
        proofGate:'G5_OPERATOR_PROOF_REQUIRED',
      };
      locationReviews.set(evidence.locationPk,l);
    }
    l.offers++;l.identityModes[evidence.identityMode]=(l.identityModes[evidence.identityMode]||0)+1;
    if(evidence.exactSourcePdc)l.exactPdcOffers++;
    else {
      l.indirectOffers++;
      if(evidence.officialTechnicalIdentityProved)l.corroboratedTechnicalOffers++;
      else l.indirectUnprovenOffers++;
      if(l.sampleIndirectOffers.length<4)l.sampleIndirectOffers.push({
        id:evidence.offerId,targets:evidence.evseTargets,
        physicalReferences:evidence.sourcePhysicalReferences,
        mode:evidence.identityMode,identityEvidence:evidence.identityEvidence,
      });
    }
  }
  const operatorDiagnostics=[];
  let multiLabelOperatorIds=0;
  for(const [id,labels] of byOperatorId){
    if(labels.size>1)multiLabelOperatorIds++;
    const ranked=[...labels.entries()].sort((a,b)=>b[1]-a[1]);
    operatorDiagnostics.push({
      supplierOperatorId:id,
      unverifiedSourceToNationalLabelPairs:ranked.map(([name,offers])=>({nationalLabelNormalized:name,offers})),
      multipleLabels:labels.size>1,
      // A dominant pair is a statistical diagnostic, never an operator crosswalk.
      independentCpoProof:false,
    });
  }
  operatorDiagnostics.sort((a,b)=>
    b.unverifiedSourceToNationalLabelPairs.reduce((n,x)=>n+x.offers,0)-
    a.unverifiedSourceToNationalLabelPairs.reduce((n,x)=>n+x.offers,0));
  const review=[...locationReviews.values()].sort((a,b)=>b.distanceM-a.distanceM||
    a.locationPk.localeCompare(b.locationPk));
  const outliersWithMixedOperatorLabels=review.filter(l=>byOperatorId.get(l.supplierOperatorId)?.size>1);
  return {
    schemaVersion:1,source:'immutable_national_mapping_plus_built_electroverse_overlay',
    overallOfferCount:offers.length,
    mappingLocationCount:map.size,
    missingMappingOffers:bad.length,
    supplierOperatorIdMissingOffers:missingSupplierOperatorId,
    nationalOperatorNameMissingOffers:missingNationalOperator,
    uniqueSupplierOperatorIds:byOperatorId.size,
    supplierIdsWithSeveralNationalOperatorLabels:multiLabelOperatorIds,
    operatorIndependentCrosswalkValidated:false,
    sourceOperatorPairsAreStatisticalNotProof:true,
    sourceHistoricalMatchPolicy:'spatial_mutual_nearest_v1_max_15m',
    reviewedDistanceLimitM:10,
    distanceOutlierLocationCount:review.length,
    distanceOutlierOfferCount:outlierOfferCount,
    exactSourceIdOutlierOfferCount:exactOutlierOfferCount,
    indirectOutlierOfferCount:indirectOutlierOfferCount,
    technicallyCorroboratedOutlierOffers,
    indirectStillUnprovedOutlierOffers,
    locationsWithIndirectStillUnproven:review.filter(x=>x.indirectUnprovenOffers>0).length,
    locationsAllExactSourcePdc:review.filter(x=>x.indirectOffers===0).length,
    locationsWithIndirectUnprovenOffers:review.filter(x=>x.indirectOffers>0).length,
    outlierLocationsWithMultiLabelSupplierId:outliersWithMixedOperatorLabels.length,
    outlierOffersWithMultiLabelSupplierId:outliersWithMixedOperatorLabels.reduce((s,r)=>s+r.offers,0),
    outlierIdentityModes:modes,
    outliers:review,
    operatorLabelDiagnostics:operatorDiagnostics,
    missingMappingSamples:bad.slice(0,30),
    g5Overall:'PARTIAL_OPERATOR_EQUIVALENCE_AND_NONEXACT_DISTANCE_EVIDENCE_NOT_PROVEN',
  };
}

/**
 * Reversible G5 fail-closed *tariff overlay* projection. For source mappings
 * older than the G5 10m policy, do not publish an INDIRECT supplier price
 * without an independently corroborating source→national EVSE technical identity.
 * Exact supplier EVSE IDs and officially corroborated Powerdot target+power+plug
 * can be retained, subject to the still-open separate operator proof gate.
 *
 * The raw tariff cache and national base are NEVER changed. Preserve every
 * quarantined offer's target/reason in the manifest for a future
 * "Tarif incalculable" diagnostic and reversible reinstatement.
 */
export function screenG5HighDistanceWithoutProof(tiles,mappings,officialTechnicalRows=[]) {
  if(!(tiles instanceof Map)||!Array.isArray(mappings))
    throw Error('G5 overlay tiles and immutable national map required');
  const map=new Map();
  for(const row of mappings) {
    const loc=String(row?.electroverseLocationPk??'');
    if(!loc||map.has(loc))throw Error('G5 duplicate source location '+loc);
    map.set(loc,row);
  }
  const technical=new Map(officialTechnicalRows.map(x=>[normG5Id(x.evseId),x]));
  const kept=new Map(),quarantined=[],byIdentityMode={};
  let checked=0,exactPreservedBeyond10m=0,officialTechnicalPreservedBeyond10m=0;
  for(const [tile,offers] of tiles) {
    const keep=[];
    for(const offer of offers) {
      const decision=classifyG5Evidence(offer,map,technical);
      checked++;
      if(decision.status==='missing_source_location')
        throw Error('G5 missing national source location in high-distance screen: '+decision.locationPk);
      const lacksProof=decision.beyond10m &&
        !decision.exactSourcePdc && !decision.officialTechnicalIdentityProved;
      if(lacksProof){
        byIdentityMode[decision.identityMode]=(byIdentityMode[decision.identityMode]||0)+1;
        quarantined.push({
          offerId:decision.offerId,locationPk:decision.locationPk,
          nationalStationId:decision.stationId,distanceM:decision.distanceM,
          targetPdcIds:decision.evseTargets,identityMode:decision.identityMode,
          supplierOperatorId:decision.supplierOperatorId,
          nationalOperator:decision.nationalOperator,
          reason:'distance_over_10m_without_independent_source_evse_proof',
          proposedResult:'Tarif incalculable',
        });
      }else{
        keep.push(offer);
        if(decision.beyond10m){
          if(decision.exactSourcePdc)exactPreservedBeyond10m++;
          else if(decision.officialTechnicalIdentityProved)officialTechnicalPreservedBeyond10m++;
        }
      }
    }
    kept.set(tile,keep);
  }
  return {
    tiles:kept,
    report:{
      checkedOffers:checked,retainedOffers:checked-quarantined.length,
      quarantinedOffers:quarantined.length,
      quarantinedLocations:new Set(quarantined.map(x=>x.locationPk)).size,
      byIdentityMode,
      exactPreservedBeyond10m,
      officialTechnicalPreservedBeyond10m,
      quarantine:quarantined,
      independentlyVerifiedOperatorCrosswalk:false,
      status:'G5_PARTIAL_OPERATOR_EQUIVALENCE_UNVERIFIED',
      policy:'Excludes only indirect >10m offers without official target identity+power+plug; raw/national master unchanged',
    },
  };
}
