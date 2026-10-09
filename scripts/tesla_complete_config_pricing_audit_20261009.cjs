#!/usr/bin/env node
'use strict';
/* Complete Tesla V9 configuration audit, staging only. Native currency, no FX. */
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const engine=require(path.resolve(process.argv[2]||'/tmp/tcc-v9-pinned-pricing-engine.js'));
const adapter=require(path.resolve(process.argv[3]||'/tmp/tcc-v9-pinned-tesla-adapter.js'));
const dataDir=path.join(root,'reports/tariff-scenarios');
const fixtures=JSON.parse(fs.readFileSync(path.join(dataDir,'tesla-global-complete-config-fixtures.json'),'utf8'));
const countries=['FR','IT','CH','DE','ES','NL','UK','MA','BE'];
const zones={FR:'Europe/Paris',IT:'Europe/Rome',CH:'Europe/Zurich',DE:'Europe/Berlin',
 ES:'Europe/Madrid',NL:'Europe/Amsterdam',UK:'Europe/London',MA:'Africa/Casablanca',BE:'Europe/Brussels'};
const deepCopy=x=>JSON.parse(JSON.stringify(x));
const round=n=>Math.round((n+Number.EPSILON)*1e6)/1e6;
function profile(cc,power,hour=10){
 const max=Number(power)||150;
 return {energyKwh:25,chargingMinutes:45,durationMinutes:50,totalChargingMinutes:45,
   powerKw:max,arrivalSoc:30,targetSoc:85,vehicleSoc:30,includeCongestionFees:true,
   postChargeMinutes:5,timeZone:zones[cc],
   startAt:'2026-10-10T'+String(hour).padStart(2,'0')+':00:00Z',
   powerSegments:[{startMin:0,endMin:20,powerKw:Math.min(50,max)},
                  {startMin:20,endMin:45,powerKw:Math.min(120,max)}]};
}
function sourceOffer(f){
 const raw={id:f.stationId||'tesla-fixture',countryCode:f.country==='UK'?'GB':f.country,
 powerKw:Number(f.configurationPowerKw)||150,
 chargingConfigurations:[{id:f.configurationId||'main',powerKw:Number(f.configurationPowerKw)||150,
 pricing:f.pricing}]};
 const compiled=adapter.normalizeStation(raw)?.offers?.[0];
 if(!compiled)throw Error('tesla_adapter_generated_no_offer');
 const src=deepCopy(f.pricing);
 const rules=Array.isArray(src?.rules)?src.rules:[];
 if(!rules.length)throw Error('missing_original_source_rules');
 const nativeCurrencies=[...new Set(rules.map(r=>String(r.currency||src.currency||'').toUpperCase()))];
 if(nativeCurrencies.length!==1||!['EUR','GBP','CHF','MAD'].includes(nativeCurrencies[0]))
   throw Error('unresolved_mixed_or_unsupported_currency');
 const currency=nativeCurrencies[0];
 for(const r of rules){
   const billing=String(r.billing||'');
   if(billing==='minute'){
     if(r.pricePerMinute!=null&&Number(r.pricePerMinute)!==0)
       throw Error('minute_source_has_ambiguous_connected_and_charging_rates');
   }else if(billing==='powerMinute'){
     if(!Array.isArray(r.powerBands)||!r.powerBands.length)
       throw Error('power_minute_source_without_bands');
     if(r.pricePerMinute!=null&&Number(r.pricePerMinute)!==0)
       throw Error('power_minute_source_has_independent_connected_rate');
   }else if(billing!=='kwh')throw Error('unrecognized_tesla_billing_'+billing);
 }
 return {...compiled,currency,pricing:src};
}
function bandRate(rule,power){
 const bands=[...(rule.powerBands||[])].sort((a,b)=>Number(a.minKw)-Number(b.minKw));
 const n=Number(power);
 if(!Number.isFinite(n)||n<0)return null;
 const maximum=Math.max(...bands.map(x=>Number(x.maxKw)));
 const matches=bands.filter(b=>{
    const lo=Number(b.minKw),hi=Number(b.maxKw);
    return n>=lo&&(n<hi||(n===maximum&&hi===maximum));
 });
 return matches.length===1&&Number.isFinite(Number(matches[0].ratePerMinute))
   ?Number(matches[0].ratePerMinute):null;
}
function powerFromTrace(segments,minute){
 if(!Array.isArray(segments))return null;
 const list=segments.filter(s=>minute>=Number(s.startMin)&&minute<Number(s.endMin));
 return list.length===1?Number(list[0].powerKw):null;
}
function computeCorrected(f,session){
 let offer;
 try{offer=sourceOffer(f);}catch(e){return {complete:false,reason:String(e.message||e)};}
 const rules=offer.pricing.rules,cc=f.country,currency=offer.currency;
 const hasPower=rules.some(r=>r.billing==='powerMinute');
 if(hasPower&&!Array.isArray(session.powerSegments))
    return {complete:false,reason:'actual_delivered_power_trace_required',currency};
 const safeRules=deepCopy(rules);
 if(hasPower)for(const r of safeRules)if(r.billing==='powerMinute'){
   delete r.pricePerMinute;
   delete r.chargePerMinute;
   delete r.chargingTimePerMinuteEur;
 }
 const safeOffer={...offer,pricing:{...offer.pricing,rules:safeRules}};
 const base=engine.evaluateOffer(safeOffer,session);
 if(!base.complete)return {complete:false,reason:base.reason||'base_calculation_incomplete',currency};
 let powerMinuteTotal=0;
 if(hasPower){
   const duration=Number(session.chargingMinutes);
   if(!Number.isFinite(duration)||duration<0)
     return{complete:false,reason:'charging_duration_missing',currency};
   const start=new Date(session.startAt);
   if(Number.isNaN(start.getTime()))return{complete:false,reason:'missing_or_invalid_session_start',currency};
   for(let minute=0;minute<duration-1e-8;minute+=1){
     const slice=Math.min(1,duration-minute),middle=minute+slice/2;
     const kW=powerFromTrace(session.powerSegments,middle);
     if(kW==null||!Number.isFinite(kW))return{complete:false,reason:'power_trace_gap_or_overlap',currency};
     const at=new Date(start.getTime()+middle*60000);
     const match=engine.matchingRuleDetailed(offer.pricing,at,session.timeZone,session);
     if(!match.rule)return{complete:false,reason:match.reason||'power_tariff_window_missing',currency};
     if(match.rule.billing!=='powerMinute')return{complete:false,reason:'mixed_billing_modes_reconciliation_needed',currency};
     const rate=bandRate(match.rule,kW);
     if(rate==null)return{complete:false,reason:'measured_power_not_covered_by_bands',currency};
     powerMinuteTotal+=rate*slice;
   }
 }
 const value=round(base.totalEur+powerMinuteTotal);
 return {complete:true,totalNative:value,currency,
   powerMinuteNative:round(powerMinuteTotal),underlyingEngineNative:base.totalEur,
   modelStatus:'STAGING_NOT_SOURCE_FRESHNESS_VALIDATED'};
}
const stats=Object.fromEntries(countries.map(cc=>[cc,{configurations:0,sessions:0,computed:0,
   incomplete:0,baselineMissingTime:0,correctedMissingTime:0,
   currencyDisagreements:0,powerMinuteSessions:0}]));
