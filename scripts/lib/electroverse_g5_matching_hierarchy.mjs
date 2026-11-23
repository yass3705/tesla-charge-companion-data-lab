/**
 * G5 diagnostic ONLY. A documented numeric supplier operator ID is not a
 * CPO crosswalk; a matching brand name/EVSE prefix or a majority is not proof.
 * This module NEVER changes the tariff overlay or promotes an offer.
 */
const id = v => String(v ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '');
const name = v => String(v ?? '').normalize('NFKD')
  .replace(/[\u0300-\u036f]/g, '').toUpperCase().replace(/[^A-Z0-9]/g, '');
const isoDay = v => typeof v === 'string' && /^20\d{2}-[01]\d-[0-3]\d$/.test(v);
const unresolved = (reason, context={}) => ({
  classification:'unmatched/ambiguous',assignable:false,reason,...context,
});

/**
 * Registry accepts ONLY explicit, independently reviewed supplier-to-national
 * operator evidence. Strings and counts from the mapping being tested are
 * not independent evidence. Source URLs/IDs and review decision must be kept.
 * Registry entries are statements of REVIEW, not self-verifying web links.
 */
export function compileG5CpoProofs(registry) {
  if (registry?.schemaVersion !== 1 || !Array.isArray(registry.approvedPairs))
    throw Error('G5 requires a versioned reviewed operator evidence registry');
  const pairs=new Map();
  for (const p of registry.approvedPairs) {
    const supplier=String(p?.supplierOperatorId ?? '');
    const national=name(p?.nationalOperator);
    const ev=p?.evidence;
    if (!/^\d+$/.test(supplier) || !national || p.country!=='FR' ||
        p.reviewStatus!=='INDEPENDENT_REVIEW_APPROVED' ||
        !isoDay(p.reviewedAt) || ev?.kind!=='explicit_supplier_operator_to_cpo_link' ||
        !ev?.supplierRecord || !ev?.nationalRecord ||
        ev.supplierRecord===ev.nationalRecord ||
        !ev?.sourceOperatorIdExplicit || !ev?.nationalCpoIdentityExplicit)
      throw Error('G5 unproved operator crosswalk cannot be approved: '+supplier);
    const key=supplier+'|'+national;
    if (pairs.has(key))throw Error('G5 duplicate independent crosswalk: '+key);
    pairs.set(key,{supplierOperatorId:supplier,nationalOperatorNormalized:national,
      country:'FR',evidence:ev,reviewedAt:p.reviewedAt});
  }
  return pairs;
}

/**
 * Exact physical source EVSE identity takes priority over spatial evidence.
 * Operator equality is separately required. For a fallback, a documented
 * site binding alone is insufficient: each offered target needs a reviewed
 * EVSE/connector/power/price-scope binding, with unique candidate ownership.
 *
 * Options are externally reviewed candidate/technical proofs, NOT values
 * inferred from a common brand name or a nearest-neighbour result.
 */
