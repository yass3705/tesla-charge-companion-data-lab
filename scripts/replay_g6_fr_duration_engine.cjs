'use strict';
const fs=require('node:fs');
const engine=require(process.argv[2]);
const rows=JSON.parse(fs.readFileSync(0,'utf8'));
function offer(rates,id){
  return {id,country:'FR',currency:'EUR',pricing:{type:'rules',rules:[{scope:'allDay',start:'00:00',end:'24:00',currency:'EUR',pricePerKwh:Number(rates.energy),chargePerMinute:Number(rates.time),idlePerMinute:Number(rates.parking),connectionFee:Number(rates.flat),ocpiDurationBands:(rates.bands||[]).map(([k,lo,hi,v])=>[k,lo,hi,Number(v)])}]}};
}
const results=rows.map(x=>{
  const f=x.fixture,s={energyKwh:Number(f.energy),durationMinutes:Number(f.duration),chargingMinutes:Number(f.charging),postChargeMinutes:Number(f.parking),startAt:f.startAt,timeZone:'Europe/Paris'};
  const r=engine.evaluateOffer(offer(x.rates,x.signature),s);
  const segments=r.components?.segmentedPricing?.segments;
  const components=Array.isArray(segments)?segments.map(y=>y.components):[r.components];
  const sum=k=>Math.round(components.reduce((v,c)=>v+(c?.[k]??0),0)*1e6)/1e6;
  return {signature:x.signature,scenario:f.id,complete:r.complete===true,currency:r.currency??null,total:r.totalEur??null,energy:sum('energy'),time:sum('chargingTime'),parking:sum('parkingTime'),flat:sum('connectionFee'),reason:r.reason??null,components:r.components??null};
});
const example=offer({energy:'0.45',flat:'1.00',time:'0.03',parking:'0.04'},'guard');
const s={energyKwh:10,durationMinutes:45,chargingMinutes:30,postChargeMinutes:15,startAt:'2026-11-25T10:00:00Z',timeZone:'Europe/Paris'};
const bad=structuredClone(example);bad.pricing.rules[0].unverifiedSurchargeEur=1;
const guards={missing_charge:engine.evaluateOffer(example,{...s,chargingMinutes:null}).complete===false,missing_parking:engine.evaluateOffer(example,{...s,postChargeMinutes:null}).complete===false,negative_time:engine.evaluateOffer(example,{...s,chargingMinutes:-1}).complete===false,unknown_fee:engine.evaluateOffer(bad,s).complete===false,missing_duration:engine.evaluateOffer(example,{...s,durationMinutes:null}).complete===false};
process.stdout.write(JSON.stringify({results,guards}));
