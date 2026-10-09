#!/usr/bin/env node
'use strict';
/*
FRANCE FIRST: compare V9 unchanged pricing engine on (a) documented deterministic
regression cases and (b) REAL France Electra/Electroverse published offer
structures. No source tariff is rewritten, no "unsupported" input becomes zero.
Requires pinned engine .js file as argv[2].
*/
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const engine=require(path.resolve(process.argv[2]||'/tmp/tcc-v9-pinned-pricing-engine.js'));
const publishedSamples=JSON.parse(fs.readFileSync(path.join(root,'reports/tariff-scenarios/france-real-offer-fixtures.json'),'utf8'));
const runtimeFile=path.join(root,'reports/tariff-scenarios/france-runtime-offer-fixtures.json');
const compiledSamples=fs.existsSync(runtimeFile)?JSON.parse(fs.readFileSync(runtimeFile,'utf8')):[];
const samples=[...publishedSamples,...compiledSamples];
const profile={energyKwh:25,durationMinutes:50,chargingMinutes:45,totalChargingMinutes:45,
 powerKw:22,arrivalSoc:30,targetSoc:85,vehicleSoc:30,includeCongestionFees:true,
 postChargeMinutes:5,startAt:'2026-10-10T11:00:00+02:00',timeZone:'Europe/Paris'};
