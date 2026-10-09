#!/usr/bin/env node
'use strict';
/*
Read-only candidate for legacy afterMinutesRate tariffs.
No production engine modifications. Until source contract validates cap windows,
mark those cases incomplete rather than report potentially wrong amounts.
*/
const fs=require('node:fs');
const path=require('node:path');

const money=x=>Math.round((x+Number.EPSILON)*1e6)/1e6;
function ruleHasActiveSurcharge(rule){
  return Number(rule?.afterMinutesRate)>0;
}
function isAllDayCap(rule){
  const start=rule?.afterMinutesCapStart||'00:00';
  const end=rule?.afterMinutesCapEnd||'24:00';
  return (start==='00:00'&&end==='24:00')||start===end;
}
function evaluateCandidate(engine,offer,session){
  const original=engine.evaluateOffer(offer,session);
  if(!original.complete)return {...original,extensionStatus:'engine_incomplete'};
  const pricing=offer?.pricing||{},rules=pricing.rules||[];
  const active=rules.filter(ruleHasActiveSurcharge);
  if(!active.length)return {...original,extensionStatus:'unmodified',additionalCostEur:0};
  if(pricing.type!=='rules'||rules.length!==1||active.length!==1||active[0].scope!=='allDay'){
    return {complete:false,reason:'after_minutes_rule_selection_needs_validation',offerId:offer?.id||null};
  }
  const rule=active[0];
  if(String(rule.currency||offer.currency||'EUR').toUpperCase()!=='EUR'){
    return {complete:false,reason:'after_minutes_currency_requires_validation',offerId:offer?.id||null};
  }
  const occupied=Number(session.durationMinutes);
  const threshold=Number(rule.afterMinutesThreshold);
  const rate=Number(rule.afterMinutesRate);
  const cap=Number(rule.afterMinutesCap||0);
  if(!Number.isFinite(occupied)||occupied<0||!Number.isFinite(threshold)||threshold<0||
     !Number.isFinite(rate)||rate<0||!Number.isFinite(cap)||cap<0){
    return {complete:false,reason:'invalid_after_minutes_input',offerId:offer?.id||null};
  }
  if(cap>0&&!isAllDayCap(rule)){
    return {complete:false,reason:'after_minutes_cap_window_requires_source_confirmation',offerId:offer?.id||null};
  }
  const billable=Math.max(0,occupied-threshold);
  const raw=money(billable*rate),added=cap>0?Math.min(cap,raw):raw;
  return {
    ...original,totalEur:money(original.totalEur+added),
    extensionStatus:'candidate_computed_not_production_validated',
    additionalCostEur:money(added),
    components:{...original.components,afterMinutesCandidate:{
      ratePerMinuteEur:rate,thresholdMinutes:threshold,connectedMinutes:occupied,
      billableMinutes:billable,rawCostEur:raw,capEur:cap||null,costEur:money(added),
      sourceContract:'legacy_fields_pending_live_CPO_confirmation'
    }}
  };
}
function runPilot(engine,fixtures){
  const selected=fixtures.filter(x=>(x.offer?.pricing?.rules||[]).some(ruleHasActiveSurcharge));
  const profiles=[50,61,90,120,180,200,300];
  const rows=[],summary={offers:selected.length,profiles:profiles.length,computed:0,incomplete:0,regressionMismatch:0};
  for(const x of selected)for(const duration of profiles){
    const profile={energyKwh:20,chargingMinutes:Math.min(40,duration),durationMinutes:duration,
      startAt:'2026-10-10T10:00:00+02:00',timeZone:'Europe/Paris',
      includeCongestionFees:true,vehicleSoc:50,targetSoc:80};
    const original=engine.evaluateOffer(x.offer,profile);
    const newer=evaluateCandidate(engine,x.offer,profile);
    if(newer.complete)summary.computed++;else summary.incomplete++;
    if(newer.complete&&(newer.totalEur+1e-8<original.totalEur))summary.regressionMismatch++;
    rows.push({offerId:x.offer.id,provider:x.provider,durationMinutes:duration,
      baselineEur:original.complete?original.totalEur:null,candidateEur:newer.complete?newer.totalEur:null,
      extraEur:newer.additionalCostEur??null,status:newer.extensionStatus||'incomplete',reason:newer.reason||null});
  }
  return {summary,rows};
}
if(require.main===module){
  const engine=require(path.resolve(process.argv[2]||'/tmp/tcc-v9-pinned-pricing-engine.js'));
  const root=path.resolve(__dirname,'..');
  const source=JSON.parse(fs.readFileSync(path.join(root,'reports/tariff-scenarios/france-runtime-offer-fixtures.json'),'utf8'));
  const overlays=JSON.parse(fs.readFileSync(path.join(root,'reports/tariff-scenarios/france-real-offer-fixtures.json'),'utf8'));
  source.push(...overlays);
  const checks=[];
  function check(name,rule,duration,expected){
    const offer={id:name,currency:'EUR',pricing:{type:'rules',rules:[{scope:'allDay',pricePerKwh:0,...rule}]}};
    const profile={energyKwh:0,chargingMinutes:duration,durationMinutes:duration,
      startAt:'2026-10-10T09:00:00Z',timeZone:'Europe/Paris'};
    const result=evaluateCandidate(engine,offer,profile);
    checks.push({name,expected,result:result.complete?result.additionalCostEur:result.reason,
      pass:expected===null?!result.complete:result.complete&&Math.abs(result.additionalCostEur-expected)<1e-7});
  }
  check('before_threshold',{afterMinutesRate:0.3,afterMinutesThreshold:60},50,0);
  check('exact_threshold',{afterMinutesRate:0.3,afterMinutesThreshold:60},60,0);
  check('after_threshold',{afterMinutesRate:0.3,afterMinutesThreshold:60},200,42);
  check('long_occupied',{afterMinutesRate:0.2,afterMinutesThreshold:120},200,16);
  check('all_day_cap',{afterMinutesRate:0.3,afterMinutesThreshold:60,afterMinutesCap:10},200,10);
  check('overnight_cap_fails_closed',{afterMinutesRate:0.05,afterMinutesThreshold:180,
    afterMinutesCap:4,afterMinutesCapStart:'20:00',afterMinutesCapEnd:'08:00'},300,null);
  const real=runPilot(engine,source);
  const report={generatedAt:new Date().toISOString(),status:checks.every(x=>x.pass)&&!real.summary.regressionMismatch
    ?'staging_checks_pass':'staging_checks_failed',
    mode:'READ_ONLY_AFTER_MINUTES_CANDIDATE',checks,...real,
    limitations:['No V9 changes','Non-EUR and multiple time-window rules fail closed',
      'Source CPO confirmation required for time-dependent cap windows',
      'Cases without afterMinutesRate are not transformed']};
  const file=path.join(root,'reports/tariff-scenarios/france-after-minutes-candidate-latest.json');
  fs.writeFileSync(file,JSON.stringify(report,null,2)+'\n');
  console.log('AFTER_MINUTES_CANDIDATE='+JSON.stringify({status:report.status,checks,summary:real.summary}));
  if(report.status!=='staging_checks_pass')process.exitCode=2;
}
module.exports={evaluateCandidate,runPilot};
