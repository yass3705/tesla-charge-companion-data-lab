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
