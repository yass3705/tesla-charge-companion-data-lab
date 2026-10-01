import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MANIFEST=CACHE+'/manifest.json';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse-fr-current-residual-ranking.json';

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const opOf=p=>{const m=String(p||'').match(/^FR([A-Z0-9]{1,8})E/);return m?m[1]:'UNKNOWN';};
const top=o=>Object.entries(o).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).map(([operator,count])=>({operator,count}));

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const manifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const overlayManifest=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const published=new Set();
for(const t of overlayManifest.tiles||[]){
  const gz=await fs.readFile(OVERLAY+'/'+t.file);
  const p=JSON.parse(zlib.gunzipSync(gz).toString('utf8'));
  for(const o of p.emspOffers||[])for(const id of o.evseIds||[])published.add(norm(id));
}
const missingByOp={}, locationByOp={}, unresolvedRefsByOp={}, samplesByOp={};
for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk)); if(!m)continue;
    const local=[...new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const missing=local.filter(p=>!published.has(p));
    if(!missing.length)continue;
    const ops=[...new Set(missing.map(opOf))];
    for(const op of ops){
      const pdcs=missing.filter(p=>opOf(p)===op);
      missingByOp[op]=(missingByOp[op]||0)+pdcs.length;
      locationByOp[op]=(locationByOp[op]||0)+1;
      const unresolved=[];
      for(const e of row.tariff?.evses||[]){
        const raw=String(e?.physicalReference??'').trim(); if(!raw)continue;
        const k=norm(raw);
        if(local.includes(k)||published.has(k))continue;
        unresolved.push(raw);
      }
      unresolvedRefsByOp[op]=(unresolvedRefsByOp[op]||0)+unresolved.length;
      if((samplesByOp[op]||[]).length<8){
        (samplesByOp[op]??=[]).push({
          locationPk:String(row.electroverseLocationPk),
          missingPdcs:pdcs.slice(0,20),
          unresolvedRefs:unresolved.slice(0,20),
          localPdcCount:local.length
        });
      }
    }
  }
}
const ranking=top(missingByOp).map(x=>({
  ...x,
  locations:locationByOp[x.operator]||0,
  unresolvedRefs:unresolvedRefsByOp[x.operator]||0,
  samples:samplesByOp[x.operator]||[]
}));
const out={generatedAt:new Date().toISOString(),publishedEvses:overlayManifest.stats?.publishedEvses||null,
  residualPhysicalReferenceRejects:overlayManifest.rejected?.physical_reference_not_in_local_national_pdcs||null,
  ranking};
await fs.mkdir('reports',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
