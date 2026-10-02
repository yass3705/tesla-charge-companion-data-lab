import fs from 'node:fs/promises';import zlib from 'node:zlib';
const wanted=new Set(["831351","128739","128820","128821"]);
const man=JSON.parse(await fs.readFile('data/platforms/electroverse/france-evse/manifest.json','utf8'));
const hits=[];
for(const t of man.tiles||[]){
 const d=JSON.parse(zlib.gunzipSync(await fs.readFile('data/platforms/electroverse/france-evse/'+t.file)));
 for(const o of d.emspOffers||[]){
  const pks=[...(o?.metadata?.electroverseEvsePks||[]),...(o?.metadata?.electroverseEvsePk!=null?[o.metadata.electroverseEvsePk]:[]),...(o?.metadata?.electroverseAliasEvsePks||[])].map(String);
  const h=pks.filter(x=>wanted.has(x)); if(h.length)hits.push({hits:h,evseIds:o.evseIds,identityMode:o?.metadata?.identityMode||null,offerId:o.id,physicalReferences:o?.metadata?.physicalReferences||o?.metadata?.physicalReference||null});
 }
}
console.log(JSON.stringify({wanted:[...wanted],hits},null,2));