export function classifyG5MatchHierarchy(offer, mapping, reviewedPairs, options={}) {
  const loc=String(offer?.metadata?.electroverseLocationPk ?? '');
  if (!mapping || String(mapping.electroverseLocationPk ?? '')!==loc)
    return unresolved('missing_exact_source_location',{locationPk:loc});
  const supplier=String(mapping.electroverse?.operatorId ?? '');
  const national=name(mapping.irve?.operator);
  const pair=reviewedPairs?.get(supplier+'|'+national);
  if (!supplier || !national || !pair)
    return unresolved('independent_operator_equivalence_missing',{locationPk:loc});
  const targets=offer?.evseIds;
  if (!Array.isArray(targets)||!targets.length||targets.some(x=>!id(x)))
    return unresolved('missing_target_pdc',{locationPk:loc});
  const allUnique=options.targetOwnersUnique === true;
  if (!allUnique)return unresolved('target_station_or_pdc_owner_not_unique',{locationPk:loc});
  if (options.sameCountry !== true || options.stationIdentityConfirmed !== true)
    return unresolved('country_or_station_identity_unproved',{locationPk:loc});
  const refs=[
    ...(Array.isArray(offer?.metadata?.physicalReferences)?
      offer.metadata.physicalReferences:[]),
    offer?.metadata?.physicalReference,
  ].map(id).filter(Boolean);
  const exact=targets.every(x=>refs.includes(id(x)));
  if (exact) return {
    classification:'exact+operator',assignable:true,
    evidence:'reviewed_supplier_cpo_and_exact_source_evse',
    locationPk:loc,targets:[...targets],
  };
  // Do not use the historical <=15m matching tolerance as new evidence.
  const f=options.fallback;
  if (!f || f.reviewStatus!=='INDEPENDENT_SCOPE_REVIEW_APPROVED' ||
      !isoDay(f.reviewedAt) || !f.sourceRecord || !f.nationalRecord ||
      f.sourceRecord===f.nationalRecord || f.stationId!==mapping.irveStationId ||
      f.country!=='FR' || f.uniqueSiteCandidates!==1)
    return unresolved('fallback_independent_site_and_scope_evidence_missing',{locationPk:loc});
  if (f.method==='gps') {
    if (!(Number.isFinite(f.distanceM) && f.distanceM>=0 && f.distanceM<=10))
      return unresolved('gps_distance_outside_reviewed_10m',{locationPk:loc});
  } else if (f.method==='address') {
    if (f.exactAddressConfirmed!==true)
      return unresolved('address_not_independently_confirmed',{locationPk:loc});
  } else return unresolved('unsupported_fallback_method',{locationPk:loc});
  if (f.pdcScopeReviewed!==true || f.connectorAndPowerReviewed!==true ||
      f.tariffHomogeneityReviewed!==true || !Array.isArray(f.targetPdcIds) ||
      targets.some(x=>!f.targetPdcIds.map(id).includes(id(x))))
    return unresolved('fallback_evse_connector_power_or_tariff_scope_unproved',{locationPk:loc});
  return {
    classification:f.method+'+operator',assignable:true,
    evidence:'reviewed_supplier_cpo_site_and_evse_scope',
    locationPk:loc,targets:[...targets],
  };
}

export function auditG5Hierarchy(offers, mappings, registry) {
  if(!Array.isArray(offers)||!Array.isArray(mappings))
    throw Error('G5 hierarchy needs source offers and mappings');
  const pairs=compileG5CpoProofs(registry);
  const byLoc=new Map();
  const owners=new Map();
  for(const m of mappings) {
    const key=String(m?.electroverseLocationPk??'');
    if(!key||byLoc.has(key))throw Error('G5 duplicate/missing mapping '+key);
    byLoc.set(key,m);
    for(const p of m.irvePdcIds||[]) {
      const k=id(p);const s=owners.get(k)||new Set();s.add(key);owners.set(k,s);
    }
  }
  const counts={};let independentlyAssignable=0;
  for(const offer of offers) {
    const loc=String(offer?.metadata?.electroverseLocationPk??'');
    const m=byLoc.get(loc);
    const unique=Array.isArray(offer?.evseIds)&&offer.evseIds.length>0 &&
      offer.evseIds.every(p=>owners.get(id(p))?.size===1 &&
        owners.get(id(p))?.has(loc));
    // No authoritative reviewed fallback bindings are present at this stage.
    // Historical mapping proximity, technical Powerdot proof and label
    // statistics are intentionally NOT passed as independent CPO evidence.
    const decision=classifyG5MatchHierarchy(offer,m,pairs,{
      targetOwnersUnique:unique,
      sameCountry:true,
      stationIdentityConfirmed:!!m?.irveStationId,
    });
    counts[decision.reason||decision.classification]=
      (counts[decision.reason||decision.classification]||0)+1;
    if(decision.assignable)independentlyAssignable++;
  }
  return {schemaVersion:1,status:'AUDIT_ONLY_NO_PRICE_PROMOTION',
    operatorPairsIndependentlyReviewed:pairs.size,
    offersReviewed:offers.length,independentlyAssignableOffers:independentlyAssignable,
    byDecision:counts,
    remainingG5:'CPO crosswalk and source-specific fallback scope must be proved before G5 PASS',
    providerCalls:0,automaticPublication:false};
}
