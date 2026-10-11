#!/usr/bin/env node
'use strict';
// Read-only audit against one immutable stable V9 commit. Never publishes prices.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const files=process.argv.slice(2);
if(files.length!==3)throw Error('Expected engine.js, live-direct.json, live-emsp.json');
const engine=require(path.resolve(files[0]));
const direct=JSON.parse(fs.readFileSync(files[1],'utf8'));
const emsp=JSON.parse(fs.readFileSync(files[2],'utf8'));
const real=[...(direct.directOffers||[]),...(direct.subscriptionOffers||[]),...(emsp.directOffers||[]),...(emsp.subscriptionOffers||[])];
const histPilot=JSON.parse(fs.readFileSync('reports/tariff-scenarios/france-pricing-pilot-latest.json','utf8'));
const readOnly=(offer,session)=>engine.evaluateOffer(offer,session);
const active=o=>(o.pricing?.rules||[]).filter(r=>Number(r.afterMinutesRate)>0);
const selected=real.filter(o=>active(o).length);
const ids=[...new Set(selected.map(o=>o.id))];
const violations=[],checks=[];
const check=(name,actual,expected,ctx={})=>{
  const pass=typeof expected==='number'?typeof actual==='number'&&Number.isFinite(actual)&&Math.abs(actual-expected)<1e-6:actual===expected;
  const result={name,pass,actual,expected,...ctx};checks.push(result);
  if(!pass)violations.push(result);
};
check('six_positive_legacy_offers_are_in_live_data',selected.length,6);
check('no_duplicate_identifiers',ids.length,selected.length);
const durations=[50,60,61,90,120,180,200,300];
const profiles=[];
const at='2026-10-10T10:00:00+02:00',zone='Europe/Paris';
const mkSession=(duration,startAt=at)=>({energyKwh:20,durationMinutes:duration,chargingMinutes:Math.min(40,duration),
 totalChargingMinutes:Math.min(40,duration),startAt,timeZone:zone,powerKw:22,vehicleSoc:50,targetSoc:80,
 includeCongestionFees:true,postChargeMinutes:Math.max(0,duration-Math.min(40,duration))});
