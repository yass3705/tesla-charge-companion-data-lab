import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const loadGz=async p=>JSON.parse(zlib.gunzipSync(await fs.readFile(p)).toString('utf8'));
const evidence=JSON.parse(await fs.readFile('data/manual_verification/electra_app_evidence_2026-10-10.json','utf8'));
const locations=(await loadGz('data/platforms/electra/france/source-locations.json.gz')).locations;
const national=await loadGz('data/national/france-irve-static-v9/all.json.gz');
const byLocation=new Map(locations.map(l=>[String(l.id),l]));
const powers=new Map();
for(const row of national)for(const cfg of row?.[8]||[])for(const id of cfg?.[6]||[]){
 const key=norm(id),power=Number(cfg?.[3]);
 if(!Number.isFinite(power)||power<=0)continue;
 let current=powers.get(key)||new Set();current.add(power);powers.set(key,current);
}
function inspectTariff(t){
 const hourly=[],rates=new Set(),allComponents=[],restrictions=[];
 for(const el of t.elements||[]){
  const pcs=el.priceComponents||[],r=el.restrictions||{};
  restrictions.push(r);
  for(const pc of pcs){
   allComponents.push({type:pc.type,value:pc.price,restriction:r});
   if(pc.type==='ENERGY'&&Number.isFinite(Number(pc.price))){
    rates.add(Number(pc.price));
    hourly.push({price:Number(pc.price),start:r.startTime??null,end:r.endTime??null,days:r.dayOfWeek??[],minPower:r.minPower??null,maxPower:r.maxPower??null});
   }
  }
 }
 return {id:String(t.chargeTariffId||t.id),currentPricePerKwh:t.currentPricePerKwh??null,currency:t.currency,
  distinctEnergyRates:[...rates].sort((a,b)=>a-b),energyWindows:hourly,
  components:allComponents,hasExplicitPowerScope:restrictions.length>0&&restrictions.every(r=>r.minPower!=null||r.maxPower!=null)};
}
const out={schemaVersion:1,generatedAt:new Date().toISOString(),sourceManifest:'data/platforms/electra/france/manifest.json',
 sourceEvidence:'data/manual_verification/electra_app_evidence_2026-10-10.json',sourceGeneratedAt:JSON.parse(await fs.readFile('data/platforms/electra/france/manifest.json','utf8')).generatedAt,
 stationCount:evidence.stations.length,stations:[],autoPublishableTariffAssignments:0};
