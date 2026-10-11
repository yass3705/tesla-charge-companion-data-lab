#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),crypto=require('node:crypto'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const enginePath=process.argv[2],sourceDirectPath=process.argv[3],sourceEmspPath=process.argv[4];
if(!enginePath||!sourceDirectPath||!sourceEmspPath)throw Error('Usage: node audit_after_minutes_live_verified_20261011.cjs engine.js direct.json emsp.json');
const engine=require(path.resolve(enginePath));
const direct=JSON.parse(fs.readFileSync(sourceDirectPath,'utf8'));
const emsp=JSON.parse(fs.readFileSync(sourceEmspPath,'utf8'));
const m=new Map([...direct.directOffers||[],...direct.subscriptionOffers||[],...emsp.directOffers||[],...emsp.subscriptionOffers||[]].map(o=>[o.id,o]));
const ids=['pluginn-direct','sigeif-24','sigeif-50-100','sigeif-7-22','pluginn-chargepass-basic','pluginn-chargepass-intense'];
const fees={ 'pluginn-direct':{kwh:.59,r:.3,at:60}, 'sigeif-24':{kwh:.45,r:.2,at:120},'sigeif-50-100':{kwh:.49,r:.3,at:60},
 'sigeif-7-22':{kwh:.39,r:.05,at:180,cap:4},'pluginn-chargepass-basic':{kwh:.46,r:.3,at:60},'pluginn-chargepass-intense':{kwh:.39,r:.3,at:60}};
const sample={energyKwh:20,durationMinutes:90,chargingMinutes:75,totalChargingMinutes:75,postChargeMinutes:15,
 powerKw:22,arrivalSoc:30,targetSoc:75,vehicleSoc:30,includeCongestionFees:true,startAt:'2026-10-11T14:00:00+02:00',timeZone:'Europe/Paris'};
const rows=[],failures=[];
for(const id of ids){
 const offer=m.get(id),f=fees[id];
 if(!offer){failures.push(id+':not_in_stable_catalogue');continue}
 const rules=offer.pricing?.rules||[];
 const active=rules.filter(r=>Number(r.afterMinutesRate)>0);
 if(active.length!==1){failures.push(id+':unexpected_active_rules_'+active.length);continue}
 const rule=active[0];
 const expected={kw:f.kwh,rate:f.r,threshold:f.at};
 if(Number(rule.pricePerKwh)!==f.kwh||Number(rule.afterMinutesRate)!==f.r||Number(rule.afterMinutesThreshold)!==f.at||
  rule.afterMinutesComponent!=='CONNECTED_TIME'||!rule.afterMinutesProvenance)
  failures.push(id+':unexpected_current_source_rule');
 if(f.cap&&!(rule.afterMinutesCap===4&&rule.afterMinutesCapMode==='night_window_local_per_night'&&rule.afterMinutesCapStart==='20:00'&&rule.afterMinutesCapEnd==='08:00'))
  failures.push(id+':invalid_current_night_cap_contract');
 const spans=[f.at,f.at+1,f.at+30];
 for(const minutes of spans){
  const session={...sample,durationMinutes:minutes,chargingMinutes:Math.min(minutes,75),totalChargingMinutes:Math.min(minutes,75),postChargeMinutes:Math.max(0,minutes-75)};
  const result=engine.evaluateOffer(offer,session);
  const expectedFee=(minutes-f.at)*f.r; // test day sessions only; SIGEIF capped scenario separately
  const expectedTotal=Number((20*f.kwh+expectedFee).toFixed(6));
  const ok=result.complete&&Math.abs(result.totalEur-expectedTotal)<=0.0002;
  if(!ok)failures.push(id+':'+minutes+':'+JSON.stringify({expectedTotal,result:result.totalEur,reason:result.reason}));
  rows.push({id,minutes,expectedTotal,result:result.complete?result.totalEur:null,reason:result.reason||null,pass:!!ok,rule});
 }
}
const nightOffer=m.get('sigeif-7-22');
for(const t of [
 {name:'night_only_4e_cap',at:'2026-10-11T20:30:00+02:00',minutes:300,expected:.39*20+4},
 {name:'day_only_uncapped',at:'2026-10-11T12:00:00+02:00',minutes:300,expected:.39*20+6},
 {name:'day_then_night',at:'2026-10-11T18:00:00+02:00',minutes:300,expected:.39*20+4}
]){
 const result=engine.evaluateOffer(nightOffer,{...sample,startAt:t.at,durationMinutes:t.minutes,chargingMinutes:75,totalChargingMinutes:75,postChargeMinutes:t.minutes-75});
 const pass=result.complete&&Math.abs(result.totalEur-t.expected)<.0002;
 if(!pass)failures.push(t.name+':'+JSON.stringify({expected:t.expected,actual:result.totalEur,reason:result.reason}));
 rows.push({id:'sigeif-7-22',scenario:t.name,expectedTotal:t.expected,result:result.complete?result.totalEur:null,reason:result.reason||null,pass});
}
const result={schemaVersion:1,generatedAt:new Date().toISOString(),
 currentEngineSha256:crypto.createHash('sha256').update(fs.readFileSync(enginePath)).digest('hex'),
 liveSources:["tesla-charge-companion-stable/main/v9-production-runtime/data/v9/france-direct-offers.json",
 "tesla-charge-companion-stable/main/v9-production-runtime/data/v9/france-emsp-offers.json"],
 ruleIds:ids,passing:rows.filter(x=>x.pass).length,total:rows.length,failed:failures.length,failures,rows,
 mode:'LIVE_CATALOGUE_STRICT_REGRESSION_NO_DEPLOY'};
fs.mkdirSync(path.join(root,'reports/tariff-scenarios'),{recursive:true});
fs.writeFileSync(path.join(root,'reports/tariff-scenarios/current-v9-after-minutes-official-six-2026-10-11.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({result:failures.length?'FAIL':'PASS',tests:rows.length,passing:result.passing,failures}));
if(failures.length)process.exitCode=1;
