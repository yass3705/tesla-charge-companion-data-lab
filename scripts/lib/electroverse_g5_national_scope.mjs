/**
 * TCC V9 G5: fail-closed overlay *projection* on the source-location
 * national mapping. Never mutate the official master or raw tariffs.
 *
 * Historical IRVE/charge-point operator names can differ from Electroverse
 * operator codes (e.g. Power Dot France vs PD1); this narrow safeguard does
 * NOT claim independent operator conformity or an approved GPS fallback.
 */
export const nationalNorm = x => String(x ?? '').trim().toUpperCase().replace(/[^A-Z0-9]/g, '');

const foreignBelgiumSource = row => {
  const site = nationalNorm(row?.irveStationId);
  const pdcs = row?.irvePdcIds;
  const lat = Number(row?.irve?.lat), lon = Number(row?.irve?.lon);
  // Source-mapped BE station and BE EVSE IDs, at documented BE coordinates.
  // Do not exclude a French site merely because the operator uses ES/DK
  // identifiers or its station ID is the regional 'MEL...' convention.
  return site.startsWith('BE') && Array.isArray(pdcs) && pdcs.length > 0 &&
    pdcs.every(p => nationalNorm(p).startsWith('BE')) &&
    Number.isFinite(lat) && Number.isFinite(lon) &&
    lat >= 49.45 && lat <= 51.65 && lon >= 2.5 && lon <= 6.5;
};

export function buildElectroverseNationalScopeIndex(mappings) {
  if(!Array.isArray(mappings))throw Error('National mapping entries required');
  const byLocation=new Map();
  for(const row of mappings) {
    const key=String(row?.electroverseLocationPk ?? '');
    if(!key || byLocation.has(key))throw Error('Duplicate or absent Electroverse location mapping: '+key);
    const pdcs=row?.irvePdcIds;
    if(!Array.isArray(pdcs))throw Error('Invalid mapped national PDC list: '+key);
    byLocation.set(key,{
      stationId:row?.irveStationId ?? null,
      operator:row?.irve?.operator ?? null,
      countryEvidence:foreignBelgiumSource(row)?'foreign_belgium':'not_independently_asserted',
      targetIds:new Set(pdcs.map(nationalNorm).filter(Boolean)),
      locationPk:key,
    });
  }
  return byLocation;
}

export function classifyElectroverseNationalOffer(offer,index) {
  const locationPk=String(offer?.metadata?.electroverseLocationPk ?? '');
  const row=index.get(locationPk);
  if(!row)return {ok:false,reason:'no_source_location_in_national_mapping',locationPk};
  const targets=offer?.evseIds;
  if(!Array.isArray(targets)||targets.length===0 || targets.some(x=>!nationalNorm(x)))
    return {ok:false,reason:'missing_official_evse_target',locationPk};
  if(row.countryEvidence==='foreign_belgium')
    return {ok:false,reason:'confirmed_foreign_belgium_site_in_france_overlay',locationPk};
  const badTargets=targets.filter(t=>!row.targetIds.has(nationalNorm(t)));
  if(badTargets.length)
    return {ok:false,reason:'target_not_in_source_location_national_pdcs',locationPk,
      targets:badTargets,stationId:row.stationId};
  return {ok:true,reason:'source_location_target_membership_confirmed',
    locationPk,stationId:row.stationId,
    operatorProof:'requires_separate_operator_and_matching_method_audit'};
}

export function screenElectroverseG5NationalOffers(tileMap,mappings) {
  if(!(tileMap instanceof Map))throw Error('Tile map required');
  const index=buildElectroverseNationalScopeIndex(mappings);
  const byReason={}, samples=[],filtered=new Map();
  let reviewed=0,quarantined=0,withOperatorName=0;
  for(const [tile,offers] of tileMap) {
    if(!Array.isArray(offers))throw Error('Invalid offer tile: '+tile);
    const keep=[];
    for(const offer of offers) {
      reviewed++;
      const check=classifyElectroverseNationalOffer(offer,index);
      if(check.ok){
        keep.push(offer);
        if(index.get(check.locationPk).operator)withOperatorName++;
      } else {
        quarantined++;
        byReason[check.reason]=(byReason[check.reason]||0)+1;
        if(samples.length<80)samples.push({
          offerId:offer?.id??null,reason:check.reason,
          locationPk:check.locationPk,stationId:check.stationId??null,
          unresolvedTargets:check.targets??null,
        });
      }
    }
    filtered.set(tile,keep);
  }
  return {
    tiles:filtered,
    report:{
      reviewedOffers:reviewed,retainedOffers:reviewed-quarantined,
      quarantinedOffers:quarantined,quarantinedByReason:byReason,
      quarantinedSamples:samples,
      retainedOffersWithMappedOperatorName:withOperatorName,
      operatorIndependentMatchVerified:false,
      fallbackGpsAddressOperatorVerified:false,
      scope:'France Electroverse overlay only; national master/raw intact',
    },
  };
}
