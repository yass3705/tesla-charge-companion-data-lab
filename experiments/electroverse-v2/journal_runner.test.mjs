import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {runJournal} from './journal_runner.mjs';
import {fixtureTransport,diffInventories,runV2,validateFixture} from './model.mjs';
const fixture=validateFixture(JSON.parse(await fs.readFile(new URL('./fixtures/archived-24.json',import.meta.url),'utf8')));
const dir=()=>fs.mkdtemp(path.join(os.tmpdir(),'electroverse-v2-'));
test('archived fixture parity and writes',async()=>{
 const j=await runJournal(fixture,{outDir:await dir()});
 const v=await runV2(fixture,{outDir:await dir()});
 assert.equal(j.metrics.writes,5);assert.equal(v.metrics.writes,10);
 for(const x of Object.values(diffInventories(j.records,v.records)))assert.deepEqual([x.missing,x.added],[[],[]]);
});
test('resume after two batches avoids replay',async()=>{
 const outDir=await dir(),transport=fixtureTransport(fixture);
 await assert.rejects(runJournal(fixture,{outDir,transport,interruptAfter:2}),{code:'SIMULATED_INTERRUPT'});
 const resumed=await runJournal(fixture,{outDir,transport});
 assert.equal(resumed.metrics.requests,5);assert.equal(resumed.metrics.covered,24);assert.equal(resumed.metrics.skippedBatches,2);
});
test('incomplete response is refused without committing its batch',async()=>{
 const outDir=await dir(),pk=fixture.stations[0].electroverseLocationPk;
 const transport=fixtureTransport(fixture,{faults:{[pk]:{batch:['partial'],single:['missing']}}});
 await assert.rejects(runJournal(fixture,{outDir,transport}),/incomplete batch/);
 const resumed=await runJournal(fixture,{outDir});assert.equal(resumed.metrics.covered,24);
});