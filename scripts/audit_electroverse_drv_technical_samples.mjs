import fs from 'node:fs/promises';

const CACHE='data/electroverse/tariff_cache';
const manifest=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const mapping=JSON.parse(await fs.readFile('data/electroverse/irve_location_mapping.json','utf8'));
const samplePks=new Set(['4184395','4185094','4302391','4184529','4185209','4184391','4184864','4184920']);
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const out={generatedAt:new Date().toISOString(),mappingKeys:{},locations:[]};

for(const pk of samplePks){
  const m=byPk.get(pk);
  if(m)for(const k of Object.keys(m))out.mappingKeys[k]=(out.mappingKeys[k]||0)+1;
}
for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const pk=String(row.electroverseLocationPk);
    if(!samplePks.has(pk))continue;
    const m=byPk.get(pk);
    out.locations.push({
      pk,
      mapping:m,
      rowKeys:Object.keys(row),
      tariffKeys:Object.keys(row.tariff||{}),
      evses:(row.tariff?.evses||[]).map(e=>({
        pk:e.pk??null,
        physicalReference:e.physicalReference??null,
        keys:Object.keys(e||{}),
        connectors:(e.connectors||[]).map(c=>({
          pk:c.pk??null,
          keys:Object.keys(c||{}),
          standard:c.standard??null,
          kilowatts:c.kilowatts??null,
          maxElectricPower:c.maxElectricPower??null,
          complexPricingDetail:c.complexPricingDetail??null
        }))
      }))
    });
  }
}
await fs.mkdir('reports',{recursive:true});
await fs.writeFile('reports/electroverse-fr-drv-technical-samples.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
