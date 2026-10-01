import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse/04dc180-residual-analysis.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const opFromRef=raw=>{
  const s=String(raw??'').trim();
  const star=s.split('*').map(x=>x.trim()).filter(Boolean);
  if(star.length>=2 && /^FR$/i.test(star[0])) return star[1].toUpperCase();
  const n=norm(s);
  const m=n.match(/^FR([A-Z0-9]{1,8})E/);
  if(m)return m[1];
  if(/^MAT\d+/i.test(s))return 'MAT';
  if(/^B\d+/i.test(s))return 'B';
  if(/^\d+$/.test(s))return 'NUMERIC';
  return n.slice(0,12)||'MISSING';
};

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));

const oman=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedSourcePks=new Set(),publishedTargets=new Set();
for(const t of oman.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
  for(const o of tile.emspOffers||[]){
    for(const pk of o?.metadata?.electroverseEvsePks||[]) if(pk!=null)publishedSourcePks.add(String(pk));
    if(o?.metadata?.electroverseEvsePk!=null) publishedSourcePks.add(String(o.metadata.electroverseEvsePk));
    for(const id of o.evseIds||[])publishedTargets.add(norm(id));
  }
}

const owners=new Map();
for(const m of mapping.mappings||[]) for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;
  const s=owners.get(k)||new Set();s.add(String(m.irveStationId??''));owners.set(k,s);
}

const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const groups=[];
let residual=0,locations=0;
for(const sh of cman.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const es=(row?.tariff?.evses||[]).filter(e=>{
      if(e?.pk==null||publishedSourcePks.has(String(e.pk)))return false;
      return opFromRef(e?.physicalReference)==='04DC180';
    });
    if(!es.length)continue;
    residual+=es.length;locations++;
    const m=byPk.get(String(row.electroverseLocationPk));
    const local=[...new Set((m?.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const available=local.filter(p=>!publishedTargets.has(p));
    const refs=es.map(e=>({e,k:norm(e.physicalReference),raw:String(e.physicalReference)}));

    const exactSuffix=[];
    for(const x of refs){
      const matches=available.filter(p=>x.k.length>=4&&p.endsWith(x.k)&&(owners.get(p)?.size||0)===1);
      if(matches.length===1)exactSuffix.push({evsePk:x.e.pk,target:matches[0],raw:x.raw});
    }
    const exactSuffixUniqueTargets=new Set(exactSuffix.map(x=>x.target)).size===exactSuffix.length;

    let commonPrefix='';
    if(available.length){
      commonPrefix=available[0];
      for(const p of available.slice(1)){
        let i=0;while(i<commonPrefix.length&&i<p.length&&commonPrefix[i]===p[i])i++;
        commonPrefix=commonPrefix.slice(0,i);if(!commonPrefix)break;
      }
    }
    const tailMap=new Map();let tailsUnique=true;
    for(const p of available){
      const tail=p.slice(commonPrefix.length);
      if(!tail||tailMap.has(tail)){tailsUnique=false;break;}
      tailMap.set(tail,p);
    }
    const tailMatches=refs.map(x=>({evsePk:x.e.pk,target:tailMap.get(x.k)||null,raw:x.raw}));
    const commonTailBijection=commonPrefix.length>=4&&tailsUnique&&
      tailMatches.every(x=>x.target&&(owners.get(x.target)?.size||0)===1)&&
      new Set(tailMatches.map(x=>x.target)).size===tailMatches.length;

    const homogeneousPricing=new Set(es.map(e=>JSON.stringify((e.connectors||[]).map(c=>({
      isChargingFree:c?.isChargingFree??null,
      priceComponents:c?.priceComponents??null,
      complexPricingDetail:c?.complexPricingDetail??null
    }))))).size===1;
    const connectorCounts=new Set(es.map(e=>(e.connectors||[]).length));
    const exactSetSafe=es.length===available.length&&available.length>0&&
      available.every(p=>(owners.get(p)?.size||0)===1)&&homogeneousPricing;

    let mode='none';
    if(exactSuffix.length===es.length&&exactSuffixUniqueTargets)mode='unique_suffix_bijection';
    else if(commonTailBijection)mode='common_tail_bijection';
    else if(exactSetSafe)mode=connectorCounts.size===1?'homogeneous_exact_set':'price_only_exact_set';

    groups.push({
      electroverseLocationPk:String(row.electroverseLocationPk),
      irveStationId:m?.irveStationId??row.irveStationId??null,
      residualCount:es.length,
      availablePdcCount:available.length,
      mode,
      homogeneousPricing,
      uniformConnectorCount:connectorCounts.size===1,
      commonPrefix:commonPrefix||null,
      refs:refs.slice(0,20).map(x=>({evsePk:x.e.pk,physicalReference:x.raw,connectorCount:(x.e.connectors||[]).length})),
      exactSuffix:exactSuffix.slice(0,20),
      commonTailMappings:commonTailBijection?tailMatches.slice(0,20):[]
    });
  }
}
const byMode={};
for(const g of groups)byMode[g.mode]=(byMode[g.mode]||0)+g.residualCount;
const out={
 schemaVersion:1,generatedAt:new Date().toISOString(),
 residualSourceEvses:residual,affectedLocations:locations,byMode,
 safelyRecoverableSourceEvses:Object.entries(byMode).filter(([k])=>k!=='none').reduce((n,[,v])=>n+v,0),
 safeGroups:groups.filter(g=>g.mode!=='none').sort((a,b)=>b.residualCount-a.residualCount).slice(0,200),
 unresolvedSamples:groups.filter(g=>g.mode==='none').sort((a,b)=>b.residualCount-a.residualCount).slice(0,100),
 policy:'Diagnostic only. 04DC180 bucket uses the exact same opFromRef classifier as the canonical unpublished-source ranking; local unpublished national targets; global target uniqueness; no proximity inference.'
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
