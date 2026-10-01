import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse/remaining-batch-analysis.json';
const VALIDATED='data/platforms/electroverse/validated-mappings/remaining-unique-suffix-residual.json';
const P01_VALIDATED='data/platforms/electroverse/validated-mappings/p01-structured-residual.json';

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
let p01Validated={nationalOrphanSources:[]};
try{p01Validated=JSON.parse(await fs.readFile(P01_VALIDATED,'utf8'));}catch(e){if(e?.code!=='ENOENT')throw e;}
const classifiedNationalOrphanPks=new Set((p01Validated.nationalOrphanSources||[]).map(x=>String(x.electroverseEvsePk)).filter(Boolean));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));

const oman=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedSourcePks=new Set(),publishedTargets=new Set();
for(const t of oman.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
  for(const o of tile.emspOffers||[]){
    for(const pk of o?.metadata?.electroverseEvsePks||[]) if(pk!=null)publishedSourcePks.add(String(pk));
    for(const pk of o?.metadata?.electroverseAliasEvsePks||[]) if(pk!=null)publishedSourcePks.add(String(pk));
    if(o?.metadata?.electroverseEvsePk!=null)publishedSourcePks.add(String(o.metadata.electroverseEvsePk));
    for(const id of o.evseIds||[])publishedTargets.add(norm(id));
  }
}

const owners=new Map();
for(const m of mapping.mappings||[]) for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;
  const s=owners.get(k)||new Set();s.add(String(m.irveStationId??''));owners.set(k,s);
}

const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const byOperator=new Map();
const validatedMappings=[];

function addOp(op,group){
  let x=byOperator.get(op);
  if(!x)x={operator:op,residualSourceEvses:0,affectedLocations:0,byMode:{},safeGroups:[],unresolvedSamples:[]};
  x.residualSourceEvses+=group.residualCount;
  x.affectedLocations++;
  x.byMode[group.mode]=(x.byMode[group.mode]||0)+group.residualCount;
  if(group.mode!=='none'){
    if(x.safeGroups.length<100)x.safeGroups.push(group);
  }else if(x.unresolvedSamples.length<20)x.unresolvedSamples.push(group);
  byOperator.set(op,x);
}

for(const sh of cman.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const pending=(row?.tariff?.evses||[]).filter(e=>e?.pk!=null&&!publishedSourcePks.has(String(e.pk))&&!classifiedNationalOrphanPks.has(String(e.pk)));
    if(!pending.length)continue;
    const byOp=new Map();
    for(const e of pending){
      const op=opFromRef(e?.physicalReference);
      const a=byOp.get(op)||[];a.push(e);byOp.set(op,a);
    }
    const m=byPk.get(String(row.electroverseLocationPk));
    const local=[...new Set((m?.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const available=local.filter(p=>!publishedTargets.has(p));

    for(const [op,es] of byOp){
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
      const technicalProfiles=new Set(es.map(e=>JSON.stringify((e.connectors||[]).map(c=>({
        kilowatts:c?.kilowatts??null,
        standard:c?.standard?.name??c?.standard??null
      })).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b))))));
      const exactSetSafe=es.length===available.length&&available.length>0&&
        pending.length===es.length&&
        available.every(p=>(owners.get(p)?.size||0)===1)&&
        homogeneousPricing&&technicalProfiles.size===1;

      let mode='none';
      if(exactSuffix.length===es.length&&exactSuffixUniqueTargets)mode='unique_suffix_bijection';
      else if(commonTailBijection)mode='common_tail_bijection';
      else if(exactSetSafe)mode=connectorCounts.size===1?'homogeneous_exact_set':'price_only_exact_set';

      const group={
        electroverseLocationPk:String(row.electroverseLocationPk),
        irveStationId:m?.irveStationId??row.irveStationId??null,
        residualCount:es.length,availablePdcCount:available.length,mode,
        homogeneousPricing,uniformConnectorCount:connectorCounts.size===1,
        commonPrefix:commonPrefix||null,
        refs:refs.slice(0,20).map(x=>({evsePk:x.e.pk,physicalReference:x.raw,connectorCount:(x.e.connectors||[]).length})),
        exactSuffix:exactSuffix.slice(0,20),
        commonTailMappings:commonTailBijection?tailMatches.slice(0,20):[]
      };
      addOp(op,group);
      if(mode==='unique_suffix_bijection'){
        for(const x of exactSuffix){
          validatedMappings.push({
            operator:op,
            electroverseLocationPk:String(row.electroverseLocationPk),
            electroverseEvsePk:x.evsePk,
            physicalReference:x.raw,
            targetPdc:x.target,
            evidence:{mode:'strict_unique_suffix_bijection',irveStationId:group.irveStationId}
          });
        }
      }
    }
  }
}

