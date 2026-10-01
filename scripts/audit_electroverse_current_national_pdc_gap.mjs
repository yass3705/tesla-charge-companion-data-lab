import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse/current-national-pdc-gap.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const opOf=p=>{const m=String(p||'').match(/^FR([A-Z0-9]{1,8})E/);return m?m[1]:'UNKNOWN';};

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const oman=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const published=new Set();
for(const t of oman.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
  for(const o of tile.emspOffers||[])for(const id of o.evseIds||[])published.add(norm(id));
}
const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const cachePks=new Set();
for(const sh of cman.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{}))cachePks.add(String(row.electroverseLocationPk));
}
const byOp={},sourceBackedByOp={},locByOp={},samples={};
const allMissing=new Set(),sourceBackedMissing=new Set();
for(const m of mapping.mappings||[]){
  const pk=String(m.electroverseLocationPk??'');
  const sourceBacked=cachePks.has(pk);
  const seenOps=new Set();
  for(const raw of m.irvePdcIds||[]){
    const p=norm(raw);if(!p||published.has(p))continue;
    allMissing.add(p);
    const op=opOf(p);byOp[op]=(byOp[op]||new Set()).add(p);
    if(sourceBacked){sourceBackedMissing.add(p);sourceBackedByOp[op]=(sourceBackedByOp[op]||new Set()).add(p);}
    seenOps.add(op);
    if((samples[op]||[]).length<8)(samples[op]??=[]).push({locationPk:pk,irveStationId:m.irveStationId??null,pdc:p,sourceBacked});
  }
  for(const op of seenOps)locByOp[op]=(locByOp[op]||0)+1;
}
const ops=new Set([...Object.keys(byOp),...Object.keys(sourceBackedByOp)]);
const ranking=[...ops].map(op=>({
  operator:op,
  missingNationalPdcs:byOp[op]?.size||0,
  sourceBackedMissingPdcs:sourceBackedByOp[op]?.size||0,
  locations:locByOp[op]||0,
  samples:samples[op]||[]
})).sort((a,b)=>b.sourceBackedMissingPdcs-a.sourceBackedMissingPdcs||b.missingNationalPdcs-a.missingNationalPdcs||a.operator.localeCompare(b.operator));
const out={
 schemaVersion:1,generatedAt:new Date().toISOString(),
 publishedNationalTargets:published.size,
 uniqueMissingNationalPdcs:allMissing.size,
 uniqueSourceBackedMissingNationalPdcs:sourceBackedMissing.size,
 ranking,
 top20:ranking.slice(0,20),
 policy:'Unique national PDCs absent from current Electroverse France overlay. sourceBacked means the mapped Electroverse location exists in the tariff cache. No source identity inference.'
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
