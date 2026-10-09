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
function minOfDay(at,timeZone){
  const p=new Intl.DateTimeFormat('en-GB',{timeZone,hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(at);
  const get=t=>Number(p.find(x=>x.type===t)?.value);
  return get('hour')*60+get('minute');
}
function nightKey(at,zone,minute){
  const p=new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(at);
  const get=t=>Number(p.find(x=>x.type===t)?.value);
  const date=new Date(Date.UTC(get('year'),get('month')-1,get('day')-(minute<480?1:0)));
  return date.toISOString().slice(0,10);
}
function strictFinite(value){return value!==null&&value!==undefined&&value!==''&&Number.isFinite(Number(value));}
function evaluateCandidate(engine,offer,session){
  const original=engine.evaluateOffer(offer,session);
  if(!original.complete)return {...original,extensionStatus:'engine_incomplete'};
  const pricing=offer?.pricing||{},rules=Array.isArray(pricing.rules)?pricing.rules:[];
  const active=rules.filter(ruleHasActiveSurcharge);
  if(!active.length)return {...original,extensionStatus:'unmodified',additionalCostEur:0};
  if(pricing.type!=='rules'||!rules.length||!session.startAt||!session.timeZone)
    return {complete:false,reason:'after_minutes_missing_rule_or_time_context',offerId:offer?.id||null};
  const occupied=Number(session.durationMinutes);
  if(!Number.isFinite(occupied)||occupied<0||occupied>24*60*7)
    return {complete:false,reason:'after_minutes_invalid_or_unsupported_duration',offerId:offer?.id||null};
  const baseStart=new Date(session.startAt);
  if(Number.isNaN(baseStart.getTime()))
    return {complete:false,reason:'after_minutes_invalid_start_date',offerId:offer?.id||null};
  let uncapped=0,allDayCapped=0;const windowGroups=new Map();
  const counts={chargedMinutes:0,nightBilledMinutes:0,dayBilledMinutes:0,ruleSegments:0};
  let lastRule=null;
  for(let i=0;i<occupied-1e-9;i+=1){
    const slice=Math.min(1,occupied-i),at=new Date(baseStart.getTime()+(i+slice/2)*60000);
    const match=engine.matchingRuleDetailed(pricing,at,session.timeZone,session);
    if(match.unknown||!match.rule)
      return {complete:false,reason:'after_minutes_missing_applicable_time_rule',offerId:offer?.id||null,
        at:at.toISOString(),ruleReason:match.reason||null};
    const rule=match.rule;
    if(lastRule!==rule){counts.ruleSegments++;lastRule=rule;}
    const rate=Number(rule.afterMinutesRate||0);
    if(!strictFinite(rule.afterMinutesRate)&&rule.afterMinutesRate!=null)
      return {complete:false,reason:'after_minutes_invalid_rate'};
    if(!Number.isFinite(rate)||rate<0)
      return {complete:false,reason:'after_minutes_invalid_rate'};
    if(rate===0)continue;
    const threshold=Number(rule.afterMinutesThreshold);
    if(!strictFinite(rule.afterMinutesThreshold)||threshold<0)
      return {complete:false,reason:'after_minutes_invalid_threshold'};
    const currency=String(rule.currency||offer.currency||'').toUpperCase();
    if(currency!=='EUR')return {complete:false,reason:'after_minutes_currency_requires_validation'};
    const billable=Math.max(0,i+slice-Math.max(i,threshold));
    if(billable<=0)continue;
    counts.chargedMinutes+=billable;
    const cost=billable*rate,cap=Number(rule.afterMinutesCap||0);
    if(!Number.isFinite(cap)||cap<0)return {complete:false,reason:'after_minutes_invalid_cap'};
    if(cap===0){uncapped+=cost;continue;}
    if(isAllDayCap(rule)){
      allDayCapped+=cost;
      continue;
    }
    if(offer?.id==='sigeif-7-22'&&cap===4&&
      rule.afterMinutesCapStart==='20:00'&&rule.afterMinutesCapEnd==='08:00'&&rate===0.05&&threshold===180){
      const minute=minOfDay(at,session.timeZone),isNight=minute>=1200||minute<480;
      if(!isNight){uncapped+=cost;counts.dayBilledMinutes+=billable;continue;}
      const key=nightKey(at,session.timeZone,minute);
      windowGroups.set(key,(windowGroups.get(key)||0)+cost);
      counts.nightBilledMinutes+=billable;
      continue;
    }
    return {complete:false,reason:'after_minutes_cap_window_requires_source_confirmation',
      offerId:offer?.id||null};
  }
  const allDayCap=active.length===1&&Number(active[0].afterMinutesCap||0)>0&&isAllDayCap(active[0])
    ?Number(active[0].afterMinutesCap):null;
  if(allDayCapped>0&&allDayCap===null)
    return {complete:false,reason:'after_minutes_mixed_all_day_caps_require_review'};
  const nightCost=[...windowGroups.values()].reduce((a,v)=>a+Math.min(v,4),0);
  const additionalCost=money(uncapped+(allDayCap!=null?Math.min(allDayCapped,allDayCap):allDayCapped)+nightCost);
  return{
    ...original,totalEur:money(original.totalEur+additionalCost),
    extensionStatus:'candidate_computed_not_production_validated',
    additionalCostEur:additionalCost,
    components:{...original.components,afterMinutesCandidate:{
      costEur:additionalCost,chargedMinutes:money(counts.chargedMinutes),
      uncappedCostEur:money(uncapped),allDayCappedCostEur:money(allDayCapped),
      nightCappedCostEur:money(nightCost),nightSessionCounts:windowGroups.size,
      ...counts,sourceContract:offer?.id==='sigeif-7-22'
        ?'SIGEIF_OFFICIAL_GUIDE_2025_20_TO_08_NIGHT_FEE_CAP'
        :'legacy_source_fee_pending_independent_provenance_review',
      referenceUrl:offer?.id==='sigeif-7-22'
        ?'https://www.sigeif.fr/sites/default/files/2025-10/GUIDE%20D%27UTILISATION%20IRVE%202025%20OCTOBRE_0.pdf'
        :null
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
  // An unsupported operator-specific night cap fails closed, unlike the official SIGEIF scheme.
  check('unsupported_overnight_cap_fails_closed',{afterMinutesRate:0.05,afterMinutesThreshold:180,
    afterMinutesCap:4,afterMinutesCapStart:'20:00',afterMinutesCapEnd:'08:00'},300,null);
  // SIGEIF 2025 guide: cap applies to night parking-fee portion ONLY.
  function sigeifNight(name,startAt,duration,expected){
    const offer={id:'sigeif-7-22',currency:'EUR',pricing:{type:'rules',rules:[{
      scope:'allDay',pricePerKwh:0,afterMinutesRate:0.05,afterMinutesThreshold:180,
      afterMinutesCap:4,afterMinutesCapStart:'20:00',afterMinutesCapEnd:'08:00'}]}};
    const res=evaluateCandidate(engine,offer,{energyKwh:0,chargingMinutes:0,
      durationMinutes:duration,startAt,timeZone:'Europe/Paris'});
    checks.push({name,expected,result:res.complete?res.additionalCostEur:res.reason,
      pass:res.complete&&Math.abs(res.additionalCostEur-expected)<1e-7});
  }
  sigeifNight('sigeif_day_uncapped','2026-10-10T09:00:00+02:00',300,6);
  sigeifNight('sigeif_night_capped','2026-10-10T17:00:00+02:00',600,4);
  sigeifNight('sigeif_day_night_split','2026-10-10T14:00:00+02:00',600,13);
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