const reasons={},rows=[];
for(const f of fixtures){
 const cc=f.country;if(!stats[cc])throw Error('missing_country_'+cc);
 stats[cc].configurations++;
 for(const hour of [2,10,17,22]){
   const session=profile(cc,f.configurationPowerKw,hour);
   const output=computeCorrected(f,session);
   let baseline=null;
   try{
     const compiled=adapter.normalizeStation({id:f.stationId,countryCode:cc==='UK'?'GB':cc,
       chargingConfigurations:[{id:f.configurationId,powerKw:f.configurationPowerKw,pricing:f.pricing}]});
     baseline=engine.evaluateOffer(compiled.offers[0],session);
     if(!baseline.complete&&baseline.reason==='no_matching_time_rule')stats[cc].baselineMissingTime++;
     const sourceCurrency=String(f.pricing?.rules?.[0]?.currency||'');
     if(compiled.offers[0].currency!==sourceCurrency)stats[cc].currencyDisagreements++;
   }catch(e){reasons['baseline_exception_'+String(e.message||e)]=(reasons['baseline_exception_'+String(e.message||e)]||0)+1;}
   stats[cc].sessions++;
   if((f.pricing.rules||[]).some(r=>r.billing==='powerMinute'))stats[cc].powerMinuteSessions++;
   if(output.complete)stats[cc].computed++;else{
     stats[cc].incomplete++;
     reasons[output.reason]=(reasons[output.reason]||0)+1;
     if(output.reason==='power_tariff_window_missing'||output.reason==='no_matching_time_rule')
       stats[cc].correctedMissingTime++;
   }
   if(!output.complete||!baseline?.complete||cc==='MA'||(f.pricing.rules||[]).some(r=>r.billing==='minute'))
     rows.push({country:cc,stationId:f.stationId,configurationId:f.configurationId,
       testedHourUtc:hour,nativeCurrency:output.currency||null,complete:output.complete,
       reason:output.reason||null,totalNative:output.totalNative??null,
       baselineComplete:baseline?.complete??null,baselineReason:baseline?.reason||null});
 }
}
function check(name,condition,detail){return {name,pass:Boolean(condition),detail:detail||null};}
const sample=f=>({country:f.country,stationId:f.stationId,configurationId:f.configurationId,
   configurationPowerKw:f.configurationPowerKw,pricing:f.pricing});
