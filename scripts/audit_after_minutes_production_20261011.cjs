#!/usr/bin/env node
'use strict';
/**
 * Test CURRENT stable V9 pricing engine + official direct offers against actual
 * documented overstay rules. No promotion of unverified eMSP rule meaning.
 * Inputs: engine.js france-direct-offers.json france-emsp-offers.json
 */
const fs=require('node:fs'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const [engineFile,directFile,emspFile]=process.argv.slice(2);
if(!engineFile||!directFile||!emspFile)throw Error('Usage: node scripts/audit_after_minutes_production_20261011.cjs ENGINE DIRECT EMSp');
const engine=require(path.resolve(engineFile));
const direct=JSON.parse(fs.readFileSync(directFile,'utf8')),emsp=JSON.parse(fs.readFileSync(emspFile,'utf8'));
const sourcePlug=JSON.parse(fs.readFileSync(path.join(root,'data/operator_direct/pluginn_fastcharge_official_france.json'),'utf8'));
const sourceSig=JSON.parse(fs.readFileSync(path.join(root,'data/operator_direct/sigeif_official_ile_de_france.json'),'utf8'));
const overlays=[...direct.directOffers||[],...direct.subscriptionOffers||[],...emsp.directOffers||[],...emsp.subscriptionOffers||[]];
const byId=new Map(overlays.map(o=>[o.id,o]));
const officialIds=['pluginn-direct','pluginn-chargepass-basic','pluginn-chargepass-intense','sigeif-7-22','sigeif-24','sigeif-50-100'];
const checks=[];
const session=(duration,startAt='2026-10-11T09:00:00+02:00')=>({startAt,timeZone:'Europe/Paris',
 energyKwh:20,durationMinutes:duration,chargingMinutes:Math.min(45,duration),
 totalChargingMinutes:Math.min(45,duration),arrivalSoc:25,targetSoc:70,powerKw:22});
function addCheck(name,passed,detail=null){
 checks.push({name,pass:passed,detail});
 if(!passed)console.error('FAILED '+name+' '+JSON.stringify(detail||''));
}
function priceCheck(offerId,duration,expected,startAt){
 const offer=byId.get(offerId);
 if(!offer)throw Error('Missing current production offer '+offerId);
 const actual=engine.evaluateOffer(offer,session(duration,startAt));
 addCheck(offerId+' duration='+duration+' start='+(startAt||'daytime'),
   actual.complete===true&&Math.abs(Number(actual.totalEur)-expected)<0.000001,
   {expected,actual:actual.totalEur??null,reason:actual.reason??null,
    afterMinutes:actual.components?.afterMinutes??null});
}
for(const id of officialIds){
 const o=byId.get(id);if(!o)throw Error('Current stable offer is missing '+id);
 const rule=o.pricing?.rules?.find(r=>Number(r.afterMinutesRate)>0);
 addCheck('verified-provenance-and-component:'+id,
  !!rule?.afterMinutesProvenance&&rule?.afterMinutesComponent==='CONNECTED_TIME'&&
  String(rule.currency)==='EUR', {component:rule?.afterMinutesComponent,source:rule?.afterMinutesProvenance});
}
const ps=sourcePlug.fees.overstayOrParkingDuration,ss=sourceSig.operatorDirect;
addCheck('official-pluginn-60min-0.30',ps.thresholdMinutes===60&&ps.eurPerMinuteAfterThreshold===0.3&&ps.doNotModelAsChargeEndedOnly===true);
addCheck('official-sigeif-7-22-night',ss.upTo22Kw.connectionOrParkingFee.freeMinutes===180&&
 ss.upTo22Kw.connectionOrParkingFee.eurPerMinuteAfter===0.05&&
 ss.upTo22Kw.connectionOrParkingFee.nightCapEur===4&&
 ss.upTo22Kw.connectionOrParkingFee.nightWindow==='20:00-08:00');
addCheck('official-sigeif-24',ss.upTo24Kw.connectionOrParkingFee.freeMinutes===120&&
 ss.upTo24Kw.connectionOrParkingFee.eurPerMinuteAfter===0.2&&
 ss.upTo24Kw.connectionOrParkingFee.nightCapEur==null);
addCheck('official-sigeif-50',ss.upTo50Kw.connectionOrParkingFee.freeMinutes===60&&
 ss.upTo50Kw.connectionOrParkingFee.eurPerMinuteAfter===0.3);
priceCheck('pluginn-direct',50,11.8);
priceCheck('pluginn-direct',61,12.1);
priceCheck('pluginn-direct',90,20.8);
priceCheck('pluginn-chargepass-basic',61,9.5);
priceCheck('pluginn-chargepass-intense',61,8.1);
priceCheck('sigeif-24',120,9);
priceCheck('sigeif-24',180,21);
priceCheck('sigeif-50-100',61,10.1);
priceCheck('sigeif-7-22',180,7.8);
priceCheck('sigeif-7-22',200,8.8);
priceCheck('sigeif-7-22',300,13.8,'2026-10-11T09:00:00+02:00');
priceCheck('sigeif-7-22',300,11.8,'2026-10-11T17:00:00+02:00');
priceCheck('sigeif-7-22',300,11.8,'2026-10-11T19:00:00+02:00');
const base=byId.get('sigeif-7-22');
const duplicate=JSON.parse(JSON.stringify(base));
delete duplicate.pricing.rules[0].afterMinutesComponent;
const rejected=engine.evaluateOffer(duplicate,session(300,'2026-10-11T17:00:00+02:00'));
addCheck('unverified-billing-component-fails-closed',rejected.complete===false&&rejected.reason==='after_minutes_component_unverified',{complete:rejected.complete,reason:rejected.reason});
const missingCap=JSON.parse(JSON.stringify(base));delete missingCap.pricing.rules[0].afterMinutesCapMode;
const refused=engine.evaluateOffer(missingCap,session(300,'2026-10-11T17:00:00+02:00'));
addCheck('unverified-night-cap-fails-closed',refused.complete===false&&refused.reason==='after_minutes_cap_window_requires_source_confirmation',{complete:refused.complete,reason:refused.reason});
const sampledFiles=['france-runtime-offer-fixtures.json','france-real-offer-fixtures.json'];
const sampled=[];
for(const name of sampledFiles){
 const file=path.join(root,'reports/tariff-scenarios',name);
 sampled.push(...JSON.parse(fs.readFileSync(file,'utf8')));
}
const affected=sampled.filter(x=>x.offer?.pricing?.type==='rules'&&x.offer.pricing.rules.some(r=>Number(r.afterMinutesRate)>0));
const counts={};
for(const x of affected){
 const kind=x.provider||x.offer.provider||'UNKNOWN';
 counts[kind]=(counts[kind]||0)+1;
}
const missingComponent=affected.filter(x=>x.offer.pricing.rules.some(r=>Number(r.afterMinutesRate)>0&&
 !['CONNECTED_TIME','PARKING_TIME','TIME'].includes(r.afterMinutesComponent)));
const unsafe=[];
for(const x of missingComponent){
 const result=engine.evaluateOffer(x.offer,session(90));
 if(result.complete!==false)unsafe.push({id:x.offer.id,provider:x.provider,totalEur:result.totalEur});
}
addCheck('unproven-legacy-offers-never-become-computed',unsafe.length===0,{unsafeCount:unsafe.length,examples:unsafe.slice(0,10)});
addCheck('review-sampled-84-affected-offers',affected.length===84,{affected:affected.length,missingComponent:missingComponent.length,providers:counts});
const report={
 schemaVersion:1,generatedAt:new Date().toISOString(),scope:'production_engine_stable_pinned_read_only',
 affectedRealOffers:affected.length,providerCounts:counts,
 officialDirectOrMembershipRulesVerified:officialIds,
 sourceProvenance:{pluginn:'data/operator_direct/pluginn_fastcharge_official_france.json#fees',
 sigeif:'data/operator_direct/sigeif_official_ile_de_france.json#operatorDirect'},
 unverifiedSampleOffers:missingComponent.length,unverifiedSampleOffersFailClosed:unsafe.length===0,
 unverifiedSampleExamples:missingComponent.slice(0,8).map(x=>({id:x.offer.id,provider:x.provider})),
 checks,pass:checks.every(x=>x.pass),
 publication:false,
 note:'Demonstrates the CURRENT engine, not the old 2026-10-09 frozen engine. No eMSP component is inferred, and no live runtime files are mutated.'
};
const dest=path.join(root,'reports/tariff-scenarios/after-minutes-production-verification-2026-10-11.json');
fs.writeFileSync(dest,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({result:report.pass?'PASS':'FAIL',checks:checks.length,passed:checks.filter(x=>x.pass).length,
 affected:affected.length,unverified:missingComponent.length,providers:counts,report:path.relative(root,dest)}));
if(!report.pass)process.exitCode=1;
