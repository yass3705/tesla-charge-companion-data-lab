import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const SRC='reports/electroverse/remaining-batch-analysis.json';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse/current-homogeneous-quickwins.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const src=JSON.parse(await fs.readFile(SRC,'utf8'));
const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const man=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const published=new Set();
for(const t of man.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
  for(const o of tile.emspOffers||[])for(const id of o.evseIds||[])published.add(norm(id));
}
const groups=[];
for(const op of src.operators||[]){
  for(const g of op.safeGroups||[]){
    if(g.mode!=='homogeneous_exact_set')continue;
    const m=byPk.get(String(g.electroverseLocationPk));
    const local=[...new Set((m?.irvePdcIds||[]).map(norm).filter(Boolean))];
    const targetPdcs=local.filter(p=>!published.has(p));
    groups.push({
      operator:op.operator,
      electroverseLocationPk:String(g.electroverseLocationPk),
      irveStationId:g.irveStationId??null,
      residualCount:g.residualCount,
      availablePdcCount:g.availablePdcCount,
      refs:g.refs||[],
      targetPdcs,
      commonPrefix:g.commonPrefix??null
    });
  }
}
const out={generatedAt:new Date().toISOString(),count:groups.length,totalSourceEvses:groups.reduce((n,g)=>n+g.residualCount,0),groups};
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));