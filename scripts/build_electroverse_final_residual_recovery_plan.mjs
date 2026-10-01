import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MANIFEST=CACHE+'/manifest.json';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='data/platforms/electroverse/validated-mappings/final-residual-recovery-plan.json';

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const opFromRef=raw=>{
  const s=String(raw??'').trim();
  const star=s.split('*').map(x=>x.trim()).filter(Boolean);
  if(star.length>=2&&/^FR$/i.test(star[0]))return star[1].toUpperCase();
  const n=norm(s),m=n.match(/^FR([A-Z0-9]{1,8})E/);
  if(m)return m[1];
  if(/^MAT\d+/i.test(s))return 'MAT';
  if(/^B\d+/i.test(s))return 'B';
  if(/^\d+$/.test(s))return 'NUMERIC';
  return n.slice(0,12)||'MISSING';
};

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const owners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;
  const s=owners.get(k)||new Set();s.add(String(m.irveStationId??''));owners.set(k,s);
}
const oman=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedSourcePks=new Set(),publishedTargets=new Set();
for(const t of oman.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
  for(const o of tile.emspOffers||[]){
    for(const pk of o?.metadata?.electroverseEvsePks||[])if(pk!=null)publishedSourcePks.add(String(pk));
    if(o?.metadata?.electroverseEvsePk!=null)publishedSourcePks.add(String(o.metadata.electroverseEvsePk));
    for(const id of o.evseIds||[])publishedTargets.add(norm(id));
  }
}
const cman=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const individualMappings=[],groupMappings=[],stats={unique_suffix_bijection:0,common_tail_bijection:0,homogeneous_exact_set:0,price_only_exact_set:0};

for(const sh of cman.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const pending=(row?.tariff?.evses||[]).filter(e=>e?.pk!=null&&!publishedSourcePks.has(String(e.pk)));
    if(!pending.length)continue;
    const byOp=new Map();
    for(const e of pending){const op=opFromRef(e?.physicalReference);const a=byOp.get(op)||[];a.push(e);byOp.set(op,a);}
    const m=byPk.get(String(row.electroverseLocationPk));
    const local=[...new Set((m?.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const available=local.filter(p=>!publishedTargets.has(p));
    if(!available.length)continue;

    for(const [op,es] of byOp){
      const refs=es.map(e=>({e,k:norm(e.physicalReference),raw:String(e.physicalReference)}));
      const exactSuffix=[];
      for(const x of refs){
        const matches=available.filter(p=>x.k.length>=4&&p.endsWith(x.k)&&(owners.get(p)?.size||0)===1);
        if(matches.length===1)exactSuffix.push({evsePk:x.e.pk,target:matches[0],raw:x.raw});
      }
      if(exactSuffix.length===es.length&&new Set(exactSuffix.map(x=>x.target)).size===exactSuffix.length){
        for(const x of exactSuffix)individualMappings.push({
          mode:'unique_suffix_bijection',operator:op,electroverseLocationPk:String(row.electroverseLocationPk),
          electroverseEvsePk:x.evsePk,physicalReference:x.raw,targetPdc:x.target,irveStationId:m?.irveStationId??null
        });
        stats.unique_suffix_bijection+=es.length;
        continue;
      }

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
      const commonTailBijection=commonPrefix.length>=4&&tailsUnique&&tailMatches.every(x=>x.target&&(owners.get(x.target)?.size||0)===1)&&
        new Set(tailMatches.map(x=>x.target)).size===tailMatches.length;
      if(commonTailBijection){
        for(const x of tailMatches)individualMappings.push({
          mode:'common_tail_bijection',operator:op,electroverseLocationPk:String(row.electroverseLocationPk),
          electroverseEvsePk:x.evsePk,physicalReference:x.raw,targetPdc:x.target,irveStationId:m?.irveStationId??null
        });
        stats.common_tail_bijection+=es.length;
        continue;
      }

      const homogeneousPricing=new Set(es.map(e=>JSON.stringify((e.connectors||[]).map(c=>({
        isChargingFree:c?.isChargingFree??null,priceComponents:c?.priceComponents??null,complexPricingDetail:c?.complexPricingDetail??null
      }))))).size===1;
      const connectorCounts=new Set(es.map(e=>(e.connectors||[]).length));
      const exactSetSafe=es.length===available.length&&available.length>0&&available.every(p=>(owners.get(p)?.size||0)===1)&&homogeneousPricing;
      if(exactSetSafe){
        const mode=connectorCounts.size===1?'homogeneous_exact_set':'price_only_exact_set';
        groupMappings.push({
          mode,operator:op,electroverseLocationPk:String(row.electroverseLocationPk),irveStationId:m?.irveStationId??null,
          sourceEvsePks:es.map(e=>e.pk),physicalReferences:es.map(e=>String(e.physicalReference)),
          targetPdcs:available,uniformConnectorCount:connectorCounts.size===1
        });
        stats[mode]+=es.length;
      }
    }
  }
}

const dedupeIndividual=new Map();
for(const x of individualMappings){
  const k=x.electroverseLocationPk+':'+x.electroverseEvsePk;
  if(!dedupeIndividual.has(k))dedupeIndividual.set(k,x);
}
const dedupeGroups=new Map();
for(const g of groupMappings){
  const k=g.electroverseLocationPk+'|'+g.operator+'|'+g.mode+'|'+[...g.sourceEvsePks].sort().join(',');
  if(!dedupeGroups.has(k))dedupeGroups.set(k,g);
}
const out={
  schemaVersion:1,generatedAt:new Date().toISOString(),dataset:'electroverse-france-final-residual-recovery-plan',
  sourceManifestGeneratedAt:oman.generatedAt,
  policy:'Only residual mappings proven against the current overlay. Individual mappings require exact unique local/global target identity; group mappings require exact source/target cardinality, globally unique targets, and homogeneous raw pricing. No proximity inference.',
  stats,
  individualMappings:[...dedupeIndividual.values()],
  groupMappings:[...dedupeGroups.values()]
};
await fs.mkdir('data/platforms/electroverse/validated-mappings',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({generatedAt:out.generatedAt,stats:out.stats,individualMappings:out.individualMappings.length,groupMappings:out.groupMappings.length,totalRecoverable:Object.values(out.stats).reduce((a,b)=>a+b,0)},null,2));
