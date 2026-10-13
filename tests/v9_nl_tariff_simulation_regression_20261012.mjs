import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const adapter=require(process.argv[2]+'/runtime-overrides/assets/v9/adapters/netherlands-dotnl.js');
const engine=require(process.argv[2]+'/runtime-overrides/assets/v9/pricing-engine.js');
const template=(price,steps={})=>['timeWindow','00:00','24:00','kwh','EUR',price,0,0,0,0,0,[0,1,2,3,4,5,6],[],steps];
function offer(rules){
 const s=adapter.normalizeRow(['NL:T:1','T','',52,5,'T',1,null,[['conf','T2','AC',22,1,rules]],'2026-10-11T10:32:00Z','IN_SERVICE']);
 assert.equal(s.offers.length,1);return s.offers[0];
}
const basic=offer([template(.29)]);
for(const scenario of [
 {startAt:'2026-10-12T09:30:00+02:00',energyKwh:10,durationMinutes:50,chargingMinutes:50},
 {startAt:'2026-10-11T20:30:00+02:00',energyKwh:20,durationMinutes:130,chargingMinutes:90}
]){
 const quote=engine.evaluateOffer(basic,{...scenario,timeZone:'Europe/Amsterdam'});
 assert.equal(quote.complete,true);
 assert.ok(Math.abs(quote.totalEur-scenario.energyKwh*.29)<1e-5);
}
const rounded=offer([template(.29,{energyStepWh:1000})]);
assert.ok(Math.abs(engine.evaluateOffer(rounded,{energyKwh:1.2,durationMinutes:15,chargingMinutes:15,startAt:'2026-10-11T12:00:00+02:00',timeZone:'Europe/Amsterdam'}).totalEur-.58)<1e-6);
console.log('NL pinned V9 direct charge smoke: PASS');
