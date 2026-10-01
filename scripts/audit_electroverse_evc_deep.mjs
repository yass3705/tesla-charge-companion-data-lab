import fs from 'node:fs/promises';
const CACHE='data/electroverse/tariff_cache';
const manifest=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
let hit=null, shardFile=null;
for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    if(String(row.electroverseLocationPk)==='4062802'){hit=row;shardFile=sh.file;break;}
  }
  if(hit)break;
}
if(!hit)throw new Error('location 4062802 not found');
const out={
  generatedAt:new Date().toISOString(),
  shardFile,
  locationPk:String(hit.electroverseLocationPk),
  irvePdcIds:hit.irvePdcIds||null,
  tariffHash:hit.tariffHash||null,
  fetchedAt:hit.fetchedAt||null,
  evseCount:(hit.tariff?.evses||[]).length,
  evses:(hit.tariff?.evses||[]).map(e=>({
    pk:e.pk??null,
    physicalReference:e.physicalReference??null,
    connectors:(e.connectors||[]).map(c=>({
      pk:c.pk??null,
      standard:c.standard??null,
      kilowatts:c.kilowatts??null,
      currency:c.complexPricingDetail?.currency??null,
      restrictions:c.complexPricingDetail?.restrictions??null
    }))
  }))
};
await fs.mkdir('reports',{recursive:true});
await fs.writeFile('reports/electroverse-fr-evc-location-4062802.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
