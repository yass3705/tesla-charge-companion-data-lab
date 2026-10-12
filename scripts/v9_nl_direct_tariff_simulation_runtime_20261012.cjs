#!/usr/bin/env node
/* Read-only candidate-snapshot simulations with the ACTUAL pinned V9 runtime.
 * A finished numerical calculation != verified public price or contract.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');

const fixturePath=process.argv[2],prodRoot=process.argv[3],reportPath=process.argv[4];
if(!fixturePath||!prodRoot||!reportPath)throw new Error('Usage: node simulate.js fixtures.json production-checkout output.json');
const source=JSON.parse(fs.readFileSync(fixturePath,'utf8'));
assert.equal(source.schemaVersion,1);
assert.equal(source.publishedToTcc,false);
const adapterPath=path.resolve(prodRoot,'runtime-overrides/assets/v9/adapters/netherlands-dotnl.js');
const enginePath=path.resolve(prodRoot,'runtime-overrides/assets/v9/pricing-engine.js');
const adapter=require(adapterPath),engine=require(enginePath);
const profiles=[
 {id:'weekday_day',session:{startAt:'2026-10-12T09:30:00+02:00',energyKwh:12,durationMinutes:45,chargingMinutes:45,postChargeMinutes:0}},
 {id:'weekday_evening_idle',session:{startAt:'2026-10-12T18:30:00+02:00',energyKwh:23,durationMinutes:75,chargingMinutes:60,postChargeMinutes:15}},
 {id:'weekday_midnight',session:{startAt:'2026-10-12T23:30:00+02:00',energyKwh:15,durationMinutes:150,chargingMinutes:80,postChargeMinutes:70}},
 {id:'sunday_idle',session:{startAt:'2026-10-11T10:00:00+02:00',energyKwh:9,durationMinutes:55,chargingMinutes:45,postChargeMinutes:10}},
 {id:'long_session',session:{startAt:'2026-10-12T11:00:00+02:00',energyKwh:40,durationMinutes:240,chargingMinutes:180,postChargeMinutes:60}},
 {id:'fall_dst_crossing',session:{startAt:'2026-10-25T00:30:00+02:00',energyKwh:10,durationMinutes:180,chargingMinutes:150,postChargeMinutes:30}}
];
const countOf=()=>Object.fromEntries(profiles.map(p=>[p.id,{completeWeight:0,incompleteWeight:0,completeGroups:0,incompleteGroups:0}]));
const profileTotals=countOf(),family={};
const reasonWeights={},reasonExamples={},cpo={};
const segmentationBlockerWeights={},segmentationBlockerSamples=[];
let totalFixtures=0,compiledConnectors=0,independentOracleCases=0,oracleMismatchWeight=0,unverifiedZeroPriceWeight=0;
let nonEurSourceCurrencyWeight=0,implausibleSourcePowerWeight=0;
const nonEurCurrencyByCode={},nonEurCurrencyExamples=[];
const blockedSamplesMax=12;

function markReason(kind,profile,g,result){
 const k=profile.id+'|'+kind;
 reasonWeights[k]=(reasonWeights[k]||0)+g.count;
 if(!reasonExamples[k])reasonExamples[k]=[];
 if(reasonExamples[k].length<blockedSamplesMax)reasonExamples[k].push({
  partyId:g.cpo,stationId:g.sampleStationId,evseId:g.sampleEvseId,tariffKey:g.tariffKey,
  standard:g.standard,powerKw:g.powerKw,weight:g.count,reason:result?.reason||null
 });
}
function familyFor(rules){
 const fields=[
  ['ENERGY',5],['TIME',6],['FLAT',7],['PARKING_TIME',8]
 ];
 const found=fields.filter(([k,i])=>rules.some(row=>Number(row[i])>0)).map(x=>x[0]);
 if(rules.some(r=>Array.isArray(r[12])&&r[12].length))found.push('DURATION_BANDS');
 if(rules.some(r=>r[13]&&Object.values(r[13]).some(v=>v!=null&&v>1)))found.push('STEP_ROUNDING');
 if(rules.some(r=>r[1]!=='00:00'||r[2]!=='24:00'))found.push('TIME_WINDOW');
 return found.length?found:['ZERO_OR_FREE'];
}
function independentEnergyOnly(offer){
 const rules=offer.pricing.rules;
 if(!rules.length)return null;
 const n=rules[0].pricePerKwh;
 if(!Number.isFinite(n)||n<0)return null;
 for(const r of rules){
  if(r.pricePerKwh!==n)return null;
  if((r.chargePerMinute||0)!==0||(r.idlePerMinute||0)!==0||(r.connectionFee||0)!==0)return null;
  if((r.afterMinutesRate||0)!==0||(r.energyStepWh||0)>1||(r.chargingTimeStepSeconds||0)>1||(r.parkingTimeStepSeconds||0)>1)return null;
  if(r.ocpiDurationBands?.length)return null;
 }
 return n;
}
for(const [i,g] of source.groups.entries()){
 if(!Number.isSafeInteger(g.count)||g.count<1)throw new Error('Invalid group multiplicity');
 const config=['cfg-'+i,'DOT-NL '+g.connectorKind+' '+g.powerKw+'kW',g.connectorKind,g.powerKw,1,g.rules];
 const site=adapter.normalizeRow([
  String(g.sampleStationId),'NL tariff fixture','',52,5,g.cpo,1,null,[config],source.sourceGeneratedAt,'IN_SERVICE'
 ]);
 assert.ok(site,'Adapter rejected compiled source tariff');
 if(site.offers.length!==1)throw new Error('Adapter suppressed/multiplied an accepted direct tariff: '+g.tariffKey);
 const offer=site.offers[0];
 assert.equal(offer.kind,'direct');
 const sourceCurrency=String(offer.currency||'UNSPECIFIED').toUpperCase();
 const currencyMismatch=sourceCurrency!=='EUR';
 if(currencyMismatch){
  nonEurSourceCurrencyWeight+=g.count;
  nonEurCurrencyByCode[sourceCurrency]=(nonEurCurrencyByCode[sourceCurrency]||0)+g.count;
  if(nonEurCurrencyExamples.length<20)nonEurCurrencyExamples.push({
    partyId:g.cpo,stationId:g.sampleStationId,evseId:g.sampleEvseId,
    tariffKey:g.tariffKey,standard:g.standard,powerKw:g.powerKw,
    currency:sourceCurrency,connectors:g.count
  });
 }
 if(g.sourcePowerPlausible===false)implausibleSourcePowerWeight+=g.count;
 const cats=familyFor(g.rules),oracle=independentEnergyOnly(offer);
 const operator=cpo[g.cpo]||(cpo[g.cpo]={groupCount:0,compiledConnectors:0,incompleteByProfile:{},incompleteReasons:{}});
 operator.groupCount++;operator.compiledConnectors+=g.count;
 for(const familyName of cats){
  const f=family[familyName]||(family[familyName]={groups:0,connectors:0,profileFailures:0});
  f.groups++;f.connectors+=g.count;
 }
 if(cats.includes('ZERO_OR_FREE'))unverifiedZeroPriceWeight+=g.count;
 for(const profile of profiles){
  const session={...profile.session,timeZone:source.timeZone,stationTimeZone:source.timeZone,powerKw:g.powerKw,includeCongestionFees:true};
  let result;
  if(currencyMismatch){
   // Never treat an unexpected USD/other-currency DOT-NL source as an EUR quote.
   result={complete:false,reason:'nl_non_eur_source_currency:'+sourceCurrency};
  }else{
   try{result=engine.evaluateOffer(offer,session);}
   catch(e){result={complete:false,reason:'exception:'+String(e).slice(0,200)};}
  }
  const out=profileTotals[profile.id];
  if(result?.complete===true&&Number.isFinite(result.totalEur)&&result.totalEur>=0){
   out.completeWeight+=g.count;out.completeGroups++;
   if(oracle!==null){
    independentOracleCases+=g.count;
    if(Math.abs(result.totalEur-oracle*session.energyKwh)>1e-5){
     oracleMismatchWeight+=g.count;
     markReason('independent_energy_only_oracle_mismatch',profile,g,result);
    }
   }
  }else{
   out.incompleteWeight+=g.count;out.incompleteGroups++;
   const reason=String(result?.reason||'nonfinite_or_negative_total');
   operator.incompleteByProfile[profile.id]=(operator.incompleteByProfile[profile.id]||0)+g.count;
   operator.incompleteReasons[reason]=(operator.incompleteReasons[reason]||0)+g.count;
   markReason(reason,profile,g,result);
   if(reason==='tariff_window_crossing_unsupported_components'){
    const r=result?.matchedRule||{};
    const flags={
     energyStepWh:Number(r.energyStepWh)>0,
     chargingTimeStepSeconds:Number(r.chargingTimeStepSeconds)>0,
     connectedTimeStepSeconds:Number(r.connectedTimeStepSeconds)>0,
     energyRoundingStartedKwh:r.energyRounding==='started_kwh',
     connectedTimeBlock:Number(r.connectedTimeBlockMinutes)>0||r.connectedTimeBlockEur!=null,
     connectedTimeAfterFree:r.connectedTimeFreeMinutes!=null||r.connectedTimePerMinuteAfterFreeEur!=null,
     connectedTimeInitialTier:r.connectedTimeInitialMinutes!=null||r.connectedTimeInitialFlatEur!=null,
     connectedTimeFixed:Number(r.connectedTimeComponentEur)>0,
     sessionFee:Number(r.sessionFeeEur)>0,
     minimumSession:r.minimumSessionEur!=null,
     holidayRule:r.holidayOnly===true||r.excludeHolidays===true,
     forceSameDay:r.mustEndSameLocalDay===true
    };
    for(const [flag,present] of Object.entries(flags)){
      if(present)segmentationBlockerWeights[flag]=(segmentationBlockerWeights[flag]||0)+g.count;
    }
    if(segmentationBlockerSamples.length<30)segmentationBlockerSamples.push({
     partyId:g.cpo,stationId:g.sampleStationId,evseId:g.sampleEvseId,
     tariffKey:g.tariffKey,weight:g.count,powerKw:g.powerKw,flags,
     matchedRule:{start:r.start,end:r.end,days:r.days,energyStepWh:r.energyStepWh,
      chargingTimeStepSeconds:r.chargingTimeStepSeconds,connectedTimeStepSeconds:r.connectedTimeStepSeconds,
      connectionFee:r.connectionFee,pricePerKwh:r.pricePerKwh,chargePerMinute:r.chargePerMinute,
      idlePerMinute:r.idlePerMinute,ocpiDurationBands:r.ocpiDurationBands}
    });
   }
   for(const name of cats)family[name].profileFailures+=g.count;
  }
 }
 totalFixtures++;compiledConnectors+=g.count;
}
assert.equal(compiledConnectors,source.compiledConnectors,'Lost weighted source connectors');
for(const p of profiles)assert.equal(profileTotals[p.id].completeWeight+profileTotals[p.id].incompleteWeight,compiledConnectors);
const bad=Object.entries(reasonWeights).sort((a,b)=>b[1]-a[1]);
const report={
 schemaVersion:1,kind:'V9_NL_READONLY_MULTI_PROFILE_ENGINE_SIMULATIONS',
 dataObservedAt:source.sourceGeneratedAt,
 inputCompressedSha256:source.inputCompressedSha256,
 engineSha256:crypto.createHash('sha256').update(fs.readFileSync(enginePath)).digest('hex'),
 adapterSha256:crypto.createHash('sha256').update(fs.readFileSync(adapterPath)).digest('hex'),
 productionPin:process.env.TCC_PRODUCTION_SHA||'unset',
 groupCount:totalFixtures,representedActiveCompiledConnectors:compiledConnectors,
 profileCount:profiles.length,weightedEvaluationCount:compiledConnectors*profiles.length,
 profiles:profiles.map(p=>({...p,results:profileTotals[p.id]})),
 families:family,
 cpo,
 failureReasonsWeighted:reasonWeights,
 failureExamplesByProfileAndReason:reasonExamples,
 segmentationBlockerWeights,segmentationBlockerSamples,
 independentEnergyOnlyOracleCases:independentOracleCases,
 independentOracleMismatchWeight:oracleMismatchWeight,
 zeroOrFreeSourceConnectorWeight:unverifiedZeroPriceWeight,
 nonEurSourceCurrencyWeight,nonEurCurrencyByCode,nonEurCurrencyExamples,
 implausibleSourcePowerWeight,
 sourceWarning:'Simulation success is not independently verified CPO quote; contractual restrictions and physical public access remain unverified.',
 publishedToTcc:false
};
fs.mkdirSync(path.dirname(reportPath),{recursive:true});
fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({
 report:'NL_V9_ENGINE_SIMULATION',dataAt:report.dataObservedAt,
 sourceSha:report.inputCompressedSha256,engineSha:report.engineSha256,
 groups:totalFixtures,weightedEvaluations:report.weightedEvaluationCount,
 profiles:report.profiles.map(p=>({id:p.id,complete:p.results.completeWeight,incomplete:p.results.incompleteWeight})),
 topReasons:bad.slice(0,18),independentOracleCases,oracleMismatchWeight,unverifiedZeroPriceWeight,
 nonEurSourceCurrencyWeight,nonEurCurrencyByCode,nonEurCurrencyExamples,implausibleSourcePowerWeight,
 segmentationBlockerWeights,segmentationBlockerSamples:segmentationBlockerSamples.slice(0,10)
}));
if(oracleMismatchWeight)process.exitCode=2;