const cases=[
 ['energy_only',{type:'rules',rules:[{scope:'allDay',pricePerKwh:.40}]},{energyKwh:25,durationMinutes:30,chargingMinutes:30},10],
 ['energy_and_connected',{type:'rules',rules:[{scope:'allDay',pricePerKwh:.4,pricePerMinute:.05}]},{energyKwh:25,durationMinutes:40,chargingMinutes:30},12],
 ['energy_and_charging',{type:'rules',rules:[{scope:'allDay',pricePerKwh:.4,chargePerMinute:.10}]},{energyKwh:25,durationMinutes:40,chargingMinutes:35},13.5],
 ['parking_after_charging',{type:'rules',rules:[{scope:'allDay',pricePerKwh:.4,idlePerMinute:.2}]},{energyKwh:25,durationMinutes:40,chargingMinutes:30},12],
 ['session_and_connection',{type:'rules',rules:[{scope:'allDay',pricePerKwh:.4,sessionFeeEur:1.3,connectionFee:.7}]},{energyKwh:25,durationMinutes:30,chargingMinutes:30},12],
 ['minimum_session',{type:'rules',rules:[{scope:'allDay',pricePerKwh:.4,minimumSessionEur:15}]},{energyKwh:5,durationMinutes:30,chargingMinutes:30},15],
 ['free_connected_10',{type:'rules',rules:[{scope:'allDay',connectedTimeFreeMinutes:10,connectedTimePerMinuteAfterFreeEur:.25}]},{energyKwh:0,durationMinutes:30,chargingMinutes:30},5],
 ['energy_wh_rounding',{type:'rules',rules:[{scope:'allDay',pricePerKwh:.5,energyStepWh:1000}]},{energyKwh:2.1,durationMinutes:20,chargingMinutes:20},1.5],
 ['ocpi_time_bands',{type:'rules',rules:[{scope:'allDay',ocpiDurationBands:[['TIME',0,600,.1],['TIME',600,null,.2]]}]},{energyKwh:0,durationMinutes:25,chargingMinutes:25},4],
 ['soc80_congestion',{type:'rules',rules:[{scope:'allDay',congestionTimePerMinute:.2}]},{energyKwh:25,durationMinutes:40,chargingMinutes:40,totalChargingMinutes:40,arrivalSoc:70,targetSoc:90},4],
 ['soc80_congestion_optout',{type:'rules',rules:[{scope:'allDay',congestionTimePerMinute:.2}]},{energyKwh:25,durationMinutes:40,chargingMinutes:40,totalChargingMinutes:40,arrivalSoc:70,targetSoc:90,includeCongestionFees:false},0],
 ['minimum_total',{type:'rules',rules:[{scope:'allDay',pricePerKwh:.4}],minimumTotalEur:19},{energyKwh:25,durationMinutes:30,chargingMinutes:30},19],
 ['conditional_fee_above_kwh',{type:'rules',rules:[{scope:'allDay',pricePerKwh:.4}],conditionalSessionFees:[{amountEur:2,conditions:[{kind:'energy_above_kwh',value:20}]}]},{energyKwh:25,durationMinutes:30,chargingMinutes:30},12],
 ['post_charge_grace',{type:'rules',rules:[{scope:'allDay',pricePerKwh:.4}],postChargeFee:{graceMinutes:5,eurPerMinute:.20}},{energyKwh:25,durationMinutes:30,chargingMinutes:30,postChargeMinutes:15},12],
 ['time_window_crossing_simple',{type:'rules',rules:[{scope:'timeRange',start:'10:00',end:'12:00',pricePerKwh:.2},{scope:'timeRange',start:'12:00',end:'14:00',pricePerKwh:.4}]},{energyKwh:20,durationMinutes:60,chargingMinutes:60,startAt:'2026-10-10T11:30:00+02:00'},6],
 ['time_window_crossing_fixed_unsupported',{type:'rules',rules:[{scope:'timeRange',start:'10:00',end:'12:00',pricePerKwh:.2,sessionFeeEur:2},{scope:'timeRange',start:'12:00',end:'14:00',pricePerKwh:.4,sessionFeeEur:2}]},{energyKwh:20,durationMinutes:60,chargingMinutes:60,startAt:'2026-10-10T11:30:00+02:00'},null],
 ['missing_congestion_soc_fails_closed',{type:'rules',rules:[{scope:'allDay',congestionTimePerMinute:.3}]},{energyKwh:20,durationMinutes:40,chargingMinutes:40,arrivalSoc:null,targetSoc:null,vehicleSoc:null},null]
];
function evaluate(offer,session){try{return engine.evaluateOffer(offer,session)}catch(e){return {complete:false,reason:'runtime_exception',message:String(e.message||e).slice(0,220)}}}
const synthetic=[];
for(const [name,pricing,patch,expected] of cases){
 const session={...profile,...patch};
 const value=evaluate({id:'regression:'+name,pricing,currency:'EUR'},session);
 const total=Number(value.totalEur);
 const good=expected===null?value.complete===false:!!value.complete&&Number.isFinite(total)&&Math.abs(total-expected)<.000001;
 synthetic.push({name,expected,actual:value.totalEur??null,complete:value.complete===true,reason:value.reason??null,pass:good});
}
const counters={};const familyStats={};const typeStats={};const reasonCounts={};const sampleIssues=[];
const unmodeledFields={};const unmodeledExamples=[];
function legacyUnmodeledFields(offer){
 const rules=[...(offer?.pricing?.rules||[]),...(offer?.pricing?.componentGroups||[]).flatMap(x=>x.rules||[])];
 const result=[];
 for(const rule of rules){
  // Current pinned pricing-engine.js does not inspect any of these legacy fields.
  // afterMinutesRate > 0 could materially change the payable charge.
  if(Number(rule?.afterMinutesRate)>0){
   result.push('afterMinutesRate');
   if(rule.afterMinutesThreshold!=null)result.push('afterMinutesThreshold');
   if(Number(rule.afterMinutesCap)>0)result.push('afterMinutesCap');
   if(rule.afterMinutesCapStart!=null)result.push('afterMinutesCapStart');
   if(rule.afterMinutesCapEnd!=null)result.push('afterMinutesCapEnd');
  }
 }
 return [...new Set(result)];
}
for(const s of samples){
 const offer=s.offer;
 let power=Number(offer?.metadata?.powerKw??offer?.maxPowerKw??0);
 if(!Number.isFinite(power)||power<=0)power=22;
 const session={...profile,powerKw:power};
 const v=evaluate(offer,session);
 const isValid=v.complete===true&&Number.isFinite(Number(v.totalEur));
 const unmodeled=legacyUnmodeledFields(offer);
 const st=isValid?(unmodeled.length?'computed_with_unmodeled_source_fields':'computed'):v.reason==='runtime_exception'?'exception':'incomplete';
 if(unmodeled.length){
   for(const field of unmodeled)unmodeledFields[field]=(unmodeledFields[field]||0)+1;
   if(unmodeledExamples.length<90)unmodeledExamples.push({offerId:offer?.id,provider:s.provider,origin:s.origin,unmodeledFields:unmodeled});
 }
 const provider=s.provider||'unknown';counters[provider]??={total:0,computed:0,incomplete:0,exception:0,computed_with_unmodeled_source_fields:0};
 counters[provider].total++;counters[provider][st]++;
 typeStats[s.tariffType]??={total:0,computed:0,incomplete:0,exception:0,computed_with_unmodeled_source_fields:0};typeStats[s.tariffType].total++;typeStats[s.tariffType][st]++;
 for(const k of s.families||[]){familyStats[k]??={total:0,computed:0,incomplete:0,exception:0,computed_with_unmodeled_source_fields:0};familyStats[k].total++;familyStats[k][st]++;}
 if(!isValid){
  const reason=String(v.reason||'reason_missing');reasonCounts[reason]=(reasonCounts[reason]||0)+1;
  if(sampleIssues.length<150)sampleIssues.push({offerId:offer?.id,provider,tariffType:s.tariffType,signature:s.signatureId,reason,matchedRule:v.matchedRule??null});
 }
}
const report={generatedAt:new Date().toISOString(),enginePin:process.env.TCC_V9_PRICING_SHA||'not_pinned',
 status:synthetic.every(x=>x.pass)?'synthetic_regressions_pass':'synthetic_regressions_failed',
 mode:'FRANCE_PILOT_REAL_PUBLISHED_EMSP_OFFERS_NON_EXHAUSTIVE_SAMPLE',
 caveats:['Real-offer results use a single illustrative session, not end-user cost or a claim about all session profiles',
  'A result marked incomplete is not evidence that the physical charging point is inactive',
  'Engine gaps and missing session context must be separately reviewed before changing pricing rules',
  'Synthetic cases are deterministic regression tests; sample offers are actual unchanged published Data Lab records'],
 sessionProfile:profile,syntheticCases:synthetic,samplesTested:samples.length,
 providers:counters,pricingTypes:typeStats,families:familyStats,
 incompleteReasons:reasonCounts,sampleIssues,
 unmodeledLegacyFields:unmodeledFields,unmodeledExamples,
 warnings:['computed_with_unmodeled_source_fields means engine returned a number but source billing components may be silently ignored; never treat these as validated amounts']};
const out=path.join(root,'reports/tariff-scenarios/france-pricing-pilot-latest.json');
fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n','utf8');
console.log('FRANCE_PRICING_PILOT='+JSON.stringify({syntheticPassed:synthetic.filter(x=>x.pass).length,syntheticTotal:synthetic.length,
syntheticFailed:synthetic.filter(x=>!x.pass).map(x=>x.name),realSamples:samples.length,providers:counters,pricingTypes:typeStats,incompleteReasons:reasonCounts,unmodeledLegacyFields:unmodeledFields}));
if(!synthetic.every(x=>x.pass))process.exitCode=2;
