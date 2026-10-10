import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const gz=async f=>JSON.parse(zlib.gunzipSync(await fs.readFile(f)).toString('utf8'));
const norm=x=>String(x||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const [verification,source,national,residual]=await Promise.all([
 fs.readFile('data/manual_verification/electra_powerdot_saint_arnoult_2026-10-10.json','utf8').then(JSON.parse),
 gz('data/platforms/electra/france/source-locations.json.gz'),
 gz('data/national/france-irve-static-v9/all.json.gz'),
 gz('reports/france/irve/electra-pricing-residual-cases-2026-10-08.json.gz')
]);
const wanted=verification.locationId;
const station=source.locations.find(l=>String(l.id)===wanted);
if(!station)throw Error('Evidence location is not in Electra source snapshot');
if(station.cpo?.name!=='Powerdot')throw Error('Evidence location is not Powerdot');
const power=new Map(),duplicate=new Map();
for(const row of national)for(const group of row?.[8]||[]){
 const kw=Number(group?.[3]);for(const id of group?.[6]||[]){
  const k=norm(id);
  if(!Number.isFinite(kw)||kw<=0)continue;
  const v=power.get(k)||new Set();v.add(kw);power.set(k,v);
  duplicate.set(k,(duplicate.get(k)||0)+1);
 }
}
function tariffsFor(loc){
 return (loc.chargeTariffs||[]).map(t=>({
  id:t.chargeTariffId||t.id,
  kinds:[...new Set((t.elements||[]).flatMap(e=>(e.priceComponents||[]).map(c=>c.type)))].sort(),
  rate:[...new Set((t.elements||[]).flatMap(e=>(e.priceComponents||[]).filter(c=>c.type==='ENERGY').map(c=>Number(c.price))))],
  restrictions:(t.elements||[]).map(e=>e.restrictions||{}),
  components:(t.elements||[]).flatMap(e=>(e.priceComponents||[]).map(c=>({type:c.type,price:Number(c.price)})))
 }));
}
const tariffs=tariffsFor(station);
const expectedIds=new Set(verification.sourcePriceTariffCandidateIds);
const evses=(station.evses||[]).map(e=>({evseId:e.evseId,powersKw:[...(power.get(norm(e.evseId))||[])].sort((a,b)=>a-b),
 duplicatedInNational:duplicate.get(norm(e.evseId))>1,physicalReference:e.physicalReference||null}));
const priceRows=verification.observations.map(o=>({
 powerKw:o.powerKw,eurPerKwh:o.eurPerKwh,
 sourceTariffs:tariffs.filter(t=>t.rate.length===1&&Math.abs(t.rate[0]-o.eurPerKwh)<0.000001)
   .map(t=>({tariffId:t.id,onlyEnergy:t.kinds.length===1&&t.kinds[0]==='ENERGY',restrictions:t.restrictions})),
 knownEvseIds:evses.filter(e=>e.powersKw.length===1&&Math.abs(e.powersKw[0]-o.powerKw)<0.001).map(e=>e.evseId)
}));
const noForeignTariffs=tariffs.every(t=>expectedIds.has(t.id));
const allKnown=evses.length>0&&evses.every(e=>e.powersKw.length===1);
const eachPowerRepresented=priceRows.every(o=>o.knownEvseIds.length>0&&o.sourceTariffs.length===1&&o.sourceTariffs[0].onlyEnergy);
const allPowersCovered=evses.every(e=>priceRows.some(o=>Math.abs(o.powerKw-e.powersKw[0])<0.001));
const noLimitRules=priceRows.every(p=>p.sourceTariffs.every(t=>t.restrictions.every(r=>
  !Object.values(r).some(v=>v!=null&&v!==''&&(!Array.isArray(v)||v.length)))));
const exactPromotionCandidate=noForeignTariffs&&allKnown&&eachPowerRepresented&&allPowersCovered&&noLimitRules;
const sample={station:station.name,locationId:wanted,cpo:station.cpo?.name,city:station.city,
 sourceEvseCount:evses.length,tariffCount:tariffs.length,evses,tariffs,priceRows,
 checks:{noForeignTariffs,allKnown,eachPowerRepresented,allPowersCovered,noLimitRules},
 candidate:exactPromotionCandidate,
 note:"Only two categorical price bands with full IRVE EVSE coverage and no other tariff/fee restrictions may be verified. App screenshot title not shown; identity inferred from conversation and map."};
const cohortIds=new Set(['9d3380b6-bfef-4f52-a50e-11f72cff552c','deb8f441-4306-4735-9990-3165dbeefffc']);
const report={schemaVersion:1,generatedAt:new Date().toISOString(),evidenceLocation:sample,guardrails:{
 requiresKnownExactEvse:true,requiresKnownPower:true,requiresOnlyTwoPowerBands:true,restrictBatchToPowersKw:[22,50],
 requiresTariffIds: [...cohortIds],requiresOnlyEnergy:true,
 explicitSameEvseSamePowerConflictsMustFail:true,unverifiedExtraFastPowersMustRemainPending:true
},batch:{candidateStationCount:0,validStationCount:0,invalidReasons:{},validStations:[],stationsWithOtherTariffs:0,nonPublicOrDealershipCandidates:[]}};
const reason=(s)=>(report.batch.invalidReasons[s]=(report.batch.invalidReasons[s]||0)+1);
for(const c of residual.cases||[]){
 if(c.cpo!=='Powerdot')continue;
 if(c.triage?.class!=='multiple_known_powers_without_tariff_mapping')continue;
 const loc=source.locations.find(x=>x.id===c.locationId);
 if(!loc)continue;
 const ts=tariffsFor(loc);
 const cp=(loc.evses||[]).map(e=>({id:e.evseId,powersKw:[...(power.get(norm(e.evseId))||[])]}));
 const valid22and50=cp.length>0&&cp.every(e=>e.powersKw.length===1&&[22,50].includes(e.powersKw[0]))&&
 cp.some(e=>e.powersKw[0]===22)&&cp.some(e=>e.powersKw[0]===50);
 if(!valid22and50)continue;
 report.batch.candidateStationCount++;
 if(/\bgarage\b|\bconcession\b|\bcentre auto\b|\bautomobile\b/i.test(String(loc.name||''))){
  reason('nonpublic_or_dealership_to_reverify');
  report.batch.nonPublicOrDealershipCandidates.push({locationId:loc.id,name:loc.name});
  continue;
 }
 if(ts.length!==2||ts.some(t=>!cohortIds.has(t.id))){reason('other_tariff_ids_or_grid_count');report.batch.stationsWithOtherTariffs++;continue;}
 if(ts.some(t=>t.kinds.length!==1||t.kinds[0]!=='ENERGY'||t.rate.length!==1)){reason('mixed_components_or_rates');continue;}
 if(ts.some(t=>t.restrictions.some(r=>Object.values(r).some(v=>v!=null&&v!==''&&(!Array.isArray(v)||v.length))))){reason('restrictions_present');continue;}
 if(ts.some(t=>Math.abs(t.rate[0]-(t.id==='9d3380b6-bfef-4f52-a50e-11f72cff552c'?0.49:0.62))>0.000001)){reason('tariff_price_mismatch');continue;}
 report.batch.validStationCount++;report.batch.validStations.push({locationId:loc.id,name:loc.name,city:loc.city,
  evses:cp.map(e=>({id:e.id,powerKw:e.powersKw[0],rate:e.powersKw[0]===22?0.49:0.62})),
  status:'candidate_not_yet_published'});
}
await fs.mkdir('reports/france/electra',{recursive:true});
const outfile='reports/france/electra/powerdot-saint-arnoult-proof-and-22-50-candidates-latest.json';
await fs.writeFile(outfile,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({report:outfile,saintArnoult:sample,
  batch:{candidateStationCount:report.batch.candidateStationCount,validStationCount:report.batch.validStationCount,
   invalidReasons:report.batch.invalidReasons,sample:report.batch.validStations.slice(0,4)}},null,2).slice(0,11500));
