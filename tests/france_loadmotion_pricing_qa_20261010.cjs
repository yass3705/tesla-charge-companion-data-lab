#!/usr/bin/env node
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const engine=require(process.argv[2]||'/tmp/tcc-v9-pinned-pricing-engine.js');
const file=process.argv[3]||'v9-production-runtime/data/v9/france-loadmotion-offers.json';
const d=JSON.parse(fs.readFileSync(file,'utf8'));
const offers=new Map(d.directOffers.map(x=>[x.id,x]));
const profile={energyKwh:25,durationMinutes:50,chargingMinutes:45,totalChargingMinutes:45,postChargeMinutes:5,
  powerKw:22,arrivalSoc:30,targetSoc:85,vehicleSoc:30,includeCongestionFees:true,
  startAt:'2026-10-10T11:00:00+02:00',postChargeStartAt:'2026-10-10T11:45:00+02:00',timeZone:'Europe/Paris'};
const amounts=new Map([
 ['loadmotion-yes55-profile-21',12.24],
 ['loadmotion-yes55-profile-22',12.24],
 ['loadmotion-yes55-profile-24',15.84],
 ['loadmotion-yes55-profile-25',15.312],
 ['loadmotion-yes55-profile-30',9.3],
]);
const results=[];
for(const [id,expected] of amounts){
 const offer=offers.get(id);assert.ok(offer,id+' missing');
 const windows=offer.pricing.postChargeFee?.exemptLocalWindows||[];
 assert.ok(windows.length,id+' must have postcharge exemption');
 const erroneous=offer.pricing.rules.filter(r=>r.scope==='timeWindow'&&r.pricePerKwh===0&&windows.some(w=>w.start===r.end&&w.end===r.start));
 assert.equal(erroneous.length,0,id+' zero-kWh parking shadow');
 const result=engine.evaluateOffer(offer,profile);
 assert.equal(result.complete,true,id+' incomplete: '+result.reason);
 assert.ok(Math.abs(result.totalEur-expected)<1e-5,id+' expected '+expected+', got '+result.totalEur);
 results.push({id,totalEur:result.totalEur,pass:true});
}
{
 const offer=offers.get('loadmotion-yes55-profile-21');
 const s={...profile,startAt:'2026-10-10T19:13:00+02:00',postChargeStartAt:'2026-10-10T19:58:00+02:00'};
 const x=engine.evaluateOffer(offer,s);
 assert.equal(x.complete,true);
 assert.ok(Math.abs(x.totalEur-12.096)<1e-5,'Crossing YES55 exemption boundary');
 results.push({id:'YES55_19h58_20h03_boundary',totalEur:x.totalEur,pass:true});
}
{
 const id='loadmotion-reveo-11-078560e5',offer=offers.get(id);
 assert.ok(offer);
 const daytime=engine.evaluateOffer(offer,profile);
 assert.equal(daytime.complete,false);
 assert.equal(daytime.reason,'no_matching_time_rule');
 const night=engine.evaluateOffer(offer,{...profile,startAt:'2026-10-10T23:30:00+02:00'});
 assert.equal(night.complete,true);
 assert.ok(Math.abs(night.totalEur-10.0002)<1e-5);
 results.push({id,daytime:'not_applicable',nightTotalEur:night.totalEur,pass:true});
}
console.log('LOADMOTION_PRICE_QA='+JSON.stringify({source:file,checks:results,allPassed:true}));
