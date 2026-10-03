import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const CANONICAL='data/national/france_public_charging_canonical.json';
const ACCESS='reports/france/irve-public-access-validation-ledger.json';
const OUT='reports/electroverse/fingerprint-candidates.json';
const PLAN='data/platforms/electroverse/validated-mappings/final-residual-recovery-plan.json';

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const num=x=>{const n=Number(String(x??'').replace(',','.'));return Number.isFinite(n)&&n>0?n:null;};
const power=x=>{const n=num(x);return n==null?null:Math.round(n);};
const modeOfConnector=c=>/CCS|CHADEMO|COMBO/.test(JSON.stringify(c??{}).toUpperCase())?'DC':'AC';
const evseMode=e=>(e?.connectors||[]).some(c=>modeOfConnector(c)==='DC')?'DC':'AC';
const evsePower=e=>{
  const cs=e?.connectors||[], non=cs.filter(c=>!(/SCHUKO|DOMESTIC/.test(JSON.stringify(c).toUpperCase())));
  const xs=(non.length?non:cs).map(c=>num(c?.kilowatts)).filter(Boolean);
  return xs.length?Math.max(...xs):null;
};
const tariffKey=e=>JSON.stringify((e?.connectors||[]).map(c=>({free:c?.isChargingFree??null,prices:c?.priceComponents??null,complex:c?.complexPricingDetail??null})));
const hasSingleTariff=es=>new Set(es.map(tariffKey)).size===1;
const DEALER_RE=/\b(concession|concessionnaire|garage|automobiles?|autohaus|bmw|hyundai|peugeot|renault|citro[eë]n|audi|volvo|toyota|nissan|opel|mercedes|ford|kia|porsche|jaguar|land rover|lexus|suzuki|honda|mitsubishi|mazda|alfa romeo|fiat|seat|skoda|groupe gueudet|by my car|car avenue)\b/i;

