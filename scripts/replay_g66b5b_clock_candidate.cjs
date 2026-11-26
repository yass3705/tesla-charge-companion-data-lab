'use strict';
// Separate candidate implementation: actual pinned matchingRule/evaluateRule,
// independently intersect charge steps with each selected UTC rule run.
const fs=require('node:fs'),engine=require(process.argv[2]);
const rows=JSON.parse(fs.readFileSync(0,'utf8')),M=60000000;
const us=v=>Math.round(Number(v)*M);
function quote(x){
 const s=x.session,t=us(s.durationMinutes),c=us(s.chargingMinutes),epoch=Date.parse(s.startAt)*1000;
 if(!Number.isSafeInteger(epoch)||!Number.isSafeInteger(t)||t<=0||c<0||c+us(s.postChargeMinutes)!==t)return{signature:x.signature,complete:false};
 const rules=x.rules.map(r=>({...r,pricePerKwh:Number(r.pricePerKwh),chargePerMinute:Number(r.chargePerMinute),idlePerMinute:Number(r.idlePerMinute),connectionFee:Number(r.connectionFee)}));
 const steps=s.chargeTimeline.map((r,i)=>({a:us(r.offsetMinutes),b:i+1<s.chargeTimeline.length?us(s.chargeTimeline[i+1].offsetMinutes):c,e:Number(r.energyKwh)}));
 const spans=[];let a=0;
 while(a<t){
   const b=Math.min(t,a+M-((epoch+a)%M));
   const rule=engine.matchingRule({rules},new Date((epoch+a)/1000).toISOString(),'Europe/Paris');
   if(!rule||b<=a)return{signature:x.signature,complete:false};
   if(spans.length&&spans.at(-1).rule===rule)spans.at(-1).b=b;
   else spans.push({a,b,rule});
   a=b;
 }
 let totals={energy:0,time:0,parking:0,flat:0,total:0};
 for(const {a,b,rule} of spans){
   const energy=steps.reduce((sum,z)=>sum+z.e*Math.max(0,Math.min(b,z.b)-Math.max(a,z.a))/(z.b-z.a),0);
   const charge=Math.max(0,Math.min(c,b)-a)/M,park=Math.max(0,b-Math.max(a,c))/M;
   const r=engine.evaluateRule(rule,{energyKwh:energy,durationMinutes:(b-a)/M,chargingMinutes:charge,postChargeMinutes:park,includeOneTimeFees:a===0});
   if(!r.complete||!Number.isFinite(r.totalEur))return{signature:x.signature,complete:false};
   for(const [k,v] of Object.entries({energy:r.components.energy??0,time:r.components.chargingTime??0,parking:r.components.parkingTime??0,flat:r.components.connectionFee??0,total:r.totalEur}))totals[k]+=Math.round(v*1e6);
 }
 return{signature:x.signature,complete:true,currency:'EUR',...Object.fromEntries(Object.entries(totals).map(([k,v])=>[k,v/1e6]))};
}
process.stdout.write(JSON.stringify(rows.map(quote)));
