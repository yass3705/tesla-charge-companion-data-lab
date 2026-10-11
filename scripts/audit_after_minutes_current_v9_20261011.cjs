#!/usr/bin/env node
'use strict';
// CURRENT V9 engine audit against the same real offer evidence as the Oct 10 review.
// No source tariff mutation, no inferred fee component, no publication.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const enginePath=path.resolve(process.argv[2]||'/tmp/tcc-v9-current-pricing-engine.js');
const engine=require(enginePath);
const currentSha=crypto.createHash('sha256').update(fs.readFileSync(enginePath)).digest('hex');
const fixturePaths=[
'reports/tariff-scenarios/france-real-offer-fixtures.json',
'reports/tariff-scenarios/france-runtime-offer-fixtures.json'
];
const records=fixturePaths.flatMap(p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8')).map(x=>({...x,fixture:p})));
const active=records.filter(x=>(x.offer?.pricing?.rules||[]).some(r=>Number(r?.afterMinutesRate)>0));
const profile={energyKwh:25,durationMinutes:90,chargingMinutes:75,totalChargingMinutes:75,
 powerKw:22,arrivalSoc:30,targetSoc:85,vehicleSoc:30,includeCongestionFees:true,
 postChargeMinutes:15,startAt:'2026-10-11T13:00:00+02:00',timeZone:'Europe/Paris'};
const durations=[50,60,61,90,120,180,300];
const byReason={},byProvider={},issues=[],individual=[],complete={};
let counted=0,unmodeled=0,unknownSemantic=0,missingCapSemantic=0,completeCases=0,incompleteCases=0,exceptions=0;
const strict=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
for(const item of active){
 const offer=item.offer;
 const rules=(offer.pricing?.rules||[]).filter(r=>Number(r.afterMinutesRate)>0);
 const semantic=rules.every(r=>['TIME','PARKING_TIME','CONNECTED_TIME'].includes(r.afterMinutesComponent));
 const capSpec=rules.every(r=>!(strict(r.afterMinutesCap)&&Number(r.afterMinutesCap)>0)||
 ['whole_session','night_window_local_per_night'].includes(r.afterMinutesCapMode));
 if(!semantic)unknownSemantic++;
 if(!capSpec)missingCapSemantic++;
 const provider=item.provider||offer.provider||'unknown';
 const totals=[],reasons=new Set();
 for(const durationMinutes of durations){
  const chargingMinutes=Math.min(75,durationMinutes);
  const session={...profile,durationMinutes,chargingMinutes,totalChargingMinutes:chargingMinutes,
   postChargeMinutes:durationMinutes-chargingMinutes};
  let res;try{res=engine.evaluateOffer(offer,session)}catch(e){exceptions++;res={complete:false,reason:'exception:'+String(e.message).slice(0,70)}}
  const final=!!res.complete&&Number.isFinite(Number(res.totalEur));
  if(final)completeCases++;
  else{incompleteCases++;const why=res.reason||'unexplained_incomplete';byReason[why]=(byReason[why]||0)+1;reasons.add(why);}
  totals.push({minutes:durationMinutes,complete:final,totalEur:final?res.totalEur:null,reason:final?null:res.reason||null,afterMinutes:res.components?.afterMinutes||null});
 }
 byProvider[provider]=(byProvider[provider]||0)+1;
 if(individual.length<110)individual.push({id:offer.id,provider,fixture:item.fixture,
  ruleDetails:rules.map(r=>({rate:r.afterMinutesRate,threshold:r.afterMinutesThreshold,component:r.afterMinutesComponent??null,cap:r.afterMinutesCap??null,
   capMode:r.afterMinutesCapMode??null,capStart:r.afterMinutesCapStart??null,capEnd:r.afterMinutesCapEnd??null})),
  semanticValidated:semantic,capModeValidated:capSpec,cases:totals});
 counted++;
}
const checkCases=[
 {name:'missing_component_must_fail',rules:[{scope:'allDay',pricePerKwh:0.4,afterMinutesRate:.3,afterMinutesThreshold:60}],minutes:90,charging:90,expectedReason:'after_minutes_component_unverified'},
 {name:'connected_after_60',rules:[{scope:'allDay',pricePerKwh:.4,afterMinutesRate:.3,afterMinutesThreshold:60,afterMinutesComponent:'CONNECTED_TIME'}],minutes:90,charging:90,expected:19},
 {name:'threshold_equal_no_extra',rules:[{scope:'allDay',pricePerKwh:.4,afterMinutesRate:.3,afterMinutesThreshold:60,afterMinutesComponent:'CONNECTED_TIME'}],minutes:60,charging:60,expected:10},
 {name:'time_only_after_60',rules:[{scope:'allDay',pricePerKwh:.4,afterMinutesRate:.3,afterMinutesThreshold:60,afterMinutesComponent:'TIME'}],minutes:90,charging:75,expected:14.5},
 {name:'parking_only_after_60',rules:[{scope:'allDay',pricePerKwh:.4,afterMinutesRate:.3,afterMinutesThreshold:60,afterMinutesComponent:'PARKING_TIME'}],minutes:90,charging:45,expected:19},
 {name:'whole_session_cap10',rules:[{scope:'allDay',currency:'EUR',pricePerKwh:.4,afterMinutesRate:.3,afterMinutesThreshold:60,afterMinutesComponent:'CONNECTED_TIME',afterMinutesCap:10,afterMinutesCapMode:'whole_session',afterMinutesCapStart:'00:00',afterMinutesCapEnd:'24:00'}],minutes:300,charging:300,expected:20},
 {name:'unverified_cap_window_fails',rules:[{scope:'allDay',currency:'EUR',pricePerKwh:.4,afterMinutesRate:.05,afterMinutesThreshold:180,afterMinutesComponent:'CONNECTED_TIME',afterMinutesCap:4,afterMinutesCapStart:'20:00',afterMinutesCapEnd:'08:00'}],minutes:300,charging:300,expectedReason:'after_minutes_cap_window_requires_source_confirmation'},
 {name:'verified_night_cap',rules:[{scope:'allDay',currency:'EUR',pricePerKwh:.4,afterMinutesRate:.05,afterMinutesThreshold:180,afterMinutesComponent:'CONNECTED_TIME',afterMinutesCap:4,afterMinutesCapMode:'night_window_local_per_night',afterMinutesCapStart:'20:00',afterMinutesCapEnd:'08:00'}],minutes:300,charging:300,startAt:'2026-10-11T20:30:00+02:00',expected:14},
 {name:'negative_cap_fails',rules:[{scope:'allDay',pricePerKwh:.4,afterMinutesRate:.3,afterMinutesThreshold:60,afterMinutesComponent:'CONNECTED_TIME',afterMinutesCap:-4}],minutes:90,charging:90,expectedReason:'after_minutes_invalid_cap_value'}
];
const tests=[];
for(const t of checkCases){
 const session={...profile,durationMinutes:t.minutes,chargingMinutes:t.charging,totalChargingMinutes:t.charging,
 postChargeMinutes:Math.max(0,t.minutes-t.charging),startAt:t.startAt||profile.startAt};
 const result=engine.evaluateOffer({id:'audit:'+t.name,currency:'EUR',pricing:{type:'rules',rules:t.rules}},session);
 const pass=t.expectedReason?result.complete===false&&result.reason===t.expectedReason:
 result.complete===true&&Math.abs(Number(result.totalEur)-t.expected)<1e-6;
 tests.push({name:t.name,pass,expected:t.expected??t.expectedReason,actual:result.complete?result.totalEur:null,
  reason:result.reason||null});
}
const summary={schemaVersion:1,generatedAt:new Date().toISOString(),pricingEngineSha256:currentSha,
 engineOrigin:process.env.CURRENT_ENGINE_ORIGIN||'not declared',fixtures:fixturePaths,
 fixtureTotal:records.length,activeOffers:active.length,byProvider,offersWithoutValidatedComponent:unknownSemantic,
 offersWithoutValidatedCapMode:missingCapSemantic,casesTested:counted*durations.length,completeCases,
 incompleteCases,exceptions,byReason,syntheticPassed:tests.filter(t=>t.pass).length,syntheticTotal:tests.length,
 mode:'READ_ONLY_CURRENT_ENGINE_UNMODELED_FIELDS_AUDIT',productionUpdated:false,
 caveat:'Pricing missing source-confirmed fee component or cap semantics is deliberately incalculable, never zero.'};
const output={summary,tests,details:individual};
if(!tests.every(t=>t.pass))throw Error('Synthetic afterMinutes regression failures '+JSON.stringify(tests.filter(t=>!t.pass)));
fs.mkdirSync(path.join(root,'reports/tariff-scenarios'),{recursive:true});
fs.writeFileSync(path.join(root,'reports/tariff-scenarios/current-v9-after-minutes-audit-2026-10-11.json'),JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify({status:'PASS',summary,tests}));
