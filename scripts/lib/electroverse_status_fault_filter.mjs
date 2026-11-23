/**
 * TCC V9 tariff-only Electroverse fault screening.
 *
 * Status is an optional timestamped observation. A stale or absent snapshot
 * NEVER hides a tariff; it never implies free/occupied availability.
 * Lookup MUST be scoped by ChargingLocation PK and source EVSE PK: upstream EVSE
 * identifiers may legitimately occur under more than one station.
 *
 * Only an explicit, recently observed hard fault can suppress an Electroverse
 * offer from the derived *active* view. Raw/national catalogues remain intact.
 */
export const FAULT_STATUSES = Object.freeze(['OUTOFORDER', 'INOPERATIVE']);
export const DEFAULT_FAULT_MAX_AGE_MS = 24 * 60 * 60 * 1000;
const faultSet = new Set(FAULT_STATUSES);

export function assessElectroverseFault(snapshot, locationPk, evsePk, {
  nowMs = Date.now(), maxFaultAgeMs = DEFAULT_FAULT_MAX_AGE_MS,
} = {}) {
  const loc = String(locationPk ?? '');
  const pk = String(evsePk ?? '');
  const status = String(snapshot?.locations?.[loc]?.[pk] ?? 'MISSING').toUpperCase();
  const observedAt = snapshot?.observedAtByLocation?.[loc] ?? null;
  const sampledMs = typeof observedAt === 'string' ? Date.parse(observedAt) : NaN;
  const evidenceOk = Boolean(loc && pk && faultSet.has(status) &&
    Number.isFinite(sampledMs) && Number.isFinite(nowMs) &&
    Number.isFinite(maxFaultAgeMs) && maxFaultAgeMs > 0 &&
    nowMs >= sampledMs && nowMs - sampledMs <= maxFaultAgeMs);
  return {
    locationPk: loc, evsePk: pk, status,
    observedAt: typeof observedAt === 'string' ? observedAt : null,
    excludeFromActiveTariffs: evidenceOk,
    reason: evidenceOk ? 'recent_confirmed_inoperative' :
      (faultSet.has(status) ? 'fault_observation_missing_or_stale' :
        'no_confirmed_hard_fault'),
  };
}

/**
 * Secondary, offer-level safety net after mapping, alias enrichment and
 * deduplication. Do not allow post-build metadata to reintroduce a faulty EVSE
 * that was excluded upstream. Keep independently supported healthy siblings.
 * The input offer and original source rows are never mutated.
 */
export function screenElectroverseOffer(offer, snapshot, {
  nowMs = Date.now(), maxFaultAgeMs = DEFAULT_FAULT_MAX_AGE_MS,
} = {}) {
  const meta = offer?.metadata || {};
  const loc = String(meta.electroverseLocationPk ?? '');
  const primary = [...new Set([
    ...(Array.isArray(meta.electroverseEvsePks) ? meta.electroverseEvsePks : []),
    meta.electroverseEvsePk,
  ].filter(x => x != null).map(String))];
  const aliases = [...new Set((Array.isArray(meta.electroverseAliasEvsePks) ?
    meta.electroverseAliasEvsePks : []).filter(x => x != null).map(String))];
  const isFault = pk => assessElectroverseFault(snapshot, loc, pk, {
    nowMs, maxFaultAgeMs,
  }).excludeFromActiveTariffs;
  const keepPrimary = primary.filter(pk => !isFault(pk));
  const keepAliases = aliases.filter(pk => !isFault(pk));
  const removedPrimary = primary.filter(pk => !keepPrimary.includes(pk));
  const removedAliases = aliases.filter(pk => !keepAliases.includes(pk));
  const hasFault = removedPrimary.length > 0 || removedAliases.length > 0;
  const keep = !hasFault || keepPrimary.length + keepAliases.length > 0;
  if (!hasFault) {
    return { keep: true, offer, removedPrimary, removedAliases, reason: 'no_confirmed_hard_fault' };
  }
  if (!keep) {
    return { keep: false, offer: null, removedPrimary, removedAliases,
      reason: 'no_healthy_source_evse_evidence' };
  }
  const metadata = {...meta};
  if (primary.length > 0) {
    metadata.electroverseEvsePks = keepPrimary;
    delete metadata.electroverseEvsePk;
  }
  if (aliases.length > 0) metadata.electroverseAliasEvsePks = keepAliases;
  return {
    keep: true, offer: {...offer, metadata},
    removedPrimary, removedAliases, reason: 'retained_with_faulty_source_references_stripped',
  };
}
