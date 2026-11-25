'use strict';
const fs=require('node:fs'),engine=require(process.argv[2]);
const req=JSON.parse(fs.readFileSync(0,'utf8'));
function quote(q,component=q.component){
  const f=q.fixture,rule={scope:'allDay',start:'00:00',end:'24:00',currency:'EUR',pricePerKwh:0,chargePerMinute:0,idlePerMinute:0,connectionFee:0,afterMinutesRate:Number(q.rate),afterMinutesThreshold:q.threshold/60};
  if(component)rule.afterMinutesComponent=component;
  const r=engine.evaluateOffer({id:q.signature,country:'FR',currency:'EUR',pricing:{type:'rules',rules:[rule]}},{energyKwh:Number(f.energy),durationMinutes:Number(f.duration),chargingMinutes:Number(f.charging),postChargeMinutes:Number(f.parking),startAt:f.startAt,timeZone:'Europe/Paris'});
  return {complete:r.complete===true,total:r.totalEur??null,reason:r.reason??null};
}
const guard=req.length>0&&quote(req[0],'').complete===false;
process.stdout.write(JSON.stringify({results:req.map(q=>quote(q)),missingComponentGuard:guard}));
