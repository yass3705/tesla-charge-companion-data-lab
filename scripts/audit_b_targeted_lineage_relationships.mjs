import fs from 'node:fs/promises';import zlib from 'node:zlib';
const locs=new Set(['346704','1405472','4220939','1291235']);
const map=JSON.parse(await fs.readFile('data/electroverse/irve_location_mapping.json','utf8'));
const man=JSON.parse(await fs.readFile('data/platforms/electroverse/france-evse/manifest.json','utf8'));
const rows=(map.mappings||[]).filter(x=>locs.has(String(x.electroverseLocationPk)));
const sourceToOffers=new Map();
for(const t of man.tiles||[]){
 const d=JSON.parse(zlib.gunzipSync(await fs.readFile('data/platforms/electroverse/france-evse/'+t.file)));
 for(const o of d.emspOffers||[]){
  const pks=[...(o?.metadata?.electroverseEvsePks||[]),...(o?.metadata?.electroverseEvsePk!=null?[o.metadata.electroverseEvsePk]:[]),...(o?.metadata?.electroverseAliasEvsePks||[])].map(String);
  for(const pk of pks){
    const a=sourceToOffers.get(pk)||[];
    a.push({evseIds:o.evseIds||[],identityMode:o?.metadata?.identityMode||null,offerId:o.id,physicalReferences:o?.metadata?.physicalReferences||o?.metadata?.physicalReference||null});
    sourceToOffers.set(pk,a);
  }
 }
}
const CACHE='data/electroverse/tariff_cache';
const cacheMan=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const sourceRows=[];
for(const sh of cacheMan.shards||[]){
 const d=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
 for(const row of Object.values(d.stations||{})){
  if(!locs.has(String(row?.electroverseLocationPk)))continue;
  const evses=row?.tariff?.evses||[];
  sourceRows.push({
   locationPk:String(row.electroverseLocationPk),file:sh.file,
   evses:evses.map(e=>({pk:e.pk,physicalReference:e.physicalReference,connectors:(e.connectors||[]).map(c=>({pk:c.pk,kilowatts:c.kilowatts,standard:typeof c.standard==='object'?c.standard?.name:c.standard})),offers:sourceToOffers.get(String(e.pk))||[]}))
  });
 }
}
const out={generatedAt:new Date().toISOString(),mappings:rows,sourceRows};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/b-targeted-lineage-relationship-audit.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
