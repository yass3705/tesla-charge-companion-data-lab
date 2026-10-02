import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const MAN='data/platforms/electroverse/france-evse/manifest.json';
const LED='data/platforms/electroverse/validated-mappings/customgyevse-pair-groups.json';
const OUT='reports/electroverse/customgyevse-final-provenance-audit.json';
const man=JSON.parse(await fs.readFile(MAN,'utf8'));
const led=JSON.parse(await fs.readFile(LED,'utf8'));
const wanted=new Set((led.groups||[]).flatMap(g=>g.sourceEvsePks||[]).map(String));
const seen=new Set(), offers=[];
for(const t of man.tiles||[]){
  const d=JSON.parse(zlib.gunzipSync(await fs.readFile('data/platforms/electroverse/france-evse/'+t.file)));
  for(const o of d.emspOffers||[]){
    const pks=[
      ...(o?.metadata?.electroverseEvsePks||[]),
      ...(o?.metadata?.electroverseEvsePk!=null?[o.metadata.electroverseEvsePk]:[]),
      ...(o?.metadata?.electroverseAliasEvsePks||[])
    ].map(String);
    const hits=pks.filter(pk=>wanted.has(pk));
    if(hits.length){
      hits.forEach(pk=>seen.add(pk));
      offers.push({id:o.id,evseIds:o.evseIds,identityMode:o?.metadata?.identityMode||null,hits,allSourcePks:pks});
    }
  }
}
const missing=[...wanted].filter(x=>!seen.has(x));
const out={generatedAt:new Date().toISOString(),ledgerSourceCount:wanted.size,seenSourceCount:seen.size,missingSourceCount:missing.length,missing,offers};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
