import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const CANONICAL='data/national/france_public_charging_canonical.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const PLAN='data/platforms/electroverse/validated-mappings/final-residual-recovery-plan.json';
const REPORT='reports/electroverse/numeric-tariff-coherence-analysis.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const text=x=>String(x??'').trim();

function first(o,names){
  for(const n of names) if(o&&o[n]!=null&&o[n]!=='') return o[n];
  return null;
}
function powerKey(v){
  const n=Number(String(v??'').replace(',','.'));
  return Number.isFinite(n)&&n>0?Math.round(n):null;
}
function tariffValues(connector){
  const out=new Set();
  const add=v=>{
    const s=String(v??'');
    for(const m of s.matchAll(/€\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:\/\s*kwh|kwh)/ig))
      out.add(Number(m[1].replace(',','.')).toFixed(6));
  };
  for(const p of connector?.priceComponents||[]) add(p?.formattedValue??p?.value??p?.amount);
  for(const r of connector?.complexPricingDetail?.restrictions||[])
    for(const p of r?.priceComponents||[]) add(p?.formattedValue??p?.value??p?.amount);
  return [...out].sort();
}
function walk(node,parentStation,index){
  if(Array.isArray(node)){for(const x of node)walk(x,parentStation,index);return;}
  if(!node||typeof node!=='object')return;
  const station=first(node,['id_station_itinerance','id_station_local','irveStationId','stationId','station_id'])||parentStation;
  const pdc=first(node,['id_pdc_itinerance','id_pdc_local','pdcId','pdc_id','idPdc']);
  const kw=first(node,['puissance_nominale','powerKw','power_kw','power','kilowatts','nominalPowerKw']);
  if(pdc!=null&&kw!=null){
    const key=norm(pdc), pk=powerKey(kw);
    if(key&&pk!=null) index.set(key,{pdcId:String(pdc),powerKw:Number(String(kw).replace(',','.')),powerKey:pk,stationId:station?String(station):null});
  }
  for(const v of Object.values(node)) if(v&&typeof v==='object') walk(v,station,index);
}

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const globalOwners=new Map();
for(const m of mapping.mappings||[]) for(const p of m.irvePdcIds||[]){
  const k=norm(p), s=globalOwners.get(k)||new Set(); if(k){s.add(String(m.irveStationId??''));globalOwners.set(k,s);}
}
const overlayManifest=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedSources=new Set(),publishedTargets=new Set();
for(const t of overlayManifest.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
  for(const o of tile.emspOffers||[]){
    for(const pk of o?.metadata?.electroverseEvsePks||[]) if(pk!=null)publishedSources.add(String(pk));
    if(o?.metadata?.electroverseEvsePk!=null)publishedSources.add(String(o.metadata.electroverseEvsePk));
    for(const id of o.evseIds||[]) publishedTargets.add(norm(id));
  }
}
const canonical=JSON.parse(await fs.readFile(CANONICAL,'utf8'));
const pdcIndex=new Map();
walk(canonical,null,pdcIndex);

