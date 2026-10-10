#!/usr/bin/env node
'use strict';
const fs=require('node:fs');
const assert=require('node:assert/strict');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const base=process.argv[2]||'/tmp/tcc-v9-new-pricing.js';
const directPath=process.argv[3]||'/tmp/tcc-v9-new-direct-offers.json';
const emspPath=process.argv[4]||'/tmp/tcc-v9-new-emsp-offers.json';
const engine=require(path.resolve(base));
const direct=JSON.parse(fs.readFileSync(directPath,'utf8'));
const emsp=JSON.parse(fs.readFileSync(emspPath,'utf8'));
const all=[...(direct.directOffers||[]),...(emsp.subscriptionOffers||[]),...(emsp.emspOffers||[])];
const verifiedIds=['pluginn-direct','pluginn-chargepass-basic','pluginn-chargepass-intense',
  'sigeif-24','sigeif-50-100','sigeif-7-22'];
const fixtures=JSON.parse(fs.readFileSync(path.join(root,'reports/tariff-scenarios/france-runtime-offer-fixtures.json'),'utf8'));
const pilot=JSON.parse(fs.readFileSync(path.join(root,'reports/tariff-scenarios/france-real-offer-fixtures.json'),'utf8'));
const selected=verifiedIds.map(id=>{
 const offer=all.find(x=>x.id===id);
 assert(offer,'missing verified source offer '+id);
 const r=offer.pricing.rules.find(r=>r.afterMinutesRate>0);
 assert.equal(r.afterMinutesComponent,'CONNECTED_TIME',id+' incorrectly classified');
 if(id==='sigeif-7-22')assert.equal(r.afterMinutesCapMode,'night_window_local_per_night');
 return offer;
});
const checks=[],failures=[];
const session=(duration,startAt='2026-10-10T10:00:00+02:00',extra={})=>({
 energyKwh:20,durationMinutes:duration,chargingMinutes:Math.min(40,duration),
 startAt,timeZone:'Europe/Paris',arrivalSoc:40,targetSoc:75,...extra
});
const evaluate=(offer,profile)=>engine.evaluateOffer(offer,profile);
function check(name,offer,profile,expected){
 let actual;
 try{
  const r=evaluate(offer,profile);
  actual=r.complete?r.totalEur:r.reason;
  const pass=typeof expected==='number'?r.complete&&Math.abs(r.totalEur-expected)<1e-6:(!r.complete&&r.reason===expected);
  checks.push({name,pass,expected,actual,complete:r.complete,component:r.components?.afterMinutes||null});
  if(!pass)failures.push(name+' actual='+actual+' expected='+expected);
 }catch(e){checks.push({name,pass:false,expected,error:String(e)});failures.push(name+' '+String(e));}
}
const offer=id=>selected.find(o=>o.id===id);
for(const o of selected){
 const r=o.pricing.rules.find(x=>x.afterMinutesRate>0);
 const baseAmount=r.pricePerKwh*20;
 for(const duration of [50,60,61,90,120,180,200,300]){
  if(o.id==='sigeif-7-22')continue;
  const surcharge=Math.max(0,duration-r.afterMinutesThreshold)*r.afterMinutesRate;
  check(o.id+'_'+duration,o,session(duration),Math.round((baseAmount+surcharge)*1000000)/1000000);
 }
}
check('sigeif_7_22_before_threshold',offer('sigeif-7-22'),session(180,'2026-10-10T09:00:00+02:00'),7.8);
check('sigeif_7_22_day_uncapped',offer('sigeif-7-22'),session(300,'2026-10-10T09:00:00+02:00'),13.8);
check('sigeif_7_22_night_capped',offer('sigeif-7-22'),session(600,'2026-10-10T17:00:00+02:00'),11.8);
check('sigeif_7_22_day_night_split',offer('sigeif-7-22'),session(600,'2026-10-10T14:00:00+02:00'),20.8);
const synthetic={id:'synthetic',currency:'EUR',pricing:{type:'rules',rules:[{
 scope:'allDay',pricePerKwh:0.4,afterMinutesRate:0.3,afterMinutesThreshold:60
}]}};
check('no_unverified_component',synthetic,session(90),'after_minutes_component_unverified');
const connected=JSON.parse(JSON.stringify(synthetic));
connected.pricing.rules[0].afterMinutesComponent='CONNECTED_TIME';
check('connected_uses_occupancy_not_charging',connected,session(90),17);
const time=JSON.parse(JSON.stringify(connected));time.pricing.rules[0].afterMinutesComponent='TIME';
check('charging_component_only_charging',time,session(90),8);
const parking=JSON.parse(JSON.stringify(connected));parking.pricing.rules[0].afterMinutesComponent='PARKING_TIME';
check('parking_component_idle_phase',parking,session(90),17);
const unknownCap=JSON.parse(JSON.stringify(connected));unknownCap.pricing.rules[0].afterMinutesCap=4;
check('unknown_cap_mode_fails_closed',unknownCap,session(90),'after_minutes_cap_window_requires_source_confirmation');
const negativeCap=JSON.parse(JSON.stringify(connected));negativeCap.pricing.rules[0].afterMinutesCap=-1;
check('negative_cap_fails_closed',negativeCap,session(90),'after_minutes_invalid_cap_value');
const nonEurCap=JSON.parse(JSON.stringify(offer('sigeif-7-22')));
nonEurCap.pricing.rules[0].currency='CHF';
check('non_eur_cap_fails_closed',nonEurCap,session(300,'2026-10-10T17:00:00+02:00'),
 'after_minutes_cap_currency_unverified');
const missingTime=JSON.parse(JSON.stringify(offer('sigeif-7-22')));
check('night_cap_missing_time_context',missingTime,
 {...session(300),startAt:null,timeZone:null},'after_minutes_cap_requires_timezone_and_start');
// Legacy Electra eMSP must not be guessed to be CONNECTED_TIME.
const electra=[...fixtures,...pilot].filter(x=>x.provider?.includes('Electra') &&
  (x.offer?.pricing?.rules||[]).some(r=>Number(r.afterMinutesRate)>0));
for(const sample of electra.slice(0,6)){
 const r=evaluate(sample.offer,session(90));
 const pass=r.complete===false;
 checks.push({name:'electra_missing_semantics_'+sample.offer.id,pass,actual:r.reason||r.totalEur});
 if(!pass)failures.push('Electra semantics guessed '+sample.offer.id);
}
const report={generatedAt:new Date().toISOString(),mode:'STAGING_ENGINE_BRANCH_ONLY',
 sixVerifiedOffers:selected.map(x=>x.id),electraLegacySamples:electra.length,
 checksTotal:checks.length,passed:checks.filter(x=>x.pass).length,failed:failures.length,
 failures,checks,publications:'none'};
fs.mkdirSync(path.join(root,'reports/tariff-scenarios'),{recursive:true});
fs.writeFileSync(path.join(root,'reports/tariff-scenarios/after-minutes-staging-validation-2026-10-11.json'),
 JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({result:failures.length?'FAILED':'PASS',summary:{
 offers:report.sixVerifiedOffers.length,checks:report.checksTotal,passed:report.passed,failed:report.failed,
 electraSamples:report.electraLegacySamples},failures}));
if(failures.length)process.exitCode=1;
