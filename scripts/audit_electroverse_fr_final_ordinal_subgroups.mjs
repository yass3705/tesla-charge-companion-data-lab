import fs from 'node:fs/promises';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const MANIFEST=CACHE+'/manifest.json';
const OUT='reports/electroverse-fr-final-ordinal-subgroup-audit.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const txt=x=>String(x??'').trim();
const inc=(o,k,n=1)=>o[k]=(o[k]||0)+n;
const top=o=>Object.entries(o).sort((a,b)=>b[1]-a[1]).map(([operator,count])=>({operator,count}));
const opOf=p=>{const m=String(p||'').match(/^FR([A-Z0-9]{1,6})E/);return m?m[1]:'UNKNOWN';};

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const manifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const globalPdcOwners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;
  const s=globalPdcOwners.get(k)||new Set();
  s.add(String(m.irveStationId||m.electroverseLocationPk||''));
  globalPdcOwners.set(k,s);
}

const byOperator={},stationsByOperator={},samples=[];
let candidateRefs=0,candidateStations=0;

for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk)); if(!m)continue;
    const localRaw=(m.irvePdcIds||row.irvePdcIds||[]).filter(Boolean);
    const local=[...new Set(localRaw.map(norm).filter(Boolean))];
    if(!local.length)continue;

    const unresolved=[];
    for(const e of row.tariff?.evses||[]){
      const raw=txt(e?.physicalReference); if(!raw)continue;
      const k=norm(raw);
      if(local.includes(k))continue;
      const parent=local.filter(p=>k.startsWith(p)&&k.length>p.length&&/^\d{1,2}$/.test(k.slice(p.length)));
      if(parent.length)continue;
      if(k.length>=4&&local.filter(p=>p.endsWith(k)).length===1)continue;
      const mm=raw.match(/^(.*?)[\s_\-\/]*([0-9]{1,2})$/);
      if(!mm||!mm[1])continue;
      unresolved.push({e,raw,stem:norm(mm[1]),ord:Number(mm[2])});
    }
    if(!unresolved.length)continue;

    const groups=new Map();
    for(const x of unresolved){
      const a=groups.get(x.stem)||[];
      a.push(x);groups.set(x.stem,a);
    }

    let stationGain=0;
    for(const [stem,items] of groups){
      const ords=items.map(x=>x.ord);
      if(new Set(ords).size!==items.length)continue;
      const wanted=new Set(ords),matches=[];
      for(const width of [1,2]){
        const pdcGroups=new Map();
        for(const p of local){
          if(p.length<=width)continue;
          const tail=p.slice(-width);if(!/^\d+$/.test(tail))continue;
          const prefix=p.slice(0,-width),ord=Number(tail);
          const a=pdcGroups.get(prefix)||[];a.push({p,ord});pdcGroups.set(prefix,a);
        }
        for(const [prefix,rows] of pdcGroups){
          if(rows.length!==items.length)continue;
          if(new Set(rows.map(r=>r.ord)).size!==rows.length)continue;
          if(rows.some(r=>!wanted.has(r.ord)))continue;
          if(rows.some(r=>(globalPdcOwners.get(r.p)?.size||0)!==1))continue;
          matches.push({width,prefix,rows});
        }
      }
      if(matches.length!==1)continue;
      const op=opOf(matches[0].rows[0].p);
      candidateRefs+=items.length;stationGain+=items.length;inc(byOperator,op,items.length);
      if(samples.length<100)samples.push({
        locationPk:String(row.electroverseLocationPk),operator:op,stem,
        physicalReferences:items.map(x=>x.raw),
        targetPdcs:matches[0].rows.sort((a,b)=>a.ord-b.ord).map(x=>x.p),
        ordinalWidth:matches[0].width
      });
    }
    if(stationGain){
      candidateStations++;
      const op=opOf(local[0]);inc(stationsByOperator,op,1);
    }
  }
}

const report={
  generatedAt:new Date().toISOString(),
  candidateRefs,candidateStations,
  candidateRefsByOperator:top(byOperator),
  candidateStationsByOperator:top(stationsByOperator),
  samples
};
await fs.mkdir('reports',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
