import fs from 'node:fs/promises';
import crypto from 'node:crypto';

const DIR='data/electroverse/tariff_cache';
const MANIFEST=`${DIR}/manifest.json`;
const MAPPING='data/electroverse/irve_location_mapping.json';
const OUT='reports/electroverse/cache-audit.json';

const manifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const mapping=JSON.parse(await fs.readFile(MAPPING,'utf8'));
const expected=new Set((mapping.mappings||[]).map(x=>String(x.electroverseLocationPk)));
const seen=new Set(), duplicates=[], wrongShard=[], invalid=[], hashMismatch=[];
let stationCount=0, connectorCount=0, freeConnectors=0, pricedConnectors=0;

const stable=x=>Array.isArray(x)?x.map(stable):(x&&typeof x==='object'
 ? Object.fromEntries(Object.keys(x).sort().map(k=>[k,stable(x[k])])) : x);
const hash=x=>crypto.createHash('sha256').update(JSON.stringify(stable(x))).digest('hex');
const shardFor=pk=>crypto.createHash('sha1').update(String(pk)).digest()[0]%128;

for(let i=0;i<128;i++){
  const file=`${DIR}/shard-${String(i).padStart(3,'0')}.json`;
  const data=JSON.parse(await fs.readFile(file,'utf8'));
  for(const [pk,s] of Object.entries(data.stations||{})){
    stationCount++;
    if(seen.has(pk)) duplicates.push(pk); else seen.add(pk);
    if(shardFor(pk)!==i) wrongShard.push(pk);
    if(!s.tariff || !s.tariffHash) { invalid.push(pk); continue; }
    if(hash(s.tariff)!==s.tariffHash) hashMismatch.push(pk);
    for(const e of s.tariff.evses||[]) for(const c of e.connectors||[]){
      connectorCount++;
      if(c.isChargingFree===true) freeConnectors++;
      if((c.priceComponents?.length||0)>0 || c.complexPricingDetail) pricedConnectors++;
    }
  }
}
const missing=[...expected].filter(pk=>!seen.has(pk));
const extra=[...seen].filter(pk=>!expected.has(pk));
const report={
  generatedAt:new Date().toISOString(),
  mappingPopulation:expected.size,
  manifestPopulation:manifest.totalStations,
  actualPopulation:stationCount,
  shardCount:manifest.shards?.length||0,
  nonEmptyShards:(manifest.shards||[]).filter(x=>x.count>0).length,
  duplicates,missing,extra,wrongShard,invalid,hashMismatch,
  connectors:{total:connectorCount,free:freeConnectors,withPricingPayload:pricedConnectors},
  ok: expected.size===stationCount && manifest.totalStations===stationCount &&
      duplicates.length===0 && missing.length===0 && extra.length===0 &&
      wrongShard.length===0 && invalid.length===0 && hashMismatch.length===0
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
if(!report.ok) process.exitCode=2;
