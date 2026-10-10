#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const engine=require(path.resolve(process.argv[2]||'production/runtime-overrides/assets/v9/pricing-engine.js'));
const proof=JSON.parse(fs.readFileSync('reports/uk/connected-kerb-midhope-verified-2026-10-10.json','utf8'));
const p=proof.pricing, sockets=proof.verifiedExactSockets, passed=[],blockers=[];
const near=(a,b)=>Math.abs(a-b)<1e-5;
const money=v=>Math.round(v*1e6)/1e6;
function test(name,fn){fn();passed.push(name);}
function london(t){return new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/London',hourCycle:'h23'}).format(new Date(t));}
function paris(t){return new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Paris',hourCycle:'h23'}).format(new Date(t));}
const window={scope:'timeWindow',start:'08:30',end:'18:00',daysOfWeek:[1,2,3,4,5,6]};
const fee=p.parkingGbpPerStarted30MinutesSource/30;
const offer=s=>({id:'ck:'+s.evseId,currency:'GBP',metadata:{timeZone:'Europe/London'},pricing:{type:'component_groups',componentGroups:[
 {kind:'ENERGY',rules:[{scope:'allDay',pricePerKwh:p.energyGbpPerKwhSource}]},
 {kind:'PARKING_CHARGING',rules:[{...window,chargePerMinute:fee,chargingTimeStepSeconds:1800}]},
 {kind:'PARKING_IDLE',rules:[{...window,idlePerMinute:fee,parkingTimeStepSeconds:1800}]},
 {kind:'IDLE_SUPPLEMENT',rules:[{scope:'allDay',idlePerMinute:p.idleSupplementGbpPerMinute}]}
]}});
function calc(startAt,durationMinutes,chargingMinutes,energyKwh,postChargeMinutes=0){
 return engine.evaluateOffer(offer(sockets[0]),{startAt,durationMinutes,chargingMinutes,energyKwh,postChargeMinutes});
}
function check(name,start,minutes,charging,kwh,idle,expected){
 const r=calc(start,minutes,charging,kwh,idle);
 test(name,()=>{assert.equal(r.complete,true);assert.ok(near(r.totalEur,expected),JSON.stringify({name,r,expected}));});
 return r;
}
test('exact_four_public_socket_identity',()=>{
 assert.equal(sockets.length,4);
 assert.equal(new Set(sockets.map(x=>x.evseId)).size,4);
 assert.equal(new Set(sockets.map(x=>x.connectorId)).size,4);
 assert.ok(sockets.every(x=>x.qrCode && x.appSocketId && x.appTariffId));
});
test('VAT_and_deposit',()=>{
 assert.equal(p.includesVat,true);
 assert.equal(p.guestPreAuthorizationGbpNotFee??p.guestPreAuthorizationCountedAsSessionCost,false);
 assert.equal(p.guestPreAuthorizationGbp,25);
 assert.equal(money(.80004*2),1.60008);
});
test('summer_winter_timezone_conversions',()=>{
 assert.equal(london('2026-10-12T07:30:00Z'),'08:30');
 assert.equal(paris('2026-10-12T07:30:00Z'),'09:30');
 assert.equal(london('2027-01-11T08:30:00Z'),'08:30');
 assert.equal(paris('2027-01-11T08:30:00Z'),'09:30');
});
check('weekday_charging_60','2026-10-12T09:00:00Z',60,60,10,0,money(10*.39996+2*.80004));
check('weekday_charging_15_rounds_30','2026-10-12T09:00:00Z',15,15,2,0,money(2*.39996+.80004));
check('sunday_free_parking','2026-10-11T09:00:00Z',60,60,10,0,money(10*.39996));
check('sunday_idle_fee_independent','2026-10-11T09:00:00Z',20,0,0,20,.2);
check('winter_local_start','2027-01-11T08:30:00Z',30,30,5,0,money(5*.39996+.80004));
check('charging_phase_no_duplicate_fee','2026-10-12T09:00:00Z',30,30,0,0,.80004);
check('idle_phase_parking_plus_idle_fee','2026-10-12T09:00:00Z',30,0,0,30,1.10004);
test('four_sockets_equal_simple_price',()=>{
 for(const s of sockets){
  const r=engine.evaluateOffer(offer(s),{startAt:'2026-10-12T09:00:00Z',durationMinutes:30,chargingMinutes:30,energyKwh:5});
  assert.equal(r.complete,true);
  assert.ok(near(r.totalEur,money(5*.39996+.80004)));
 }
});
const crossings=[
 {name:'entry_boundary_0830',at:'2026-10-12T07:20:00Z',length:30,kwh:5,
  expected:money(5*.39996+.80004)},
 {name:'exit_boundary_1800',at:'2026-10-12T16:30:00Z',length:90,kwh:9,
  expected:money(9*.39996+.80004)}
];
for(const x of crossings){
 const r=calc(x.at,x.length,x.length,x.kwh);
 if(r.complete && near(r.totalEur,x.expected))passed.push(x.name);
 else blockers.push({name:x.name,expected:x.expected,actual:r.totalEur,engineComplete:r.complete,
  cause:'production component_groups selects fee window at session start; crossing not segmented'});
}
blockers.push(
 {name:'rounding_across_charging_idle_phase_boundary',cause:'operator billing or receipt required'},
 {name:'winter_source_schedule_confirmed_against_app',cause:'one summer UTC capture does not prove winter clock policy'},
 {name:'public_V9_pricing_deployment',cause:'candidate not activated; no production integration check'});
const result={generatedAt:new Date().toISOString(),source:'first party Connected Kerb user screenshots + original guest raw source',
 engine:'yass3705/tesla-charge-companion-production/runtime-overrides/assets/v9/pricing-engine.js',
 verifiedSocketCount:sockets.length,passedCount:passed.length,passed,blockers,
 activationReady:blockers.length===0,status:blockers.length?'blocked_before_publishing_prices':'tested_and_ready'};
fs.mkdirSync('reports/uk',{recursive:true});
fs.writeFileSync('reports/uk/midhope-runtime-test-result-2026-10-10.json',JSON.stringify(result,null,2)+'\n');
console.log('MIDHOPE_RUNTIME_QA='+JSON.stringify({passed:result.passedCount,blockers,activationReady:result.activationReady}));
