import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import crypto from 'node:crypto';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const json=(path,val)=>{mkdirSync(dirname(path),{recursive:true});writeFileSync(path,JSON.stringify(val)+'\n');};
const shardIndex=pk=>crypto.createHash('sha1').update(pk).digest()[0]%128;
test('429 stops further requests while valid progress, pending and sanitized diagnostics survive',()=>{
  const temp=mkdtempSync(join(tmpdir(),'v9-electroverse-429-'));
  try{
    const ids=['100','101','102'],folder=join(temp,'data/electroverse/tariff_cache');
    const meta=[];
    for(let i=0;i<128;i++){
      const file='shard-'+String(i).padStart(3,'0')+'.json';
      const shard={shard:i,shardCount:128,stations:{}},path=join(folder,file);
      json(path,shard);
      meta.push({shard:i,file,count:0,sizeBytes:Buffer.byteLength(JSON.stringify(shard)+'\n')});
    }
    json(join(folder,'manifest.json'),{shards:meta,totalStations:0});
    json(join(folder,'checked-at.json'),{version:1,checkedAt:Object.fromEntries(ids.map(pk=>[pk,'2026-11-01T00:00:00.000Z']))});
    json(join(temp,'data/electroverse/irve_location_mapping.json'),{mappings:ids.map(pk=>({electroverseLocationPk:pk,irveStationId:'station-'+pk,irvePdcIds:[]}))});
    json(join(temp,'reports/electroverse/incremental-selection.json'),{selectedCount:ids.length,selected:ids.map(pk=>({pk}))});
    const preload=join(temp,'mock-provider.mjs');
    writeFileSync(preload, "let count=0;\nglobalThis.fetch=async()=>{\n count++;\n if(count===1)return new Response(JSON.stringify({data:{s0:{chargingLocationPk:'100',evses:{edges:[]}}}}),{status:200,headers:{'Content-Type':'application/json'}});\n return new Response('',{status:429,headers:{'retry-after':'120'}});\n};\n");
    const result=spawnSync(process.execPath,['--import',preload,join(root,'scripts/electroverse_hybrid_refresh.mjs')],
      {cwd:temp,env:{...process.env,
          [['ELECTROVERSE','API','KEY'].join('_')]:'synthetic-test-only',
          ELECTROVERSE_BATCH_SIZE:'1',ELECTROVERSE_CONCURRENCY:'1',
          ELECTROVERSE_WAVE_PAUSE_MS:'1',ELECTROVERSE_FALLBACK_INTERVAL_MS:'1'},encoding:'utf8',timeout:20000});
    assert.equal(result.status,2,'Unexpected collector exit '+result.status+': '+result.stderr);
    const state=JSON.parse(readFileSync(join(folder,'checked-at.json')));
    assert.notEqual(state.checkedAt['100'],'2026-11-01T00:00:00.000Z');
    assert.equal(state.checkedAt['101'],'2026-11-01T00:00:00.000Z');
    assert.equal(state.checkedAt['102'],'2026-11-01T00:00:00.000Z');
    const failures=JSON.parse(readFileSync(join(temp,'reports/electroverse/hybrid-refresh-failures.json'))).failures;
    assert.deepEqual(failures.map(x=>x.pk),['101','102']);
    assert.equal(failures[0].error,'rate_limited');
    assert.equal(failures[1].error,'deferred_due_to_rate_limit');
    const manifest=JSON.parse(readFileSync(join(folder,'manifest.json')));
    assert.equal(manifest.lastIncrementalRefresh.httpRequests,2);
    assert.equal(manifest.lastIncrementalRefresh.new,1);
    assert.equal(manifest.lastIncrementalRefresh.failures,2);
    assert.equal(manifest.lastIncrementalRefresh.rateLimit.backoffSeconds,120);
    assert.equal(JSON.parse(readFileSync(join(folder,'shard-'+String(shardIndex('100')).padStart(3,'0')+'.json'))).stations['100'].tariff.chargingLocationPk,'100');
    const events=JSON.parse(readFileSync(join(temp,'reports/electroverse/failure-diagnostics.json'))).events;
    assert.equal(events.length,1);
    assert.equal(events[0].rateLimit.httpStatus,429);
    assert.ok(!JSON.stringify(events).includes('synthetic-test-only'));
  }finally{rmSync(temp,{recursive:true,force:true});}
});
