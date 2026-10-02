import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const root=process.argv[2]||'.';
const wanted=new Set(["3551072","3551081","3551091","3551099","3551062","3551070","3551246","3551260","3551706","3551722"]);
const man=JSON.parse(await fs.readFile(root+'/data/platforms/electroverse/france-evse/manifest.json','utf8'));
const seen=new Map();
for(const t of man.tiles||[]){
  const d=JSON.parse(zlib.gunzipSync(await fs.readFile(root+'/data/platforms/electroverse/france-evse/'+t.file)));
  for(const o of d.emspOffers||[]){
    const pks=[...(o?.metadata?.electroverseEvsePks||[]),...(o?.metadata?.electroverseEvsePk!=null?[o.metadata.electroverseEvsePk]:[]),...(o?.metadata?.electroverseAliasEvsePks||[])].map(String);
    for(const pk of pks) if(wanted.has(pk)){
      const a=seen.get(pk)||[];
      a.push({id:o.id,identityMode:o?.metadata?.identityMode||null,evseIds:o.evseIds||[]});
      seen.set(pk,a);
    }
  }
}
const out={seenCount:seen.size,missing:[...wanted].filter(x=>!seen.has(x)),seen:Object.fromEntries(seen)};
console.log(JSON.stringify(out,null,2));