const fixtureMA=fixtures.find(f=>f.country==='MA'&&(f.pricing.rules||[]).some(r=>r.billing==='powerMinute'));
const traceRule={scope:'allDay',billing:'powerMinute',currency:'MAD',
 powerBands:[{minKw:0,maxKw:60,ratePerMinute:.5},{minKw:60,maxKw:100,ratePerMinute:1},
 {minKw:100,maxKw:180,ratePerMinute:2},{minKw:180,maxKw:250,ratePerMinute:3}]};
const standard={country:'MA',stationId:'power-trace-test',configurationId:'main',
 configurationPowerKw:250,pricing:{type:'rules',rules:[traceRule]}};
const trace={...profile('MA',250,10),energyKwh:20,durationMinutes:20,chargingMinutes:20,
 powerSegments:[{startMin:0,endMin:10,powerKw:50},{startMin:10,endMin:20,powerKw:120}]};
const expected=computeCorrected(standard,trace);
const noTrace=computeCorrected(standard,{...trace,powerSegments:null});
const fixedMinute={country:'FR',stationId:'fixed-minute-test',configurationId:'main',
 configurationPowerKw:120,pricing:{type:'rules',rules:[{scope:'allDay',billing:'minute',
 currency:'EUR',chargePerMinute:1}]}};
const minuteSession={...profile('FR',120,10),energyKwh:0,durationMinutes:20,chargingMinutes:20};
const minuteResult=computeCorrected(fixedMinute,minuteSession);
const checks=[
 check('all_nine_countries_have_real_complete_configs',countries.every(c=>stats[c].configurations>0)),
 check('all_real_complete_config_samples_tested',fixtures.length===Object.values(stats).reduce((a,v)=>a+v.configurations,0)),
 check('real_morocco_power_minute_included',Boolean(fixtureMA)),
 check('power_trace_example_25_MAD',expected.complete&&expected.totalNative===25,expected),
 check('missing_power_trace_fails_closed',!noTrace.complete&&noTrace.reason==='actual_delivered_power_trace_required'),
 check('minute_tariff_single_billing_20_EUR',minuteResult.complete&&minuteResult.totalNative===20,minuteResult),
 check('every_case_has_defined_country_currency',fixtures.every(f=>(f.pricing.rules||[]).every(r=>Boolean(r.currency))))
];
const report={generatedAt:new Date().toISOString(),
 mode:'TESLA_COMPLETE_CONFIG_RULE_WINDOWS_STAGING_NATIVE_CURRENCY_NOT_PRODUCTION',
 referenceEnginePin:process.env.TCC_V9_PRICING_SHA||'unknown',
 fixtureConfigurations:fixtures.length,byCountry:stats,checks,reasons,exceptionRows:rows,
 interpretation:{
  noMatchingRule:'Prior 16 no_matching_time_rule results were single-window fixture tests. Compare full configurations before claiming true coverage gaps.',
  currency:'Native CHF/GBP/MAD amounts must not be presented as EUR; FX is separate.',
  power:'Real delivered-power trace, not rated stall kW, is compulsory for powerMinute.',
  provenance:'Source timestamps are audited separately. Passing calculation is not proof current charge price.',
  baseline:'Existing production V9 adapter/engine was not mutated; corrected amounts are staging only.'}};
fs.writeFileSync(path.join(dataDir,'tesla-complete-config-pricing-audit-latest.json'),JSON.stringify(report,null,2)+'\n');
console.log('TESLA_COMPLETE_CONFIG_AUDIT='+JSON.stringify({
 fixtures:fixtures.length,byCountry:stats,reasons,checks}));
if(checks.some(x=>!x.pass))process.exitCode=2;
