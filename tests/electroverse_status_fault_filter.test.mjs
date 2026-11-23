import test from 'node:test';
import assert from 'node:assert/strict';
import {
  assessElectroverseFault, DEFAULT_FAULT_MAX_AGE_MS,
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
