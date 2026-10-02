import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const DIR='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse/b-sibling-published-target-audit.json';
const sourcePks=new Set([
 '4321963','4321964','831351','128739',
 '3310695','3310697','3310700','3310702','3310705','3310709','3310710','3310713','3310716','3310717','3310718','3310721','4444437'
]);
const man=JSON.parse(await fs.readFile(DIR+'/manifest.json','utf8'));
const hits=[];
for(const t of man.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(DIR+'/'+t.file)));
  for(const o of tile.emspOffers||[]){
    const pks=new Set((o?.metadata?.electroverseEvsePks||[]).map(String));
    if(o?.metadata?.electroverseEvsePk!=null)pks.add(String(o.metadata.electroverseEvsePk));
    for(const pk of o?.metadata?.electroverseAliasEvsePks||[]) if(pk!=null)pks.add(String(pk));
    for(const pk of o?.metadata?.aliasElectroverseEvsePks||[]) if(pk!=null)pks.add(String(pk));
    const overlap=[...pks].filter(pk=>sourcePks.has(pk));
    if(!overlap.length)continue;
    hits.push({
      sourcePks:overlap,
      evseIds:o.evseIds||[],
      identityMode:o?.metadata?.identityMode??null,
      physicalReferences:o?.metadata?.physicalReferences??(o?.metadata?.physicalReference?[o.metadata.physicalReference]:[]),
      sourceGroupSize:o?.metadata?.sourceGroupSize??null,
      targetGroupSize:o?.metadata?.targetGroupSize??null,
      offerId:o.id
    });
  }
}
const out={generatedAt:new Date().toISOString(),wanted:[...sourcePks],hits};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({wanted:sourcePks.size,hits:hits.length,hitsByPk:Object.fromEntries([...sourcePks].map(pk=>[pk,hits.filter(h=>h.sourcePks.includes(pk)).map(h=>h.evseIds)]))},null,2));
