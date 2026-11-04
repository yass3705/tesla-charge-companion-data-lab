import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {simulateGeneration} from './generation_journal_runner.mjs';
import {fixtureTransport,diffInventories,validateFixture,sha} from './model.mjs';
const fixture=validateFixture(JSON.parse(await fs.readFile(new URL('./fixtures/archived-24.json',import.meta.url),'utf8')));
const temp=()=>fs.mkdtemp(path.join(os.tmpdir(),'electroverse-v2-'));
const selected=fixture.stations.slice(0,3).map(r=>r.electroverseLocationPk);
test('selected refresh plus unchanged retained yields identical archived data',async()=>{
 const r=await simulateGeneration({previous:fixture.stations,fixture,selected,generationId:'g2',outDir:await temp()});
 assert.equal(r.metrics.requests,1);
 assert.equal(r.provenance.filter(x=>x.state==='fetched_this_generation').length,3);
 assert.equal(r.provenance.filter(x=>x.state==='previous_verified_not_refreshed').length,21);
 for(const x of Object.values(diffInventories(fixture.stations,r.records)))assert.deepEqual([x.missing,x.added],[[],[]]);
});
test('tariff change in selection retained independently of other cached records',async()=>{
 const changed=structuredClone(fixture);
 changed.stations[0].tariff.evses[0].connectors[0].priceComponents[0].formattedValue='Consumption rate: €0.39 kWh';
 changed.stations[0].tariffHash=sha(changed.stations[0].tariff);
 const r=await simulateGeneration({previous:fixture.stations,fixture:changed,selected,generationId:'g3',outDir:await temp()});
 assert.equal(r.records[0].tariffHash,changed.stations[0].tariffHash);
 assert.equal(r.records[4].tariffHash,fixture.stations[4].tariffHash);
});
test('missing inventory blocks publication, preserving old data externally',async()=>{
 await assert.rejects(simulateGeneration({previous:fixture.stations,fixture,selected,generationId:'g4',outDir:await temp(),inventoryComplete:false}),/incomplete inventory/);
});
test('previous corrupt tariff hash fails closed',async()=>{
 const previous=structuredClone(fixture.stations);previous[0].tariffHash='wrong';
 await assert.rejects(simulateGeneration({previous,fixture,selected,generationId:'g5',outDir:await temp()}),/SHA mismatch/);
});
test('interruption resumes selected list only',async()=>{
 const selectedMany=fixture.stations.slice(0,12).map(r=>r.electroverseLocationPk);
 const outDir=await temp(),transport=fixtureTransport(fixture);
 await assert.rejects(simulateGeneration({previous:fixture.stations,fixture,selected:selectedMany,generationId:'g6',outDir,transport,interruptAfter:2}),{code:'SIMULATED_INTERRUPT'});
 const r=await simulateGeneration({previous:fixture.stations,fixture,selected:selectedMany,generationId:'g6',outDir,transport});
 assert.equal(r.metrics.requests,3);assert.equal(r.provenance.filter(x=>x.state==='fetched_this_generation').length,12);
});
