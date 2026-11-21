import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const script=fileURLToPath(new URL('../scripts/electroverse_hybrid_refresh.mjs',import.meta.url));
for(const failure of ['cursor_cycle','duplicate_evse']){
 const out=await fs.mkdtemp(path.join(os.tmpdir(),'v9-hybrid-'));
 try{
  const cache=path.join(out,'data/electroverse/tariff_cache');
  await fs.mkdir(cache,{recursive:true});await fs.mkdir(path.join(out,'reports/electroverse'),{recursive:true});
  const save=async(name,value)=>fs.writeFile(path.join(out,name),JSON.stringify(value)+'\n');
  const index=pk=>createHash('sha1').update(pk).digest()[0]%128;
  const prior={electroverseLocationPk:'bad',fetchMode:'paged',tariffHash:'previous',tariff:{preserved:true}};
  const shards=[];
  for(let i=0;i<128;i++){
   const file=`shard-${String(i).padStart(3,'0')}.json`,stations=i===index('bad')?{bad:prior}:{};
   await save('data/electroverse/tariff_cache/'+file,{shard:i,shardCount:128,stations});
   shards.push({shard:i,file,count:Object.keys(stations).length,sizeBytes:(await fs.stat(path.join(cache,file))).size});
  }
  await save('data/electroverse/tariff_cache/manifest.json',{shards,totalStations:1});
  await save('data/electroverse/irve_location_mapping.json',{mappings:['good','bad'].map(pk=>({electroverseLocationPk:pk,irveStationId:'source-'+pk}))});
  await save('reports/electroverse/incremental-selection.json',{selected:[{pk:'good'},{pk:'bad'}]});
  const wrapper=`
   let page=0;
   const evse=pk=>({node:{pk,connectors:{edges:[{node:{pk:'plug-'+pk,kilowatts:22,priceComponents:null}}]}}});
   globalThis.fetch=async(_url,request)=>{
     const body=JSON.parse(request.body);let data;
     if(body.query.includes('ElectroverseTariffBatch'))data={s0:{chargingLocationPk:'good',evses:{edges:[evse('good')]}}};
     else {
       if(!body.query.includes('ElectroverseTariffPaged'))throw Error('Unexpected provider request');
       page++;
       data={chargingLocation:{chargingLocationPk:'bad',evses:{edges:[evse(${JSON.stringify(failure)}==='duplicate_evse'?'duplicate':String(page))],pageInfo:{hasNextPage:true,endCursor:page===2?'b':'a'}}}};
     }
     return new Response(JSON.stringify({data}),{status:200});
   };
   await import(${JSON.stringify(script)});
  `;
  await fs.writeFile(path.join(out,'fixture.mjs'),wrapper);
  const result=spawnSync(process.execPath,[path.join(out,'fixture.mjs')],{cwd:out,encoding:'utf8',timeout:10000,
    env:{...process.env,ELECTROVERSE_API_KEY:'placeholder',ELECTROVERSE_WAVE_PAUSE_MS:'0',ELECTROVERSE_FALLBACK_INTERVAL_MS:'0'}});
  assert.equal(result.status,2,result.stderr);
  const read=async p=>JSON.parse(await fs.readFile(path.join(out,p),'utf8'));
  const report=await read('reports/electroverse/hybrid-refresh-failures.json');
  assert.deepEqual(report.failures.map(f=>[f.pk,f.error]),[['bad',failure==='cursor_cycle'?'cursor_not_advancing':'duplicate_evse_across_pages']]);
  const bad=await read('data/electroverse/tariff_cache/'+shards[index('bad')].file);
  const good=await read('data/electroverse/tariff_cache/'+shards[index('good')].file);
  assert.deepEqual(bad.stations.bad,prior,'failed location retains its previous tariff without partial overwrite');
  assert.equal(good.stations.good.tariff.chargingLocationPk,'good','independent successful source response retained');
  const m=await read('data/electroverse/tariff_cache/manifest.json');
  assert.equal(m.lastIncrementalRefresh.failures,1);assert.equal(m.lastIncrementalRefresh.new,1);
  const ledger = path.join(cache,'checked-at.json');
  await fs.writeFile(ledger, '{broken');
  const damaged = spawnSync(process.execPath,[path.join(out,'fixture.mjs')],{cwd:out,encoding:'utf8',
    env:{...process.env,ELECTROVERSE_API_KEY:'placeholder'}});
  assert.equal(damaged.status,1);
  assert.equal(await fs.readFile(ledger,'utf8'),'{broken');
 }finally{await fs.rm(out,{recursive:true,force:true});}
}
console.log('Actual hybrid collector: cyclic cursors and duplicate paged EVSE fail, last-good and successful siblings retained; offline only PASS');