const money=n=>Math.round((n+Number.EPSILON)*1e6)/1e6;
function independentFee(rule,session){
 const rate=Number(rule.afterMinutesRate),threshold=Number(rule.afterMinutesThreshold),cap=Number(rule.afterMinutesCap||0);
 const dur=Number(session.durationMinutes),minutes=Math.max(0,dur-threshold);
 if(cap===0)return money(minutes*rate);
 if(rule.afterMinutesCapMode==='whole_session')return money(Math.min(cap,minutes*rate));
 if(rule.afterMinutesCapMode!=='night_window_local_per_night')throw Error('unverified cap mode');
 const start=new Date(session.startAt),fmt=new Intl.DateTimeFormat('en-GB',{timeZone:session.timeZone,hour:'2-digit',minute:'2-digit',hourCycle:'h23'}),
 datefmt=new Intl.DateTimeFormat('en-CA',{timeZone:session.timeZone,year:'numeric',month:'2-digit',day:'2-digit'});
 const partsAt=d=>{const p=fmt.formatToParts(d);return Number(p.find(x=>x.type==='hour').value)*60+Number(p.find(x=>x.type==='minute').value);};
 const dayOf=d=>{const p=datefmt.formatToParts(d);const v=k=>Number(p.find(x=>x.type===k).value);return new Date(Date.UTC(v('year'),v('month')-1,v('day')));};
 const capStart=Number(rule.afterMinutesCapStart.slice(0,2))*60+Number(rule.afterMinutesCapStart.slice(3));
 const capEnd=Number(rule.afterMinutesCapEnd.slice(0,2))*60+Number(rule.afterMinutesCapEnd.slice(3));
 if(capStart<=capEnd)throw Error('unsupported night cap shape');
 let daytime=0;const nightByKey={};
 for(let i=threshold;i<dur;i++){
  const dt=new Date(start.getTime()+(i+0.5)*60000),minute=partsAt(dt);
  const isNight=minute>=capStart||minute<capEnd;
  if(!isNight){daytime+=rate;continue}
  const d=dayOf(dt);
  if(minute<capEnd)d.setUTCDate(d.getUTCDate()-1);
  const key=d.toISOString().slice(0,10);
  nightByKey[key]=(nightByKey[key]||0)+rate;
 }
 return money(daytime+Object.values(nightByKey).reduce((acc,v)=>acc+Math.min(cap,v),0));
}
for(const offer of selected){
 const rules=active(offer),source=offer.source||null;
 check('one_active_rule_'+offer.id,rules.length,1);
 const rule=rules[0];
 check('explicit_connected_time_'+offer.id,rule.afterMinutesComponent,'CONNECTED_TIME');
 check('valid_positive_rate_'+offer.id,Number(rule.afterMinutesRate)>0,true);
 check('threshold_nonnegative_'+offer.id,Number.isFinite(Number(rule.afterMinutesThreshold))&&Number(rule.afterMinutesThreshold)>=0,true);
 if(Number(rule.afterMinutesCap)>0)check('explicit_local_night_mode_'+offer.id,rule.afterMinutesCapMode,'night_window_local_per_night');
 for(const duration of durations){
  const session=mkSession(duration);
  const full=readOnly(offer,session);
  const baseOffer=structuredClone(offer);
  for(const r of baseOffer.pricing.rules)if(Number(r.afterMinutesRate)>0){
   r.afterMinutesRate=0;r.afterMinutesCap=0;
  }
  const base=readOnly(baseOffer,session);
  const expected=independentFee(rule,session);
  check('offer_complete_'+offer.id+'_'+duration,full.complete,true,{reason:full.reason||null});
  check('baseline_complete_'+offer.id+'_'+duration,base.complete,true,{reason:base.reason||null});
  if(full.complete&&base.complete)check('fee_exact_'+offer.id+'_'+duration,money(full.totalEur-base.totalEur),expected);
  profiles.push({offerId:offer.id,duration,expectedExtraEuro:expected,actualExtraEuro:full.complete&&base.complete?money(full.totalEur-base.totalEur):null,
   complete:full.complete===true,reason:full.reason||null});
 }
 if(Number(rule.afterMinutesCap)>0){
  for(const [key,startAt,duration] of [['night_crossing','2026-10-10T18:00:00+02:00',600],
   ['two_nights','2026-10-10T18:00:00+02:00',3000]]){
   const session=mkSession(duration,startAt),res=readOnly(offer,session);
   const baseOffer=structuredClone(offer);for(const r of baseOffer.pricing.rules)r.afterMinutesRate=0;
   const base=readOnly(baseOffer,session);
   const expected=independentFee(rule,session);
   check(key+'_complete_'+offer.id,res.complete,true,{reason:res.reason||null});
   check(key+'_base_complete_'+offer.id,base.complete,true);
   if(res.complete&&base.complete)check(key+'_fee_'+offer.id,money(res.totalEur-base.totalEur),expected);
  }
 }
}
// Fail-closed contract must not compute an incomplete price.
const template=selected.find(o=>Number(active(o)[0]?.afterMinutesCap||0)===0);
if(template){
 const session=mkSession(120);
 const broken=structuredClone(template);delete broken.pricing.rules[0].afterMinutesComponent;
 const result=readOnly(broken,session);
 check('unknown_time_dimension_fail_closed',result.complete,false,{reason:result.reason||null});
 const withCap=structuredClone(template);withCap.pricing.rules[0].afterMinutesCap=5;
 withCap.pricing.rules[0].afterMinutesCapMode='unspecified';
 const bad=readOnly(withCap,session);
 check('unverified_cap_mode_fail_closed',bad.complete,false,{reason:bad.reason||null});
}
const historical=histPilot.unmodeledExamples||[];
const byProvider={};
for(const ex of historical){const p=ex.provider||'UNKNOWN';byProvider[p]=(byProvider[p]||0)+1;}
const srcObj={
 generatedAt:new Date().toISOString(),referenceEngineRepo:'yass3705/tesla-charge-companion-stable',
 referenceStableCommit:process.env.TCC_STABLE_REF||null,readOnly:true,
 engineSha256:crypto.createHash('sha256').update(fs.readFileSync(files[0])).digest('hex'),
 baselineReportAt:histPilot.generatedAt,
 historicalUnmodeledOffers:historical.length,historicalUnmodeledProviders:byProvider,
 livePositiveRateOffers:selected.length,livePositiveRateOfferIds:ids,scenarios:profiles.length,
 checks:checks.length,passed:checks.filter(x=>x.pass).length,failed:violations.length,
 positiveRateSourceRuleDetails:selected.map(x=>({id:x.id,provider:x.provider,source:x.source,
  rule:active(x).map(r=>({rate:r.afterMinutesRate,threshold:r.afterMinutesThreshold,component:r.afterMinutesComponent,
    cap:r.afterMinutesCap,capMode:r.afterMinutesCapMode||null,capStart:r.afterMinutesCapStart||null,capEnd:r.afterMinutesCapEnd||null}))})),
 observations:profiles,failures:violations.slice(0,30),
 note:'Historical 84 suspicious offer samples are not necessarily positive rate. Dedicated fixture audit required for the 78 Electra eMSP samples. This audit checks current V9 live direct/subscription offers only; no production changes.'};
const dst='reports/tariff-scenarios/live-v9-after-minutes-2026-10-11.json';
fs.writeFileSync(dst,JSON.stringify(srcObj,null,2)+'\n');
console.log(JSON.stringify({audit:violations.length?'FAIL':'PASS',stable:srcObj.referenceStableCommit,live:srcObj.livePositiveRateOffers,
 historic:srcObj.historicalUnmodeledOffers,checks:checks.length,failed:violations.length,failedExamples:violations.slice(0,7)}));
if(violations.length)process.exitCode=1;
