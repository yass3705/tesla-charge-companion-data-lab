'use strict';
const fs=require('node:fs');
const engine=require(process.argv[2]);
const rows=JSON.parse(fs.readFileSync(0,'utf8'));
function offer(rates,id){
  return {id,country:'FR',currency:'EUR',pricing:{type:'rules',rules:[{scope:'allDay',start:'00:00',end:'24:00',currency:'EUR',pricePerKwh:Number(rates.energy),connectionFee:Number(rates.flat)}]}};
}
const results=rows.map(x=>{
  const f=x.fixture,s={energyKwh:Number(f.energy),durationMinutes:f.duration,chargingMinutes:f.charging,postChargeMinutes:f.parking,startAt:f.startAt,timeZone:'Europe/Paris'};
  const r=engine.evaluateOffer(offer(x.rates,x.signature),s);
  const segments=r.components?.segmentedPricing?.segments;
  const components=Array.isArray(segments)?segments.map(y=>y.components):[r.components];
  const sum=k=>components.reduce((v,c)=>v+(c?.[k]??0),0);
  return {signature:x.signature,scenario:f.id,complete:r.complete===true,currency:r.currency??null,total:r.totalEur??null,energy:Math.round(sum('energy')*1e6)/1e6,flat:Math.round(sum('connectionFee')*1e6)/1e6,reason:r.reason??null,components:r.components??null};
});
const example=offer({energy:'0.45',flat:'1.00'},'guard');
const s={energyKwh:10,durationMinutes:30,chargingMinutes:30,postChargeMinutes:0,startAt:'2026-11-25T10:00:00Z',timeZone:'Europe/Paris'};
const bad=structuredClone(example);bad.pricing.rules[0].unverifiedSurchargeEur=1;
const currency=structuredClone(example);currency.currency='ZZZ';
const guards={missing_energy:engine.evaluateOffer(example,{...s,energyKwh:null}).complete===false,negative_energy:engine.evaluateOffer(example,{...s,energyKwh:-1}).complete===false,unknown_fee:engine.evaluateOffer(bad,s).complete===false,wrong_currency:engine.evaluateOffer(currency,s).complete===false};
process.stdout.write(JSON.stringify({results,guards}));
