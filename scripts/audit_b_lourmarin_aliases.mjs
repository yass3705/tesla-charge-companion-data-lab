import fs from 'node:fs/promises';
const CACHE='data/electroverse/tariff_cache';
const loc='1291235';
const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
let evses=[];
for(const sh of cman.shards||[]){
 const d=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
 for(const row of Object.values(d.stations||{})){
  if(String(row?.electroverseLocationPk)!==loc)continue;
  evses=row?.tariff?.evses||[];
 }
}
const sig=e=>JSON.stringify((e.connectors||[]).map(c=>({
 k:c.kilowatts,s:typeof c.standard==='object'?c.standard?.name:c.standard,
 free:c.isChargingFree,pc:c.priceComponents,complex:c.complexPricingDetail
})));
const rows=evses.map(e=>({pk:e.pk,ref:e.physicalReference,connectors:(e.connectors||[]).map(c=>({kw:c.kilowatts,std:typeof c.standard==='object'?c.standard?.name:c.standard})),pricingSig:sig(e)}));
const g22=rows.filter(r=>r.connectors.length===1&&Number(r.connectors[0].kw)===22&&r.connectors[0].std==='IEC_62196_T2');
const out={generatedAt:new Date().toISOString(),rows,g22Count:g22.length,g22PricingSignatures:new Set(g22.map(x=>x.pricingSig)).size,g22};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/b-lourmarin-alias-audit.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({g22Count:out.g22Count,g22PricingSignatures:out.g22PricingSignatures,g22:g22.map(x=>({pk:x.pk,ref:x.ref}))},null,2));