const candidates=[], rejected=[];
const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
for(const sh of cman.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const source=(row?.tariff?.evses||[]).filter(e=>e?.pk!=null&&!publishedSources.has(String(e.pk))&&/^\d{1,3}$/.test(text(e?.physicalReference)));
    if(!source.length)continue;
    const m=byPk.get(String(row.electroverseLocationPk));
    if(!m)continue;
    const targetIds=[...new Set((m.irvePdcIds||[]).map(norm).filter(Boolean))].filter(p=>!publishedTargets.has(p));
    const sourceSimple=source.every(e=>(e.connectors||[]).length===1);
    const targetRows=targetIds.map(p=>pdcIndex.get(p)).filter(Boolean);
    const reason=[];
    if(!sourceSimple)reason.push('multi_connector_source_evse');
    if(targetRows.length!==targetIds.length)reason.push('pdc_power_missing_in_canonical');
    if(targetRows.length!==source.length)reason.push('cardinality_mismatch');
    const sourceByPower=new Map(),targetByPower=new Map();
    for(const e of source){
      const c=e.connectors?.[0], k=powerKey(c?.kilowatts);
      if(k==null)reason.push('source_power_missing');
      const a=sourceByPower.get(k)||[];a.push(e);sourceByPower.set(k,a);
      const tariffs=tariffValues(c); if(tariffs.length!==1)reason.push('non_unique_tariff_per_power');
      e.__coherence={powerKey:k,powerKw:Number(c?.kilowatts),tariff:tariffs[0]??null};
    }
    for(const p of targetRows){
      const a=targetByPower.get(p.powerKey)||[];a.push(p);targetByPower.set(p.powerKey,a);
    }
    const powers=new Set([...sourceByPower.keys(),...targetByPower.keys()]);
    for(const k of powers){
      if(k==null||sourceByPower.get(k)?.length!==targetByPower.get(k)?.length)reason.push('power_cardinality_mismatch');
    }
    if(reason.length){rejected.push({electroverseLocationPk:String(row.electroverseLocationPk),irveStationId:m.irveStationId,reason:[...new Set(reason)],sourceCount:source.length,targetCount:targetRows.length});continue;}
    const groups=[];
    for(const [k,es] of sourceByPower){
      const ps=targetByPower.get(k)||[];
      if(ps.some(p=>(globalOwners.get(norm(p.pdcId))?.size||0)!==1)) {reason.push('target_not_globally_unique');break;}
      groups.push({
        mode:'homogeneous_target_subset',
        operator:'NUMERIC_TARIFF_COHERENCE',
        electroverseLocationPk:String(row.electroverseLocationPk),
        irveStationId:String(m.irveStationId),
        sourceEvsePks:es.map(e=>e.pk),
        physicalReferences:es.map(e=>text(e.physicalReference)),
        targetPdcs:ps.map(p=>p.pdcId),
        uniformConnectorCount:true,
        profile:{kilowatts:es[0].__coherence.powerKw},
        evidence:{
          source:'current Electroverse tariff cache + current PAN national IRVE canonical',
          observed:new Date().toISOString().slice(0,10),
          rule:'Exact source/PDC cardinality and power multiset per station/power group; one Electroverse consumption tariff per power; no source-to-target permutation asserted.',
          tariffEurPerKwh:Number(es[0].__coherence.tariff)
        }
      });
    }
    if(reason.length){rejected.push({electroverseLocationPk:String(row.electroverseLocationPk),irveStationId:m.irveStationId,reason:[...new Set(reason)]});continue;}
    candidates.push(...groups);
  }
}
const unique=new Map();
for(const g of candidates)unique.set(g.electroverseLocationPk+'|'+g.profile.kilowatts+'|'+g.sourceEvsePks.join(','),g);
const groups=[...unique.values()];
let plan={schemaVersion:1,generatedAt:new Date().toISOString(),dataset:'electroverse-france-final-residual-recovery-plan',policy:'Only residual mappings proven against the current overlay. Individual mappings require exact unique local/global target identity; group mappings require exact source/target cardinality, globally unique targets, and homogeneous raw pricing. No proximity inference.'};
try{plan=JSON.parse(await fs.readFile(PLAN,'utf8'));}catch{}
plan.groupMappings=(plan.groupMappings||[]).filter(g=>g.operator!=='NUMERIC_TARIFF_COHERENCE');
plan.groupMappings.push(...groups);
plan.generatedAt=new Date().toISOString();
plan.policy=plan.policy||'Group mappings require exact cardinality and homogeneous pricing; no permutation inference.';
plan.stats={...(plan.stats||{}),numericTariffCoherenceGroups:groups.length,numericTariffCoherenceSourceEvses:groups.reduce((n,g)=>n+g.sourceEvsePks.length,0)};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.mkdir('data/platforms/electroverse/validated-mappings',{recursive:true});
await fs.writeFile(REPORT,JSON.stringify({schemaVersion:1,generatedAt:new Date().toISOString(),policy:'Total Rungis generalized: exact station cardinality, exact power multiset per group, unique Electroverse tariff per power, no individual permutation.',candidateGroupCount:groups.length,candidateSourceEvses:groups.reduce((n,g)=>n+g.sourceEvsePks.length,0),candidates:groups,rejectedCount:rejected.length,rejectedSamples:rejected.slice(0,100)},null,2)+'\n');
await fs.writeFile(PLAN,JSON.stringify(plan,null,2)+'\n');
console.log(JSON.stringify({candidateGroupCount:groups.length,candidateSourceEvses:groups.reduce((n,g)=>n+g.sourceEvsePks.length,0),rejectedCount:rejected.length,top:groups.slice(0,20).map(g=>({location:g.electroverseLocationPk,power:g.profile.kilowatts,count:g.sourceEvsePks.length,tariff:g.evidence.tariffEurPerKwh}))},null,2));
