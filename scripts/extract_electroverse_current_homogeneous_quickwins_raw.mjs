import fs from 'node:fs/promises';
const CACHE='data/electroverse/tariff_cache';
const man=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const wanted=new Set(['4179421','4179445','2651834','2651034','664412']);
const rows=[];
for(const sh of man.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    for(const e of row.tariff?.evses||[]){
      if(!wanted.has(String(e.pk)))continue;
      rows.push({
        locationPk:String(row.electroverseLocationPk),
        evsePk:e.pk,
        physicalReference:e.physicalReference,
        connectors:(e.connectors||[]).map(c=>({
          pk:c.pk,
          standard:c.standard,
          kilowatts:c.kilowatts,
          isChargingFree:c.isChargingFree,
          priceComponents:c.priceComponents,
          complexPricingDetail:c.complexPricingDetail
        }))
      });
    }
  }
}
await fs.writeFile('reports/electroverse/current-homogeneous-quickwins-raw.json',JSON.stringify({generatedAt:new Date().toISOString(),rows},null,2)+'\n');
console.log(JSON.stringify({count:rows.length,rows},null,2));