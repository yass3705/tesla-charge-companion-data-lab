import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const targetLocation='546812';
const manifest=JSON.parse(await fs.readFile('data/electroverse/tariff_cache/manifest.json','utf8'));
const out=[];
for(const sh of manifest.shards||[]){
  const j=JSON.parse(await fs.readFile('data/electroverse/tariff_cache/'+sh.file,'utf8'));
  for(const row of Object.values(j.stations||{})){
    if(String(row.electroverseLocationPk)!==targetLocation) continue;
    for(const e of row?.tariff?.evses||[]){
      if(!String(e?.physicalReference||'').includes('S30')) continue;
      out.push({
        evsePk:e.pk,
        physicalReference:e.physicalReference,
        connectors:(e.connectors||[]).map(c=>({
          pk:c.pk,
          kilowatts:c.kilowatts,
          standard:c.standard,
          isChargingFree:c.isChargingFree,
          priceComponents:c.priceComponents,
          complexPricingDetail:c.complexPricingDetail
        }))
      });
    }
  }
}
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/s30-sample-profiles.json',JSON.stringify({generatedAt:new Date().toISOString(),targetLocation,out},null,2)+'\n');
console.log(JSON.stringify(out,null,2));