const operators=[...byOperator.values()].map(x=>({
  ...x,
  safelyRecoverableSourceEvses:Object.entries(x.byMode).filter(([k])=>k!=='none').reduce((n,[,v])=>n+v,0),
  safeGroups:x.safeGroups.sort((a,b)=>b.residualCount-a.residualCount)
})).sort((a,b)=>b.residualSourceEvses-a.residualSourceEvses||a.operator.localeCompare(b.operator));

const out={
  classifiedNationalOrphanSourceEvses:classifiedNationalOrphanPks.size,
  schemaVersion:1,generatedAt:new Date().toISOString(),
  sourceEvseResidualCount:operators.reduce((n,x)=>n+x.residualSourceEvses,0),
  operatorBucketCount:operators.length,
  safelyRecoverableSourceEvses:operators.reduce((n,x)=>n+x.safelyRecoverableSourceEvses,0),
  uniqueSuffixValidatedMappings:validatedMappings.length,
  operators,
  policy:'Single-pass diagnostic over every current unpublished source EVSE. Same canonical classifier and strict local unpublished target/global uniqueness checks; no proximity inference.'
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.mkdir('data/platforms/electroverse/validated-mappings',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
await fs.writeFile(VALIDATED,JSON.stringify({
  schemaVersion:1,generatedAt:out.generatedAt,
  dataset:'electroverse-france-remaining-validated-unique-suffix-mappings',
  count:validatedMappings.length,
  policy:'Only exact unique suffix bijections to currently unpublished local national PDC targets that are globally unique. No proximity inference.',
  mappings:validatedMappings
},null,2)+'\n');


const debugSourcePks=new Set(['1028573','1036491','1214346','1214350','4179421','4179445']);
const debugTargets=new Set(['FRMAPE000025001939','FRMAPE000025001863','FRMAPE000029973055','FRMAPE000030051219','FRGSPE12345958361','FRGSPE12345958371'].map(norm));
const debugOffers=[];
for(const t of oman.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
  for(const o of tile.emspOffers||[]){
    const pks=[
      ...(o?.metadata?.electroverseEvsePks||[]).map(String),
      ...(o?.metadata?.electroverseEvsePk!=null?[String(o.metadata.electroverseEvsePk)]:[])
    ];
    const targets=(o.evseIds||[]).map(norm);
    if(pks.some(x=>debugSourcePks.has(x))||targets.some(x=>debugTargets.has(x))){
      debugOffers.push({
        id:o.id,
        evseIds:o.evseIds||[],
        sourcePks:pks,
        identityMode:o?.metadata?.identityMode||null,
        offerGranularity:o?.metadata?.offerGranularity||null,
        powerKw:o?.metadata?.powerKw??null
      });
    }
  }
}
console.log('DEBUG_SIX_RESIDUALS '+JSON.stringify({
  publishedSourcePks:[...debugSourcePks].filter(x=>publishedSourcePks.has(x)),
  publishedTargets:[...debugTargets].filter(x=>publishedTargets.has(x)),
  offers:debugOffers
},null,2));

console.log(JSON.stringify({
  generatedAt:out.generatedAt,
  sourceEvseResidualCount:out.sourceEvseResidualCount,
  operatorBucketCount:out.operatorBucketCount,
  safelyRecoverableSourceEvses:out.safelyRecoverableSourceEvses,
  uniqueSuffixValidatedMappings:out.uniqueSuffixValidatedMappings,
  topRecoverable:operators.filter(x=>x.safelyRecoverableSourceEvses>0).slice(0,100).map(x=>({
    operator:x.operator,residual:x.residualSourceEvses,recoverable:x.safelyRecoverableSourceEvses,byMode:x.byMode
  })),
  topResidual:operators.slice(0,30).map(x=>({
    operator:x.operator,residual:x.residualSourceEvses,locations:x.affectedLocations,byMode:x.byMode
  }))
},null,2));

// rerun marker 2026-10-01 post-79373

// rerun after connector-power overlay 2026-10-01

// verify post-rebuild residual count 2026-10-01

// debug six post-connector-power residuals 2026-10-01

// verify residuals after split pricing merge 2026-10-01

// verify hardened NUMERIC conflict resolution 2026-10-01

// rerank after parent connector-power publication 2026-10-01

// rerank after hardened zero integration 2026-10-01

// rerank after P01 exact-reference donor publication 2026-10-01

// rerank after strict station-homogeneous price broadcast 2026-10-01
