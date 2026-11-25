'use strict';
const fs=require('node:fs'),engine=require(process.argv[2]);
const requests=JSON.parse(fs.readFileSync(0,'utf8'));
function offer(x){return {id:x.signature,country:'FR',currency:'EUR',pricing:{type:'rules',rules:x.rules.map(r=>({...r,pricePerKwh:Number(r.pricePerKwh),chargePerMinute:Number(r.chargePerMinute),idlePerMinute:Number(r.idlePerMinute),connectionFee:Number(r.connectionFee)}))}};}
function session(f){return {energyKwh:Number(f.energy),durationMinutes:Number(f.duration),chargingMinutes:Number(f.charging),postChargeMinutes:Number(f.parking),startAt:f.startAt,timeZone:'Europe/Paris'};}
const results=requests.map(x=>{
 const r=engine.evaluateOffer(offer(x),session(x.fixture));
 const ss=r.components?.segmentedPricing?.segments;
 const components=Array.isArray(ss)?ss.map(y=>y.components):[r.components];
 const sum=k=>Math.round(components.reduce((v,c)=>v+(c?.[k]??0),0)*1e6)/1e6;
 return {signature:x.signature,scenario:x.fixture.id,complete:r.complete===true,currency:r.currency??null,total:r.totalEur??null,energy:sum('energy'),time:sum('chargingTime'),parking:sum('parkingTime'),flat:sum('connectionFee'),reason:r.reason??null};
});
const x={signature:'guard',rules:[{scope:'allDay',start:'00:00',end:'24:00',pricePerKwh:0.4,chargePerMinute:0.05,idlePerMinute:0.1,connectionFee:1},{scope:'timeWindow',start:'07:00',end:'23:00',pricePerKwh:0.5,chargePerMinute:0.05,idlePerMinute:0.1,connectionFee:1}]};
const o=offer(x),s={energyKwh:6,durationMinutes:60,chargingMinutes:30,postChargeMinutes:30,startAt:'2026-11-25T21:45:00Z',timeZone:'Europe/Paris'};
const guards={missing_zone:engine.evaluateOffer(o,{...s,timeZone:null}).complete===false,invalid_zone:engine.evaluateOffer(o,{...s,timeZone:'Invalid/Zone'}).complete===false,missing_charge:engine.evaluateOffer(o,{...s,chargingMinutes:null}).complete===false,missing_parking:engine.evaluateOffer(o,{...s,postChargeMinutes:null}).complete===false};
process.stdout.write(JSON.stringify({results,guards}));
