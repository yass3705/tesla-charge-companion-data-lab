import fs from 'node:fs/promises';
const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const man=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
let rowOut=null;
for(const sh of man.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    if(String(row.electroverseLocationPk)!=='4456304')continue;
    rowOut={locationPk:String(row.electroverseLocationPk),irvePdcIds:row.irvePdcIds||null,evses:(row.tariff?.evses||[]).map(e=>({
      pk:e.pk,physicalReference:e.physicalReference,
      connectors:(e.connectors||[]).map(c=>({pk:c.pk,standard:c.standard?.name||c.standard,kilowatts:c.kilowatts,priceComponents:c.priceComponents,complexPricingDetail:c.complexPricingDetail}))
    }))};
    break;
  }
  if(rowOut)break;
}
const m=(mapping.mappings||[]).find(x=>String(x.electroverseLocationPk)==='4456304');
const out={mapping:m,row:rowOut};
await fs.writeFile('reports/electroverse/location-4456304-debug.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));