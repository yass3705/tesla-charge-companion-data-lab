import fs from 'node:fs/promises';
const CACHE='data/electroverse/tariff_cache';
const LOC='4548206';
const OUT='reports/electroverse/b-boeuf-rouge-full-cache-audit.json';
const man=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
let station=null,shard=null;
for(const sh of man.shards||[]){
  const d=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  if(d.stations?.[LOC]){station=d.stations[LOC];shard=sh.file;break;}
}
if(!station)throw new Error('location not found');
const out={generatedAt:new Date().toISOString(),shard,station};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
const sig=e=>JSON.stringify((e.connectors||[]).map(c=>({kilowatts:c.kilowatts,standard:c.standard,isChargingFree:c.isChargingFree,priceComponents:c.priceComponents,complexPricingDetail:c.complexPricingDetail})));
const rows=(station.tariff?.evses||[]).map(e=>({pk:e.pk,ref:e.physicalReference,kw:(e.connectors||[]).map(c=>c.kilowatts),pricingSig:sig(e)}));
console.log(JSON.stringify({rows:rows.map(x=>({pk:x.pk,ref:x.ref,kw:x.kw,sigLen:x.pricingSig.length})),numeric1234650945SamePricing:new Set(rows.filter(x=>x.ref==='1234650945').map(x=>x.pricingSig)).size===1,b188SamePricing:new Set(rows.filter(x=>x.ref==='B188').map(x=>x.pricingSig)).size===1},null,2));
