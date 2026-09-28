import fs from 'node:fs/promises';

const MAPPING='data/electroverse/irve_location_mapping.json';
const DIR='data/electroverse/tariff_cache';
const MANIFEST=`${DIR}/manifest.json`;
const OUT='reports/electroverse/incremental-selection.json';
const TTL_HOURS=Number(process.env.TTL_HOURS||168);
const LIMIT=Number(process.env.LIMIT||500);

const mapping=JSON.parse(await fs.readFile(MAPPING,'utf8'));
const manifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const cached=new Map();

for(const sh of manifest.shards||[]){
  if(!sh.count) continue;
  const data=JSON.parse(await fs.readFile(`${DIR}/${sh.file}`,'utf8'));
  for(const [pk,s] of Object.entries(data.stations||{})){
    cached.set(String(pk),{fetchedAt:s.fetchedAt||null});
  }
}

const now=Date.now(),ttlMs=TTL_HOURS*3600_000;
const rows=(mapping.mappings||[]).map(m=>{
  const pk=String(m.electroverseLocationPk);
  const c=cached.get(pk)||null;
  const t=c?.fetchedAt?Date.parse(c.fetchedAt):NaN;
  const ageMs=Number.isFinite(t)?Math.max(0,now-t):Infinity;
  let reason='fresh';
  if(!c) reason='new';
  else if(!Number.isFinite(t)) reason='missing_fetchedAt';
  else if(ageMs>=ttlMs) reason='stale';
  return {pk,irveStationId:m.irveStationId,reason,ageHours:Number.isFinite(ageMs)?Number((ageMs/3600000).toFixed(2)):null};
});
const rank={new:0,missing_fetchedAt:1,stale:2};
const due=rows.filter(x=>x.reason!=='fresh').sort((a,b)=>{
  const r=(rank[a.reason]??9)-(rank[b.reason]??9);
  return r||(b.ageHours??Infinity)-(a.ageHours??Infinity)||a.pk.localeCompare(b.pk);
});
const selected=due.slice(0,LIMIT);
const counts={fresh:0,new:0,missing_fetchedAt:0,stale:0};
for(const r of rows) counts[r.reason]=(counts[r.reason]||0)+1;
const report={
  generatedAt:new Date().toISOString(),
  storage:'sharded-v1',
  policy:{ttlHours:TTL_HOURS,limit:LIMIT},
  mappingPopulation:rows.length,
  cachePopulation:cached.size,
  counts,
  dueTotal:due.length,
  selectedCount:selected.length,
  selected
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,selected:selected.slice(0,20)},null,2));