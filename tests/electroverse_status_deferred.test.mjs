import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import crypto from 'node:crypto';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
function write(path,val){
 mkdirSync(dirname(path),{recursive:true});
 writeFileSync(path,JSON.stringify(val)+'\n');
}
function invoke(temp,preload,env={}){
 return spawnSync(process.execPath,['--import',preload,
   join(root,'scripts/electroverse_status_incremental.mjs'),'collect','0'],
  {cwd:temp,encoding:'utf8',timeout:30000,
   env:{...process.env,ELECTROVERSE_API_KEY:'test-only-no-supplier',
    ELECTROVERSE_STATUS_REQUEST_DELAY_MS:'450',
    ELECTROVERSE_STATUS_ATTEMPTS:'1',
    ELECTROVERSE_STATUS_RUN_LIMIT:'1500',
    ELECTROVERSE_STATUS_429_BUDGET_SECONDS:'480',...env}});
}

test('sweep defers old failed PK, recovery calls only that PK and retains good result',()=>{
 const temp=mkdtempSync(join(tmpdir(),'tcc-v9-status-deferred-'));
 try {
  const cache=join(temp,'data/electroverse/tariff_cache');
  const time=new Date().toISOString();
  const shards=[];
  for(let i=0;i<128;i++){
   const file='shard-'+String(i).padStart(3,'0')+'.json';
   const stations=i===0?{'100':{tariff:{evses:[{pk:'EVSE-100'}]}}}:{};
   const raw=JSON.stringify({stations})+'\n';
   const dest=join(cache,file);
   mkdirSync(dirname(dest),{recursive:true});
   writeFileSync(dest,raw);
   shards.push({file,count:Object.keys(stations).length,sizeBytes:Buffer.byteLength(raw)});
  }
  const generatedAt=time;
  write(join(cache,'manifest.json'),{generatedAt,shards});
  const sourceFingerprint=crypto.createHash('sha256').update(
   JSON.stringify({date:generatedAt,shards:shards.map(x=>[x.file,x.count,x.sizeBytes])})).digest('hex');
  const partition=join(temp,'data/electroverse/live_statuses/parts/part-00.json');
  write(partition,{schemaVersion:1,partition:0,partitionCount:16,
    sourceFingerprint,sourceCacheDate:generatedAt,
    startedAt:time,updatedAt:time,expectedLocations:1,
    entries:{},errors:{'100':{attempts:1,error:'single_paged_unavailable',at:time}}});
  const noSupplier=join(temp,'no-supplier.mjs');
  writeFileSync(noSupplier,"globalThis.fetch=async()=>{throw Error('Unexpected supplier call during deferred sweep')};\n");
  const sweep=invoke(temp,noSupplier,{ELECTROVERSE_STATUS_DEFER_FAILED:'1'});
  assert.equal(sweep.status,0,sweep.stderr+'\n'+sweep.stdout);
  const partial=JSON.parse(readFileSync(partition));
  assert.deepEqual(partial.entries,{});
  assert.ok(partial.errors['100']);
  const sweptReport=JSON.parse(readFileSync(join(temp,'reports/electroverse/status-partition-latest.json')));
  assert.equal(sweptReport.phase,'initial_sweep');
  assert.equal(sweptReport.verifiedLocations,0);
  assert.equal(sweptReport.requests,0);
  assert.equal(sweptReport.deferredFailures,1);

  const oneSupplier=join(temp,'one-supplier.mjs');
  writeFileSync(oneSupplier,[
   "globalThis.fetch=async (_url,options)=>{",
   " const body=JSON.parse(options.body);",
   " if(!body.query.includes('s0:chargingLocation(pk:\"100\")'))",
   "   throw Error('Unexpected request instead of deferred PK 100');",
   " return new Response(JSON.stringify({data:{s0:{evses:{",
   "  edges:[{node:{pk:'EVSE-100',status:'AVAILABLE'}}],",
   "  pageInfo:{hasNextPage:false,endCursor:null}}}}}),{",
   "  status:200,headers:{'Content-Type':'application/json'}});",
   "};",
  ].join('\n')+'\n');
  const recovery=invoke(temp,oneSupplier,{ELECTROVERSE_STATUS_RECOVERY_ONLY:'1'});
  assert.equal(recovery.status,0,recovery.stderr+'\n'+recovery.stdout);
  const after=JSON.parse(readFileSync(partition));
  assert.deepEqual(after.entries['100'],{'EVSE-100':'AVAILABLE'});
  assert.deepEqual(after.errors,{});
  assert.equal(after.startedAt,time,'Do not silently extend freshness when retrying');
  const report=JSON.parse(readFileSync(join(temp,'reports/electroverse/status-partition-latest.json')));
  assert.equal(report.phase,'deferred_recovery');
  assert.equal(report.newSuccessful,1);
  assert.equal(report.verifiedLocations,1);
  assert.equal(report.requests,1);
 } finally {rmSync(temp,{recursive:true,force:true});}
});