for(const verify of evidence.stations){
 const l=byLocation.get(verify.locationId);
 if(!l){out.stations.push({locationId:verify.locationId,error:'location_id_not_in_source'});continue;}
 const pdc=(l.evses||[]).map(e=>{
  const actualPowers=[...(powers.get(norm(e.evseId))||[])].sort((a,b)=>a-b);
  return {evseId:e.evseId,sourceEvseUuid:e.id,connectorIds:(e.connectors||[]).map(c=>c.id),nationalPowersKw:actualPowers,
   technicalPowerStatus:actualPowers.length===1?'one_national_power':actualPowers.length===0?'missing_power':'conflicting_national_powers'};
 });
 const tariff=(l.chargeTariffs||[]).map(inspectTariff);
 const checks=(verify.observations||[]).map(o=>{
  let matches=o.energyEurPerKwh==null?[]:tariff.filter(t=>t.distinctEnergyRates.some(r=>Math.abs(r-o.energyEurPerKwh)<0.0001)).map(t=>t.id);
  const exactNominalPdc=pdc.filter(p=>p.nationalPowersKw.length===1&&Math.abs(p.nationalPowersKw[0]-o.maxPowerKw)<0.5).map(p=>p.evseId);
  const status=o.energyEurPerKwh==null?'missing_app_rate':
   matches.length!==1?'ambiguous_tariff_identification':
   exactNominalPdc.length===0?'technical_power_mismatch':
   'per_power_candidate_requires_live_tariff_refresh';
  return {powerKw:o.maxPowerKw,appRate:o.energyEurPerKwh,appLabel:o.label,possibleTariffIds:matches,matchedEvseIds:exactNominalPdc,
   status,pricing:o.pricing??'price_of_day'};
 });
 const fees=(verify.fees||[]).map(f=>({type:f.kind,value:f.eurPerMinute??f.eurPerHour,
  unit:f.eurPerMinute!=null?'EUR/min':'EUR/hour',condition:f.condition??f.trigger}));
 // A price-per-kWh match is insufficient when parking/time components differ.
 // Location-level app fees may not apply to every power or every tariff.
 const stationParkingFee=fees.find(v=>v.type==='parking'&&v.unit==='EUR/hour')?.value??null;
 const feeComparisons=checks.map(c=>{
  const options=tariff.filter(t=>c.possibleTariffIds.includes(t.id)).map(t=>{
   const relevant=t.components.filter(p=>p.type==='TIME'||p.type==='PARKING_TIME')
     .map(p=>({type:p.type,amountPerHour:Number(p.value),restrictions:p.restriction||{}}));
   const kinds=[...new Set(relevant.map(x=>x.type))];
   const matchingAppFee=stationParkingFee==null?null:relevant.some(x=>Math.abs(x.amountPerHour-stationParkingFee)<0.001);
   const rateConflict=stationParkingFee==null?false:relevant.length>0&&!matchingAppFee;
   const potentialDoubleCharge=kinds.includes('TIME')&&kinds.includes('PARKING_TIME')&&
     relevant.some(x=>relevant.some(y=>x!==y&&x.type!==y.type&&x.amountPerHour===y.amountPerHour&&x.amountPerHour>0));
   return {tariffId:t.id,sourceHourlyComponents:relevant,stationParkingRateMatchesAtLeastOne:matchingAppFee,
     conflictsWithStationDisplayedRate:rateConflict,potentialDoubleCharge};
  });
  return {powerKw:c.powerKw,appRate:c.appRate,stationParkingFeeEurPerHour:stationParkingFee,options,
    verdict:options.some(x=>x.conflictsWithStationDisplayedRate)?'station_fee_conflict_needs_connector_scope':
      options.some(x=>x.potentialDoubleCharge)?'parallel_time_and_parking_risk':
      options.length&&stationParkingFee!=null&&!options.some(x=>x.sourceHourlyComponents.length)?'app_station_fee_not_in_selected_tariff':
      'no_additional_rate_conflict_observed'};
 });
 const mismatches=checks.filter(c=>['ambiguous_tariff_identification','technical_power_mismatch'].includes(c.status));
 const missing=pdc.filter(e=>e.technicalPowerStatus!=='one_national_power');
 const unresolved={technicalMismatches:mismatches.length,unknownTechnicalEVSEs:missing.length,sourceTariffs:tariff.length,
   pricedAppPowerGroups:checks.filter(c=>c.appRate!=null).length,
   possibleSourceMappingUnique:checks.filter(c=>c.possibleTariffIds.length===1).length};
 out.stations.push({locationId:verify.locationId,name:verify.name,cpo:verify.cpo,validation:verify.confidence,
  appObserved:verify.observations||[],appFees:fees,sourceTariffs:tariff,nationalEvsePowers:pdc,
  perPowerChecks:checks,feeComparisons,unresolved,
  finalDisposition:verify.status==='not_found_in_app_to_recheck'?'app_absent_unverified_keep_unpublished':
   'evidence_supports_per_power_rules_not_exact_all_evse_and_temporal_applicability',
  crossChannelWarning:'Electra eMSP only. Do not override direct CPO tariffs.'});
}
out.summary={checkedStations:out.stations.length,appPresent:out.stations.filter(x=>x.appObserved?.length).length,
 appAbsent:out.stations.filter(x=>x.finalDisposition==='app_absent_unverified_keep_unpublished').length,
 matchedRateAndPowerCandidates:out.stations.reduce((n,x)=>n+(x.perPowerChecks||[]).filter(z=>z.status==='per_power_candidate_requires_live_tariff_refresh').length,0),
 sourceTariffAmbiguous:out.stations.reduce((n,x)=>n+(x.perPowerChecks||[]).filter(z=>z.status==='ambiguous_tariff_identification').length,0),
 powerMismatches:out.stations.reduce((n,x)=>n+(x.perPowerChecks||[]).filter(z=>z.status==='technical_power_mismatch').length,0),
 feeConflictGroups:out.stations.reduce((n,x)=>n+(x.feeComparisons||[]).filter(z=>z.verdict==='station_fee_conflict_needs_connector_scope').length,0),
 potentialDoubleChargeGroups:out.stations.reduce((n,x)=>n+(x.feeComparisons||[]).filter(z=>z.verdict==='parallel_time_and_parking_risk').length,0)};
const path='reports/france/electra/user-screen-reconciliation-2026-10-10.json';
await fs.mkdir('reports/france/electra',{recursive:true});
await fs.writeFile(path,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({report:path,summary:out.summary,stations:out.stations.map(s=>({name:s.name,perPowerChecks:s.perPowerChecks,unresolved:s.unresolved}))}).slice(0,18000));
