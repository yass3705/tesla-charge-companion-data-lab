import fs from 'node:fs/promises';

const targets=new Set(['1028573','1036491','1214346','1214350','4179421','4179445']);
const shards=['data/electroverse/tariff_cache/shard-033.json','data/electroverse/tariff_cache/shard-043.json','data/electroverse/tariff_cache/shard-105.json'];
const out=[];
for(const file of shards){
  const j=JSON.parse(await fs.readFile(file,'utf8'));
  for(const row of Object.values(j.stations||{})){
    for(const e of row?.tariff?.evses||[]){
      if(targets.has(String(e?.pk))){
        out.push({
          shard:file,
          electroverseLocationPk:String(row.electroverseLocationPk),
          evsePk:e.pk,
          physicalReference:e.physicalReference,
          connectors:e.connectors||[]
        });
      }
    }
  }
}
console.log(JSON.stringify(out,null,2));
