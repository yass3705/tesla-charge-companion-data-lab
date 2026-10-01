import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse/s30-duplicate-physicalref-analysis.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const pricingSig=e=>JSON.stringify((e?.connectors||[]).map(c=>({
  isChargingFree:c?.isChargingFree??null,
  priceComponents:c?.priceComponents??null,
  complexPricingDetail:c?.complexPricingDetail??null,
  kilowatts:c?.kilowatts??null,
  standard:c?.standard?.name??c?.standard??null
})));
const opFromRef=raw=>{
  const s=String(raw??'').trim();
  const star=s.split('*').map(x=>x.trim()).filter(Boolean);
  if(star.length>=2 && /^FR$/i.test(star[0])) return star[1].toUpperCase();
  const n=norm(s); const m=n.match(/^FR([A-Z0-9]{1,8})E/); return m?m[1]:'';
};

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const owners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
 const k=norm(p); if(!k)continue; const s=owners.get(k)||new Set();s.add(String(m.irveStationId??''));owners.set(k,s);
}
const oman=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedSource=new Set(), publishedTargets=new Set();
for(const t of oman.tiles||[]){
 const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
 for(const o of tile.emspOffers||[]){
   for(const pk of o?.metadata?.electroverseEvsePks||[])if(pk!=null)publishedSource.add(String(pk));
   if(o?.metadata?.electroverseEvsePk!=null)publishedSource.add(String(o.metadata.electroverseEvsePk));
   for(const id of o.evseIds||[])publishedTargets.add(norm(id));
 }
}
const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const groups=[]; let residual=0,duplicateRefs=0,identicalDuplicateRefs=0;
for(const sh of cman.shards||[]){
 const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
 for(const row of Object.values(data.stations||{})){
   const es=(row?.tariff?.evses||[]).filter(e=>e?.pk!=null&&!publishedSource.has(String(e.pk))&&opFromRef(e?.physicalReference)==='S30');
   if(!es.length)continue; residual+=es.length;
   const m=byPk.get(String(row.electroverseLocationPk));
   const local=[...new Set((m?.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
   const available=local.filter(p=>!publishedTargets.has(p));
   const byRef=new Map();
   for(const e of es){
     const k=norm(e.physicalReference); const arr=byRef.get(k)||[];arr.push(e);byRef.set(k,arr);
   }
   const dup=[...byRef.entries()].filter(([,a])=>a.length>1);
   duplicateRefs+=dup.reduce((n,[,a])=>n+a.length,0);
   const identical=dup.filter(([,a])=>new Set(a.map(pricingSig)).size===1);
   identicalDuplicateRefs+=identical.reduce((n,[,a])=>n+a.length,0);

   const canonical=[...byRef.entries()].map(([k,a])=>({k,raw:String(a[0].physicalReference),entries:a,pricingVariants:new Set(a.map(pricingSig)).size}));
   const proposals=[];
   for(const x of canonical){
     const suffixMatches=available.filter(p=>x.k.length>=4&&p.endsWith(x.k)&&(owners.get(p)?.size||0)===1);
     const parentMatches=available.filter(p=>x.k.startsWith(p)&&x.k.length>p.length&&/^\d{1,2}$/.test(x.k.slice(p.length))&&(owners.get(p)?.size||0)===1);
     let trimmed=[];
     for(let len=Math.min(x.k.length-1,24);len>=6;len--){
       const s=x.k.slice(-len); const ms=available.filter(p=>p.endsWith(s)&&(owners.get(p)?.size||0)===1);
       if(ms.length===1){trimmed=ms;break;}
     }
     proposals.push({k:x.k,raw:x.raw,sourceCount:x.entries.length,pricingVariants:x.pricingVariants,
       suffixTarget:suffixMatches.length===1?suffixMatches[0]:null,
       parentTarget:parentMatches.length===1?parentMatches[0]:null,
       trimmedTarget:trimmed.length===1?trimmed[0]:null});
   }
   const deterministic=proposals.filter(x=>x.pricingVariants===1&&(x.suffixTarget||x.parentTarget||x.trimmedTarget));
   const targets=deterministic.map(x=>x.suffixTarget||x.parentTarget||x.trimmedTarget);
   const uniqueTargets=new Set(targets).size===targets.length;
   groups.push({
     electroverseLocationPk:String(row.electroverseLocationPk),
     irveStationId:m?.irveStationId??row.irveStationId??null,
     residualCount:es.length,
     uniquePhysicalRefs:byRef.size,
     duplicatePhysicalRefGroups:dup.length,
     identicalDuplicatePhysicalRefGroups:identical.length,
     availablePdcCount:available.length,
     deterministicCanonicalRefs:deterministic.length,
     deterministicUniqueTargets:uniqueTargets,
     fullyResolvableAfterDedup:canonical.length===deterministic.length&&uniqueTargets,
     proposals:proposals.slice(0,40)
   });
 }
}
const safe=groups.filter(g=>g.fullyResolvableAfterDedup);
const out={
 schemaVersion:1,generatedAt:new Date().toISOString(),
 residualSourceEvses:residual,
 duplicateSourceEvsesInsideDuplicateRefs:duplicateRefs,
 identicalPricingDuplicateSourceEvses:identicalDuplicateRefs,
 locations:groups.length,
 fullyResolvableLocationsAfterDedup:safe.length,
 fullyResolvableSourceEvsesAfterDedup:safe.reduce((n,g)=>n+g.residualCount,0),
 fullyResolvableCanonicalRefsAfterDedup:safe.reduce((n,g)=>n+g.uniquePhysicalRefs,0),
 safeGroups:safe.sort((a,b)=>b.residualCount-a.residualCount).slice(0,150),
 unresolvedSamples:groups.filter(g=>!g.fullyResolvableAfterDedup).sort((a,b)=>b.residualCount-a.residualCount).slice(0,100),
 policy:'Diagnostic only. Collapses duplicate S30 source EVSEs only when physicalReference and full connector/pricing signature are identical, then requires deterministic local globally-unique target identity. No proximity inference.'
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));

// rerun after connector-power and exact-set hardening 2026-10-01