function walk(node,parentStation,index){
  if(Array.isArray(node)){for(const x of node)walk(x,parentStation,index);return;}
  if(!node||typeof node!=='object')return;
  const station=String(node.id_station_itinerance??node.id_station_local??node.irveStationId??node.stationId??node.station_id??parentStation??'');
  const pdc=node.id_pdc_itinerance??node.id_pdc_local??node.pdcId??node.pdc_id??node.idPdc;
  const kw=power(node.puissance_nominale??node.powerKw??node.power_kw??node.power??node.kilowatts??node.nominalPowerKw);
  if(pdc!=null&&kw!=null){
    const s=JSON.stringify(node).toUpperCase();
    const mode=/CCS|CHADEMO|COMBO/.test(s)?'DC':'AC';
    const prev=index.get(norm(pdc))||{pdcId:String(pdc),stationId:station,powers:[],modes:new Set(),text:''};
    prev.powers.push(kw);prev.modes.add(mode);prev.text+=' '+s;
    index.set(norm(pdc),prev);
  }
  for(const v of Object.values(node))if(v&&typeof v==='object')walk(v,station,index);
}
const canonical=JSON.parse(await fs.readFile(CANONICAL,'utf8'));
const pdcIndex=new Map();walk(canonical,null,pdcIndex);
const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const owners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;const s=owners.get(k)||new Set();s.add(String(m.irveStationId??''));owners.set(k,s);
}
const excluded=new Set();
try{
  const ledger=JSON.parse(await fs.readFile(ACCESS,'utf8'));
  for(const d of ledger.decisions||[])if(d.decision==='exclude_non_public')for(const id of d.stationIds||[])excluded.add(String(id));
}catch{}
const manifest=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedSources=new Set(),publishedTargets=new Set();
for(const t of manifest.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
  for(const o of tile.emspOffers||[]){
    for(const p of o?.metadata?.electroverseEvsePks||[])publishedSources.add(String(p));
    for(const p of o?.metadata?.electroverseAliasEvsePks||[])publishedSources.add(String(p));
    if(o?.metadata?.electroverseEvsePk!=null)publishedSources.add(String(o.metadata.electroverseEvsePk));
    for(const id of o.evseIds||[])publishedTargets.add(norm(id));
  }
}
function matchGroups(sourceGroups,targetGroups){
  const remaining=[...targetGroups],out=[];
  for(const sg of [...sourceGroups].sort((a,b)=>a.power-b.power)){
    const i=remaining.findIndex(t=>t.mode===sg.mode&&Math.abs(t.power-sg.power)<=10&&t.count===sg.count);
    if(i<0)return null;
    out.push({source:sg,target:remaining[i]});remaining.splice(i,1);
  }
  return remaining.length?null:out;
}
const candidates=[],excludedRows=[],rejected=[];
const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
for(const sh of cman.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const loc=String(row.electroverseLocationPk??''),m=byPk.get(loc);if(!m)continue;
    const station=String(m.irveStationId??row.irveStationId??'');
    const source=(row.tariff?.evses||[]).filter(e=>e?.pk!=null&&!publishedSources.has(String(e.pk)));
    if(!source.length)continue;
    const targetIds=[...new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))].filter(p=>!publishedTargets.has(p));
    const targetRows=targetIds.map(p=>pdcIndex.get(p)).filter(Boolean);
    const stationText=targetRows.map(x=>x.text).join(' ');
    if(excluded.has(station)){excludedRows.push({loc,station,reason:'exclude_non_public',sourceCount:source.length});continue;}
    if(DEALER_RE.test(stationText)||DEALER_RE.test(station)){excludedRows.push({loc,station,reason:'exclude_dealership_heuristic',sourceCount:source.length});continue;}
    if(source.length!==targetRows.length){rejected.push({loc,station,reason:'cardinality_mismatch',sourceCount:source.length,targetCount:targetRows.length});continue;}
    if(targetRows.some(x=>(owners.get(norm(x.pdcId))?.size||0)!==1)){rejected.push({loc,station,reason:'target_not_globally_unique'});continue;}
    const sgMap=new Map(),tgMap=new Map();
    for(const e of source){
      const p=evsePower(e);if(p==null){rejected.push({loc,station,reason:'source_power_missing'});continue;}
      const k=evseMode(e)+'|'+p,a=sgMap.get(k)||{mode:evseMode(e),power:p,count:0,evses:[]};a.count++;a.evses.push(e);sgMap.set(k,a);
    }
    for(const t of targetRows){
      const p=t.powers.length?Math.max(...t.powers):null;if(p==null){rejected.push({loc,station,reason:'target_power_missing'});continue;}
      const mode=t.modes.has('DC')?'DC':'AC',k=mode+'|'+p,a=tgMap.get(k)||{mode,power:p,count:0,pdcs:[]};a.count++;a.pdcs.push(t);tgMap.set(k,a);
    }
    const groups=matchGroups([...sgMap.values()],[...tgMap.values()]);
    if(!groups||groups.some(g=>!hasSingleTariff(g.source.evses))){rejected.push({loc,station,reason:'mode_power_or_tariff_coherence_failed'});continue;}
    for(const g of groups)candidates.push({
      mode:'homogeneous_target_subset',operator:'ELECTROVERSE_IRVE_FINGERPRINT',
      electroverseLocationPk:loc,irveStationId:station,
      sourceEvsePks:g.source.evses.map(e=>e.pk),physicalReferences:g.source.evses.map(e=>String(e.physicalReference??'')),
      targetPdcs:g.target.pdcs.map(p=>p.pdcId),profile:{kilowatts:g.source.power,mode:g.source.mode},
      targetPowerKws:g.target.pdcs.map(p=>p.powers[0]),
      evidence:{rule:'same station cardinality, same AC/DC mode, power difference <=10 kW, one tariff per source power group',sourcePowerKw:g.source.power,targetPowerKw:g.target.power,tariffKey:tariffKey(g.source.evses[0])}
    });
  }
}
const unique=new Map();
for(const g of candidates)unique.set(String(g.electroverseLocationPk)+'|'+g.sourceEvsePks.join(','),g);
const finalCandidates=[...unique.values()];
let plan={schemaVersion:1,individualMappings:[],groupMappings:[]};
try{plan=JSON.parse(await fs.readFile(PLAN,'utf8'));}catch{}
plan.groupMappings=(plan.groupMappings||[]).filter(g=>g.operator!=='ELECTROVERSE_IRVE_FINGERPRINT');
plan.groupMappings.push(...finalCandidates);
plan.generatedAt=new Date().toISOString();
plan.policy='IRVE fingerprint groups: exact station cardinality, AC/DC mode equality, power tolerance <=10 kW, unique tariff per source power group; dealerships and explicitly non-public stations excluded.';
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.mkdir('data/platforms/electroverse/validated-mappings',{recursive:true});
await fs.writeFile(OUT,JSON.stringify({schemaVersion:1,generatedAt:plan.generatedAt,policy:plan.policy,candidateGroups:finalCandidates.length,candidateSourceEvses:finalCandidates.reduce((n,g)=>n+g.sourceEvsePks.length,0),excluded:excludedRows,rejectedCount:rejected.length,rejectedSamples:rejected.slice(0,500),candidates:finalCandidates},null,2)+'\n');
await fs.writeFile(PLAN,JSON.stringify(plan,null,2)+'\n');
console.log(JSON.stringify({candidateGroups:finalCandidates.length,candidateSourceEvses:finalCandidates.reduce((n,g)=>n+g.sourceEvsePks.length,0),excluded:excludedRows.length,rejected:rejected.length},null,2));
