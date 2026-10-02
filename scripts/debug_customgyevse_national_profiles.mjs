import fs from 'node:fs/promises';

const MAP='data/electroverse/irve_location_mapping.json';
const NATIONAL='data/national/france_public_charging_canonical.json';
const OUT='reports/electroverse/customgyevse-national-sample.json';
const targetLocations=new Set(['4222135','4225537','4226165']);
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const targets=[];
for(const m of mapping.mappings||[]){
  if(!targetLocations.has(String(m.electroverseLocationPk)))continue;
  for(const p of m.irvePdcIds||[])targets.push({locationPk:String(m.electroverseLocationPk),stationId:m.irveStationId??null,pdc:String(p),norm:norm(p)});
}
const targetSet=new Set(targets.map(x=>x.norm));
const nat=JSON.parse(await fs.readFile(NATIONAL,'utf8'));
const hits=[];
const seen=new Set();
function shallow(v){
  if(v==null||typeof v!=='object')return v;
  if(Array.isArray(v))return {__arrayLength:v.length,__sample:v.slice(0,3).map(x=>typeof x==='object'?Object.keys(x||{}):x)};
  const o={};
  for(const [k,x] of Object.entries(v)){
    if(x==null||typeof x!=='object')o[k]=x;
    else if(Array.isArray(x))o[k]={__arrayLength:x.length,__sample:x.slice(0,5).map(y=>typeof y==='object'?Object.keys(y||{}):y)};
    else o[k]={__keys:Object.keys(x).slice(0,30)};
  }
  return o;
}
function walk(v,path=[],parent=null){
  if(v==null)return;
  if(typeof v==='string'){
    const n=norm(v);
    if(targetSet.has(n)){
      const key=path.join('.');
      if(!seen.has(key)){seen.add(key);hits.push({path:key,value:v,parent:shallow(parent)});}
    }
    return;
  }
  if(typeof v!=='object')return;
  if(Array.isArray(v)){for(let i=0;i<v.length;i++)walk(v[i],[...path,String(i)],v);return;}
  for(const [k,x] of Object.entries(v))walk(x,[...path,k],v);
}
walk(nat);
await fs.mkdir('reports/electroverse',{recursive:true});
const out={generatedAt:new Date().toISOString(),targets,hits:hits.slice(0,200)};
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));


// Extended structural diagnostic 2026-10-02
const CACHE='data/electroverse/tariff_cache';
const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const source=[];
for(const sh of cman.shards||[]){
  const d=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(d.stations||{})){
    if(!targetLocations.has(String(row.electroverseLocationPk))) continue;
    source.push({
      locationPk:String(row.electroverseLocationPk),
      stationId:row.irveStationId??null,
      evses:(row?.tariff?.evses||[]).map(e=>({
        evsePk:e.pk??null,
        physicalReference:e.physicalReference??null,
        connectors:(e.connectors||[]).map(x=>({
          pk:x.pk??null,
          kilowatts:x.kilowatts??null,
          standard:x?.standard?.name??x?.standard??null,
          isChargingFree:x.isChargingFree??null,
          priceComponents:x.priceComponents??null,
          complexPricingDetail:x.complexPricingDetail??null
        }))
      }))
    });
  }
}
const byLocTargets=new Map();
for(const t of targets){
  const a=byLocTargets.get(t.locationPk)||[];
  a.push(t); byLocTargets.set(t.locationPk,a);
}
const structural=[];
for(const s of source){
  const tg=byLocTargets.get(s.locationPk)||[];
  const groups=new Map();
  for(const t of tg){
    const m=t.norm.match(/^FRGYMEC([12])(\d+)$/);
    if(!m) continue;
    const branch=m[1], tail=m[2];
    const g=groups.get(tail)||{};
    g[branch]=t.pdc; groups.set(tail,g);
  }
  structural.push({
    locationPk:s.locationPk,
    stationId:s.stationId,
    sourceEvses:s.evses,
    targetPairs:[...groups.entries()].map(([tail,g])=>({tail,branch1:g['1']??null,branch2:g['2']??null}))
  });
}
const prev=JSON.parse(await fs.readFile(OUT,'utf8'));
prev.structural=structural;
await fs.writeFile(OUT,JSON.stringify(prev,null,2)+'\n');
console.log(JSON.stringify({structuralLocations:structural.length, structural},null,2));
