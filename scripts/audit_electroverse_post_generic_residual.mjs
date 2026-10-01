import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const txt=x=>String(x??'').trim();
const opOf=p=>{const m=String(p||'').match(/^FR([A-Z0-9]{1,6})E/);return m?m[1]:'UNKNOWN';};
const CACHE='data/electroverse/tariff_cache', MAP='data/electroverse/irve_location_mapping.json', OVERLAY='data/platforms/electroverse/france-evse';
const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const manifest=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const om=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const published=new Set();
for(const t of om.tiles||[]){const p=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)).toString('utf8'));for(const o of p.emspOffers||[])for(const id of o.evseIds||[])published.add(norm(id));}
const fam=new Map();
const get=op=>{if(!fam.has(op))fam.set(op,{operator:op,locations:new Set(),missing:new Set(),unresolved:0,card:{},samples:[]});return fam.get(op);};
for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk));if(!m)continue;
    const local=[...new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const missingAll=local.filter(p=>!published.has(p));if(!missingAll.length)continue;
    const unresolved=(row.tariff?.evses||[]).map(e=>txt(e?.physicalReference)).filter(Boolean).filter(raw=>{const k=norm(raw);return !local.includes(k)&&!published.has(k);});
    const ops=[...new Set(missingAll.map(opOf))];
    for(const op of ops){
      const r=get(op), miss=missingAll.filter(p=>opOf(p)===op);
      r.locations.add(String(row.electroverseLocationPk));for(const p of miss)r.missing.add(p);r.unresolved+=unresolved.length;
      const key=`${unresolved.length}->${miss.length}|all=${missingAll.length}|ops=${ops.sort().join(',')}`;r.card[key]=(r.card[key]||0)+1;
      if(r.samples.length<8)r.samples.push({locationPk:String(row.electroverseLocationPk),unresolvedRefs:unresolved.slice(0,10),missingPdcs:miss,allMissing:missingAll});
    }
  }
}
const families=[...fam.values()].map(r=>({operator:r.operator,locations:r.locations.size,missingPdcs:r.missing.size,unresolvedRefs:r.unresolved,cardinality:Object.entries(r.card).sort((a,b)=>b[1]-a[1]).slice(0,20).map(([key,count])=>({key,count})),samples:r.samples})).sort((a,b)=>b.missingPdcs-a.missingPdcs);
const out={generatedAt:new Date().toISOString(),publishedEvses:om.stats?.publishedEvses,remainingFamilyCount:families.length,remainingMissingPdcs:families.reduce((n,x)=>n+x.missingPdcs,0),families};
await fs.mkdir('reports',{recursive:true});await fs.writeFile('reports/electroverse-fr-post-generic-residual.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({generatedAt:out.generatedAt,publishedEvses:out.publishedEvses,remainingFamilyCount:out.remainingFamilyCount,remainingMissingPdcs:out.remainingMissingPdcs,top:families.slice(0,100).map(x=>({operator:x.operator,missingPdcs:x.missingPdcs,locations:x.locations,unresolvedRefs:x.unresolvedRefs,cardinality:x.cardinality.slice(0,8)}))},null,2));
