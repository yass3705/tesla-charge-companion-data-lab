import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MANIFEST=CACHE+'/manifest.json';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse-fr-all-remaining-families.json';

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const txt=x=>String(x??'').trim();
const opOf=p=>{const m=String(p||'').match(/^FR([A-Z0-9]{1,6})E/);return m?m[1]:'UNKNOWN';};

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const manifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const overlayManifest=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const published=new Set();
for(const t of overlayManifest.tiles||[]){
  const gz=await fs.readFile(OVERLAY+'/'+t.file);
  const p=JSON.parse(zlib.gunzipSync(gz).toString('utf8'));
  for(const o of p.emspOffers||[])for(const id of o.evseIds||[])published.add(norm(id));
}

const fam=new Map();
const get=op=>{
  if(!fam.has(op))fam.set(op,{operator:op,locations:new Set(),missingPdcs:new Set(),unresolvedRefs:0,unresolvedLocations:0,shape:{},cardinality:{},samples:[]});
  return fam.get(op);
};
for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk)); if(!m)continue;
    const local=[...new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const missingAll=local.filter(p=>!published.has(p));
    if(!missingAll.length)continue;
    const ops=[...new Set(missingAll.map(opOf))];
    const unresolved=[];
    for(const e of row.tariff?.evses||[]){
      const raw=txt(e?.physicalReference);if(!raw)continue;
      const k=norm(raw);
      if(local.includes(k)||published.has(k))continue;
      unresolved.push({raw,k});
    }
    for(const op of ops){
      const r=get(op);
      const missing=missingAll.filter(p=>opOf(p)===op);
      r.locations.add(String(row.electroverseLocationPk));
      for(const p of missing)r.missingPdcs.add(p);
      if(unresolved.length){
        r.unresolvedLocations++;
        r.unresolvedRefs+=unresolved.length;
        const key=`${unresolved.length}->${missing.length}|allUnclaimed=${missingAll.length}|ops=${ops.sort().join(',')}`;
        r.cardinality[key]=(r.cardinality[key]||0)+1;
        for(const x of unresolved){
          const shape=/^\d+$/.test(x.raw)?'digits':/^[A-Za-z0-9]+$/.test(x.raw)?'alnum':x.raw.includes('*')?'asterisk':x.raw.includes('-')?'hyphenated':x.raw.includes('_')?'underscore':x.raw.includes('#')?'hash':'other';
          r.shape[shape]=(r.shape[shape]||0)+1;
        }
        if(r.samples.length<12)r.samples.push({
          locationPk:String(row.electroverseLocationPk),
          unresolvedRefs:unresolved.slice(0,12).map(x=>x.raw),
          missingPdcs:missing,
          allUnclaimedPdcs:missingAll
        });
      }
    }
  }
}
const families=[...fam.values()].map(r=>({
  operator:r.operator,
  locations:r.locations.size,
  missingPdcs:r.missingPdcs.size,
  unresolvedRefs:r.unresolvedRefs,
  unresolvedLocations:r.unresolvedLocations,
  shape:Object.entries(r.shape).sort((a,b)=>b[1]-a[1]).map(([key,count])=>({key,count})),
  cardinality:Object.entries(r.cardinality).sort((a,b)=>b[1]-a[1]).slice(0,25).map(([key,count])=>({key,count})),
  samples:r.samples
})).sort((a,b)=>b.missingPdcs-a.missingPdcs||a.operator.localeCompare(b.operator));

const report={
  generatedAt:new Date().toISOString(),
  publishedEvses:overlayManifest.stats?.publishedEvses||null,
  remainingFamilyCount:families.length,
  remainingMissingPdcs:families.reduce((n,x)=>n+x.missingPdcs,0),
  families
};
await fs.mkdir('reports',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({
  generatedAt:report.generatedAt,
  publishedEvses:report.publishedEvses,
  remainingFamilyCount:report.remainingFamilyCount,
  remainingMissingPdcs:report.remainingMissingPdcs,
  top:families.slice(0,80).map(x=>({operator:x.operator,missingPdcs:x.missingPdcs,locations:x.locations,unresolvedRefs:x.unresolvedRefs,topCardinality:x.cardinality.slice(0,5)}))
},null,2));
