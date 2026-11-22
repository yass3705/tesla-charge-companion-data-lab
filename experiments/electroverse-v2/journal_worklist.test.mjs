import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {runJournal} from './journal_runner.mjs';
import {appendBatch} from './generation_store.mjs';
import {sha,validateFixture} from './model.mjs';
const fixture=validateFixture(JSON.parse(await fs.readFile(new URL('./fixtures/archived-24.json',import.meta.url),'utf8')));
const temp=()=>fs.mkdtemp(path.join(os.tmpdir(),'electroverse-v2-'));
test('recovery rejects valid-checksum journal with wrong station order',async()=>{
 const dir=await temp();
 const sourceHash=sha(fixture.stations.map(r=>[String(r.electroverseLocationPk),r.tariffHash]));
 await appendBatch(dir,{sourceHash,index:0,records:[...fixture.stations.slice(0,5)].reverse()});
 await assert.rejects(runJournal(fixture,{outDir:dir}),/journal worklist mismatch/);
});
test('recovery rejects valid-checksum journal with missing station and no network',async()=>{
 const dir=await temp();
 const sourceHash=sha(fixture.stations.map(r=>[String(r.electroverseLocationPk),r.tariffHash]));
 await appendBatch(dir,{sourceHash,index:0,records:fixture.stations.slice(0,4)});
 await assert.rejects(runJournal(fixture,{outDir:dir}),/journal worklist mismatch/);
});
