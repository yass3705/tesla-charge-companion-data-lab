import fs from 'node:fs/promises';
const CACHE='data/electroverse/tariff_cache';
const loc='4220939';
const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
let evses=[];
for(const sh of cman.shards||[]){
 const d=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
 for(const row of Object.values(d.stations||{})){
  if(String(row?.electroverseLocationPk)!==loc)continue;
  evses=row?.tariff?.evses||[];
 }
}
const slim=evses.filter(e=>{
 const cs=e?.connectors||[];return cs.some(c=>Number(c?.kilowatts)===22);
}).map(e=>({
 pk:e.pk,ref:e.physicalReference,
 connectors:(e.connectors||[]).map(c=>({
  pk:c.pk,kw:c.kilowatts,std:typeof c.standard==='object'?c.standard?.name:c.standard,
  free:c.isChargingFree,pc:c.priceComponents,complex:c.complexPricingDetail
 }))
}));
const sig=x=>JSON.stringify(x.connectors.map(c=>({kw:c.kw,std:c.std,free:c.free,pc:c.pc,complex:c.complex})));
const out={generatedAt:new Date().toISOString(),count:slim.length,pricingSignatureCount:new Set(slim.map(sig)).size,rows:slim};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/b-dree-22kw-source-audit.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({count:out.count,pricingSignatureCount:out.pricingSignatureCount,rows:slim.map(x=>({pk:x.pk,ref:x.ref,connectors:x.connectors.map(c=>({kw:c.kw,std:c.std,pc:c.pc}))}))},null,2));