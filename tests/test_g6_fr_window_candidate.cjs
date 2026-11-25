'use strict';
const assert=require('node:assert/strict'),engine=require('../migration/v9/g6-candidate/pricing-engine.cjs');
const rule=(scope,start,end,rate,fee=0)=>({scope,start,end,currency:'EUR',pricePerKwh:0,chargePerMinute:rate,idlePerMinute:0,connectionFee:fee});
function quote(rules,startAt,duration=60,pricing={},charging=duration){
 return engine.evaluateOffer({currency:'EUR',country:'FR',pricing:{type:'rules',rules,...pricing}},{startAt,durationMinutes:duration,chargingMinutes:charging,postChargeMinutes:duration-charging,energyKwh:0,timeZone:'Europe/Paris'});
}
function exact(q,expected){assert.equal(q.complete,true,JSON.stringify(q));assert.ok(Math.abs(q.totalEur-expected)<1e-6,JSON.stringify(q));}
const day=rule('allDay','00:00','24:00',0.06,1),night=rule('timeWindow','23:00','07:00',0.01,2);
exact(quote([day,night],'2026-11-25T21:45:00Z'),2.35);
exact(quote([day,night],'2026-11-25T21:45:00Z',60,{priceSelectionBasis:'session_start_local_time'}),4.6);
exact(quote([day,night],'2026-11-26T05:45:00Z'),4.85);
exact(quote([day,night],'2026-11-25T22:00:00Z'),2.6);
exact(quote([day,night],'2026-11-25T21:00:00Z'),4.6);
const spring=rule('timeWindow','03:00','04:00',0.01,2);
exact(quote([day,spring],'2026-03-29T00:30:00Z'),3.1);
const fall=rule('timeWindow','02:15','02:45',0.01,2);
exact(quote([day,fall],'2026-10-25T00:00:00Z',120),5.2);
const overlap=rule('timeWindow','23:15','23:45',0.2);
assert.equal(quote([day,night,overlap],'2026-11-25T21:45:00Z').complete,false);
assert.equal(quote([day,night],'2026-11-25T21:45:00Z',10081).complete,false);
console.log('9 candidate boundary tests passed');
