import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {validateFixture,validateRecord,sha,fixtureTransport,runV1Model,runV2,diffInventories} from '../model.mjs';
const fixture=validateFixture(JSON.parse(await fs.readFile(new URL('../fixtures/archived-24.json',import.meta.url),'utf8')));
const temp=()=>fs.mkdtemp(path.join(os.tmpdir(),'electroverse-v2-'));
const ids=fixture.stations.map(x=>x.electroverseLocationPk);

// Exact archived tariff projection, including all nested complex restrictions.
test('archived V1 records and V2 output preserve every identity and tariff component',async()=>{
  const v1=await runV1Model(fixture,{outDir:await temp()});
  const v2=await runV2(fixture,{outDir:await temp()});
  assert.equal(v1.metrics.covered,24);assert.equal(v2.metrics.covered,24);
  for(const row of Object.values(diffInventories(v1.records,v2.records)))assert.deepEqual([row.missing,row.added],[[],[]]);
  assert.deepEqual(v1.records.map(x=>x.tariffHash).sort(),v2.records.map(x=>x.tariffHash).sort());
});
test('interruption resumes after checkpoint without recollecting completed batches',async()=>{
  const outDir=await temp(),transport=fixtureTransport(fixture);
  await assert.rejects(runV2(fixture,{outDir,transport,interruptAfter:2}),{code:'SIMULATED_INTERRUPT'});
  const resumed=await runV2(fixture,{outDir,transport});
  assert.equal(resumed.metrics.covered,24);
  assert.equal(transport.metrics().requests,5);
  assert.equal(resumed.metrics.requests,5);
  assert.equal(Object.values(diffInventories(fixture.stations,resumed.records)).every(x=>!x.missing.length&&!x.added.length),true);
});
test('partial GraphQL alias falls back only for the absent station',async()=>{
  const transport=fixtureTransport(fixture,{faults:{[ids[0]]:{batch:['partial']}}});
  const result=await runV2(fixture,{outDir:await temp(),transport});
  assert.equal(result.metrics.covered,24);assert.equal(result.metrics.requests,6);
  assert.deepEqual(result.errors,[]);
});
for(const status of [429,500,503,'timeout'])test(`persistent ${status} retains last-good and stays pending`,async()=>{
  const outDir=await temp();const previous=await runV2(fixture,{outDir});
  const changed=structuredClone(fixture),target=changed.stations[0];
  target.tariff.evses[0].connectors[0].kilowatts=11;target.tariffHash=sha(target.tariff);
  const before=await fs.readFile(path.join(outDir,'last-good.json'));
  const transport=fixtureTransport(changed,{faults:{[ids[0]]:{batch:[status,status]}}});
  const next=await runV2(changed,{outDir,transport});
  assert.equal(next.metrics.covered,19);assert.equal(next.errors.length,5);
  assert.equal(next.metrics.requests,6,'two batch attempts for first group; no immediate single storm');
  const state=JSON.parse(await fs.readFile(path.join(outDir,'last-good.json')));
  assert.equal(state.stations[ids[0]].tariffHash,fixture.stations[0].tariffHash);
  assert.ok(before.length>0);
});
for(const fault of ['pagination_incomplete','cursor_stuck','missing'])test(`${fault} cannot overwrite a verified tariff`,async()=>{
  const outDir=await temp();await runV2(fixture,{outDir});
  const changed=structuredClone(fixture);changed.stations[0].tariff.evses[0].connectors[0].kilowatts=13;
  changed.stations[0].tariffHash=sha(changed.stations[0].tariff);
  const transport=fixtureTransport(changed,{faults:{[ids[0]]:{batch:[fault],single:[fault]}}});
  const result=await runV2(changed,{outDir,transport});
  assert.equal(result.metrics.covered,23);
  assert.equal(JSON.parse(await fs.readFile(path.join(outDir,'last-good.json'))).stations[ids[0]].tariffHash,fixture.stations[0].tariffHash);
});
test('corrupt checkpoint fails closed and leaves last-good untouched',async()=>{
  const outDir=await temp();await runV2(fixture,{outDir});
  const before=await fs.readFile(path.join(outDir,'last-good.json'));
  await fs.writeFile(path.join(outDir,'checkpoint.json'),'{bad');
  await assert.rejects(runV2(fixture,{outDir}),/corrupt JSON/);
  assert.deepEqual(await fs.readFile(path.join(outDir,'last-good.json')),before);
});
test('checkpoint cannot claim a station missing from last-good',async()=>{
  const outDir=await temp();await runV2(fixture,{outDir});
  const file=path.join(outDir,'last-good.json'),state=JSON.parse(await fs.readFile(file));
  delete state.stations[ids[0]];await fs.writeFile(file,JSON.stringify(state));
  await assert.rejects(runV2(fixture,{outDir}),/checkpoint references missing verified station/);
});
test('schema, SHA and duplicate IDs reject corrupt or ambiguous inputs',()=>{
  const duplicate=structuredClone(fixture);duplicate.stations.push(structuredClone(duplicate.stations[0]));
  assert.throws(()=>validateFixture(duplicate),/duplicate station/);
  const wrong=structuredClone(fixture.stations[0]);wrong.tariff.evses[0].connectors[0].kilowatts=1;
  assert.throws(()=>validateRecord(wrong),/SHA mismatch/);
  const malformed=structuredClone(fixture.stations[0]);malformed.tariff.evses[0].connectors=[];malformed.tariffHash=sha(malformed.tariff);
  assert.doesNotThrow(()=>validateRecord(malformed),'empty connector arrays are valid data, not synthetic replacements');
});
test('changed data is accepted only when its exact components and SHA agree',async()=>{
  const outDir=await temp();await runV2(fixture,{outDir});
  const changed=structuredClone(fixture),tariff=changed.stations[0].tariff;
  tariff.evses[0].connectors[0].priceComponents[0].formattedValue='Consumption rate: €0.31 kWh';
  changed.stations[0].tariffHash=sha(tariff);
  const result=await runV2(changed,{outDir});
  assert.equal(result.metrics.changed,1);assert.equal(result.metrics.covered,24);
  assert.equal(result.records.find(x=>x.electroverseLocationPk===ids[0]).tariffHash,changed.stations[0].tariffHash);
});
test('synthetic zero-price fixture preserves free flag, VAT, currency and restrictions',()=>{
  const record=structuredClone(fixture.stations[0]);record.electroverseLocationPk='synthetic-free';
  record.tariff.chargingLocationPk='synthetic-free';
  const c=record.tariff.evses[0].connectors[0];c.isChargingFree=true;
  c.priceComponents=[{__typename:'ConsumptionRate',formattedValue:'Consumption rate: €0.00 kWh'},
    {__typename:'VAT',formattedValue:'VAT rate: 0%'}];
  c.complexPricingDetail={currency:'EUR',restrictions:[{restrictionTypes:['WEEKDAY'],
    weekdayRestrictions:{daysOfWeek:['MONDAY']},priceComponents:c.priceComponents}]};
  record.tariffHash=sha(record.tariff);validateRecord(record);
  for(const row of Object.values(diffInventories([record],[structuredClone(record)])))assert.deepEqual([row.missing,row.added],[[],[]]);
});
test('output guard rejects canonical or arbitrary paths',async()=>{
  await assert.rejects(runV2(fixture,{outDir:'data/electroverse/tariff_cache'}),/output must be/);
});
