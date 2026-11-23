import test from 'node:test';
import assert from 'node:assert/strict';
import {
  assessElectroverseFault, screenElectroverseOffer, DEFAULT_FAULT_MAX_AGE_MS,
} from '../scripts/lib/electroverse_status_fault_filter.mjs';

const nowMs = Date.parse('2026-11-23T13:45:00Z');
const fresh = new Date(nowMs - 30 * 60_000).toISOString();
const snapshot = {
  locations: {
    'A': {one: 'OUTOFORDER', two: 'INOPERATIVE',
      three: 'CHARGING', four: 'BLOCKED', five: 'UNKNOWN', six: 'RESERVED'},
    'B': {one: 'AVAILABLE'},
  },
  observedAtByLocation: {A: fresh, B: fresh},
};
const check = (station, evse, options = {}) =>
  assessElectroverseFault(snapshot, station, evse, {nowMs, ...options});

test('fresh explicit faults suppress only the matching station + EVSE tariff', () => {
  assert.equal(check('A', 'one').excludeFromActiveTariffs, true);
  assert.equal(check('A', 'two').excludeFromActiveTariffs, true);
  assert.equal(check('B', 'one').excludeFromActiveTariffs, false);
});

test('occupied, blocked, reserved, unknown, and missing do not suppress tariffs', () => {
  for (const evse of ['three', 'four', 'five', 'six', 'missing']) {
    assert.equal(check('A', evse).excludeFromActiveTariffs, false, evse);
  }
});

test('stale or legacy un-timestamped faults never suppress tariffs', () => {
  const staleSnapshot = {
    locations: {A: {one: 'OUTOFORDER'}},
    observedAtByLocation: {A: new Date(nowMs - DEFAULT_FAULT_MAX_AGE_MS - 1).toISOString()},
  };
  assert.equal(assessElectroverseFault(staleSnapshot, 'A', 'one', {nowMs}).excludeFromActiveTariffs, false);
  assert.equal(assessElectroverseFault({locations: {A: {one: 'OUTOFORDER'}}}, 'A', 'one', {nowMs}).excludeFromActiveTariffs, false);
});

test('future, invalid, or zero-age-policy timestamps fail open for price comparison', () => {
  for (const observedAt of [new Date(nowMs + 1000).toISOString(), 'bad-date']) {
    assert.equal(assessElectroverseFault({locations: {A: {one: 'OUTOFORDER'}},
      observedAtByLocation: {A: observedAt}}, 'A', 'one', {nowMs}).excludeFromActiveTariffs, false);
  }
  assert.equal(check('A', 'one', {maxFaultAgeMs: 0}).excludeFromActiveTariffs, false);
});

test('no historical status means no EVSE deletion, regardless of other station statuses', () => {
  assert.equal(assessElectroverseFault(null, 'A', 'one', {nowMs}).excludeFromActiveTariffs, false);
  assert.equal(check('UNRELATED', 'one').excludeFromActiveTariffs, false);
});

test('postbuild removes fault source references added through grouping or dedupe', () => {
 const o={id:'offer-a',evseIds:['NATIONAL-EVSE'],metadata:{
   electroverseLocationPk:'A', electroverseEvsePks:['one','three'],
   electroverseAliasEvsePks:['two','four'],
 }};
 const result=screenElectroverseOffer(o,snapshot,{nowMs});
 assert.equal(result.keep,true);
 assert.deepEqual(result.offer.metadata.electroverseEvsePks,['three']);
 assert.deepEqual(result.offer.metadata.electroverseAliasEvsePks,['four']);
 assert.deepEqual(result.removedPrimary,['one']);
 assert.deepEqual(result.removedAliases,['two']);
 assert.deepEqual(o.metadata.electroverseEvsePks,['one','three'],
   'Original offer / immutable source evidence must not be mutated');
});
test('postbuild drops single-source inoperative offer, even with healthy aliases', () => {
 const o={id:'offer-b',metadata:{electroverseLocationPk:'A',
    electroverseEvsePks:['one','two'],electroverseAliasEvsePks:['three']}};
 const r=screenElectroverseOffer(o,snapshot,{nowMs});
 assert.equal(r.keep,false);
 assert.equal(r.offer,null);
 assert.equal(r.reason,'no_healthy_source_evse_evidence');
});
test('postbuild fails open for old or unobserved status and protects unrelated stations',()=>{
 const o={id:'offer-c',metadata:{electroverseLocationPk:'A',
    electroverseEvsePks:['one','five','three']}};
 const r=screenElectroverseOffer(o,snapshot,{nowMs:nowMs+DEFAULT_FAULT_MAX_AGE_MS+1});
 assert.equal(r.keep,true);
 assert.equal(r.offer,o);
 const different=screenElectroverseOffer({...o,metadata:{...o.metadata,electroverseLocationPk:'B'}},snapshot,{nowMs});
 assert.equal(different.keep,true);
});
test('postbuild strips faulty aliases without removing healthy primary tariff',()=>{
 const o={id:'offer-d',metadata:{electroverseLocationPk:'A',
    electroverseEvsePk:'three',electroverseAliasEvsePks:['one']}};
 const r=screenElectroverseOffer(o,snapshot,{nowMs});
 assert.equal(r.keep,true);
 assert.deepEqual(r.offer.metadata.electroverseEvsePks,['three']);
 assert.deepEqual(r.offer.metadata.electroverseAliasEvsePks,[]);
});
