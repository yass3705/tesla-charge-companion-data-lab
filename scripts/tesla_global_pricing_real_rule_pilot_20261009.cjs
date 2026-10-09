#!/usr/bin/env node
'use strict';
/*
Read-only Tesla global tariffs regression against PINNED V9 engine and Tesla adapter.
A monetary result is *not validated* if any billable parameter is unmodelled.
*/
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const engine=require(path.resolve(process.argv[2]||'/tmp/tcc-v9-pinned-pricing-engine.js'));
const adapter=require(path.resolve(process.argv[3]||'/tmp/tcc-v9-pinned-tesla-adapter.js'));
const inFile=path.join(root,'reports/tariff-scenarios/tesla-global-real-rule-fixtures.json');
const fixtures=JSON.parse(fs.readFileSync(inFile,'utf8'));
const scopes=['FR','IT','CH','DE','ES','NL','UK','MA','BE'];
const timezones={FR:'Europe/Paris',IT:'Europe/Rome',CH:'Europe/Zurich',DE:'Europe/Berlin',
 ES:'Europe/Madrid',NL:'Europe/Amsterdam',UK:'Europe/London',MA:'Africa/Casablanca',BE:'Europe/Brussels'};
function chooseSession(cc,power){return {
 energyKwh:25,chargingMinutes:45,durationMinutes:50,totalChargingMinutes:45,
 powerKw:Number(power)||100,arrivalSoc:30,targetSoc:85,vehicleSoc:30,
 includeCongestionFees:true,postChargeMinutes:5,
 startAt:'2026-10-10T10:00:00Z',timeZone:timezones[cc]||'UTC'
};}
function normalize(x){
 const raw={id:x.stationId||'tesla-audit',countryCode:x.country==='UK'?'GB':x.country,
  powerKw:Number(x.configurationPowerKw)||100,
  chargingConfigurations:[{id:x.configurationId||'audit-cfg',powerKw:Number(x.configurationPowerKw)||100,
  pricing:{type:'rules',rules:[x.pricingRule]}}]};
 return adapter.normalizeStation(raw).offers[0];
}
function keyOf(x){return x.country+'/'+x.billing;}
const results=[];const counts={};const issues={};const examples=[];
for(const cc of scopes)counts[cc]={tested:0,computedClean:0,computedUnreliable:0,incomplete:0,exception:0};
for(const f of fixtures){
 const cc=f.country;
 if(!counts[cc])throw Error('Out-of-scope fixture country: '+cc);
 const rec={country:cc,stationId:f.stationId,configId:f.configurationId,billing:f.billing,
  ruleCurrency:f.currency,configurationPowerKw:f.configurationPowerKw};
 let status='exception';let reason=null;
 try{
  const offer=normalize(f);
  if(!offer){status='incomplete';reason='adapter_no_offer';}
  else{
   const r=engine.evaluateOffer(offer,chooseSession(cc,f.configurationPowerKw));
   const potential=[];
   if(f.billing==='powerMinute')potential.push('power_bands_flattened_from_rated_power_not_actual_power_trace');
   if(f.currency!=='EUR')potential.push('offer_currency_hardcoded_EUR_source_'+f.currency);
   const src=f.pricingRule||{};
   for(const k of ['afterMinutesRate','afterMinutesThreshold','afterMinutesCap','afterMinutesCapStart','afterMinutesCapEnd']){
    if(src[k]!=null&&src[k]!==0&&src[k]!=='')potential.push('unmodelled_source_field_'+k);
   }
   if(!r.complete){status='incomplete';reason=r.reason||'unknown';}
   else if(potential.length){status='computedUnreliable';reason=potential.join('|');}
   else{status='computedClean';}
   rec.modelTotalEur=r.complete?r.totalEur:null;rec.modelOfferCurrency=offer.currency;
   rec.modelComplete=r.complete;rec.unmodelledRisk=potential;
  }
 }catch(e){status='exception';reason=String(e&&e.message||e);}
 counts[cc].tested++;counts[cc][status]++;
 if(reason){issues[reason]=(issues[reason]||0)+1;if(examples.length<100)examples.push({...rec,status,reason});}
 results.push({...rec,status,reason});
}
const rawPowerRule={scope:'allDay',billing:'powerMinute',currency:'MAD',
  powerBands:[{minKw:0,maxKw:60,ratePerMinute:.5},{minKw:60,maxKw:100,ratePerMinute:1},
   {minKw:100,maxKw:180,ratePerMinute:2},{minKw:180,maxKw:250,ratePerMinute:3}]};
const synthOffer=adapter.normalizeStation({id:'test-power-trace',countryCode:'MA',powerKw:250,
 pricing:{type:'rules',rules:[rawPowerRule]}}).offers[0];
const staticEstimate=engine.evaluateOffer(synthOffer,{
 energyKwh:25,chargingMinutes:20,durationMinutes:20,startAt:'2026-10-10T10:00:00Z',timeZone:'Africa/Casablanca'});
// 10 minutes actually delivered at 50 kW, then 10 minutes at 120 kW.
// The correct reference is 10*0.5+10*2 = 25 MAD, NOT 20*3 = 60.
const deliveredPowerTruthMAD=25;
const checks=[
 {name:'nine_countries_explicit_in_scope',pass:scopes.every(x=>Object.hasOwn(counts,x))},
 {name:'actual_tesla_fixtures_loaded',pass:fixtures.length>0},
 {name:'power_minute_is_NOT_validated_without_power_trace',
  pass:staticEstimate.complete===true&&Math.abs(staticEstimate.totalEur-deliveredPowerTruthMAD)>0.01,
  engineReturn:staticEstimate.totalEur,referenceMAD:deliveredPowerTruthMAD},
 {name:'adapter_must_not_be_treated_as_currency_authority',
  pass:synthOffer.currency==='EUR'&&rawPowerRule.currency==='MAD',
  reportedOfferCurrency:synthOffer.currency,sourceCurrency:rawPowerRule.currency}
];
const report={
 generatedAt:new Date().toISOString(),mode:'TESLA_GLOBAL_REAL_RULE_FIXTURES_NON_EXHAUSTIVE',
 enginePin:process.env.TCC_V9_PRICING_SHA||'not_pinned',countries:counts,
 fixtureCount:fixtures.length,checks,issues,issueExamples:examples,
 warnings:[
  'Only structural Tesla fixtures: no claim of exhaustive real-session tariff accuracy.',
  'Never compare displayed model EUR directly with MAD until currency handling and FX are proven.',
  'An offer with powerMinute based on rated charger power is NOT a valid dynamic charging power calculation.',
  'Model-computed amounts with unmodelled fields must remain unvalidated, not published to V9.'
 ]};
fs.writeFileSync(path.join(root,'reports/tariff-scenarios/tesla-global-pricing-pilot-latest.json'),JSON.stringify(report,null,2)+'\n');
console.log('TESLA_GLOBAL_PRICING_PILOT='+JSON.stringify({total:fixtures.length,counts,checks,issues}));
if(checks.some(x=>!x.pass)||scopes.some(x=>counts[x].exception>0))process.exitCode=2;
