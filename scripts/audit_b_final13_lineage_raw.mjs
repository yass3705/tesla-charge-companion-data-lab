import fs from 'node:fs/promises';
const CACHE='data/electroverse/tariff_cache';
const RES='reports/electroverse/b-residual-analysis.json';
const OUT='reports/electroverse/b-final13-lineage-raw-audit.json';
const res=JSON.parse(await fs.readFile(RES,'utf8'));
const wanted=new Set();
const byLoc=new Map();
for(const g of res.unresolvedSamples||[]){
  const loc=String(g.electroverseLocationPk);
  const s=new Set((g.refs||[]).map(r=>String(r.evsePk)));
  byLoc.set(loc,s);
  for(const x of s)wanted.add(x);
}
const man=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const rows=[];
for(const sh of man.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const loc=String(row?.electroverseLocationPk??'');
    if(!byLoc.has(loc))continue;
    const hit=[];
    for(const e of row?.tariff?.evses||[]){
      if(!wanted.has(String(e?.pk)))continue;
      const slim={};
      for(const [k,v] of Object.entries(e||{})){
        if(['connectors'].includes(k))continue;
        slim[k]=v;
      }
      slim.connectors=(e?.connectors||[]).map(c=>{
        const x={};
        for(const [k,v] of Object.entries(c||{})){
          if(['priceComponents','complexPricingDetail'].includes(k))continue;
          x[k]=v;
        }
        x.priceComponents=c?.priceComponents??null;
        x.complexPricingDetail=c?.complexPricingDetail??null;
        return x;
      });
      hit.push(slim);
    }
    if(hit.length){
      const rowSlim={};
      for(const [k,v] of Object.entries(row||{})){
        if(['tariff'].includes(k))continue;
        rowSlim[k]=v;
      }
      const tariffSlim={};
      for(const [k,v] of Object.entries(row?.tariff||{})){
        if(k==='evses')continue;
        tariffSlim[k]=v;
      }
      rows.push({locationPk:loc,shard:sh.file,row:rowSlim,tariff:tariffSlim,evses:hit});
    }
  }
}
const out={generatedAt:new Date().toISOString(),wantedEvses:wanted.size,locations:byLoc.size,rows};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({generatedAt:out.generatedAt,wantedEvses:out.wantedEvses,locations:out.locations,rows:rows.length,topLevelEvseKeys:[...new Set(rows.flatMap(r=>r.evses.flatMap(e=>Object.keys(e))))].sort(),rowKeys:[...new Set(rows.flatMap(r=>Object.keys(r.row||{})))].sort(),tariffKeys:[...new Set(rows.flatMap(r=>Object.keys(r.tariff||{})))].sort()},null,2));
