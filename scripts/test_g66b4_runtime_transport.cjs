'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const [prod,input,phase,output,responsePath]=process.argv.slice(2);
const data=JSON.parse(fs.readFileSync(input,'utf8'));
const context={TCCV9OfferEngine:require(path.join(prod,'runtime-owned/assets/v9/offer-engine.js'))};
for(const name of ['pricing-engine','session-engine'])vm.runInNewContext(fs.readFileSync(path.join(prod,'runtime-overrides/assets/v9/'+name+'.js'),'utf8'),context);
const engine=context.TCCV9SessionEngine,bridge=require(path.join(prod,'v9-production-shell/bridge.js'));
const scope=['nationalStationKey','nationalEvseKey','nationalConnectorKey','source_id','tariff_signature'];
const map=new Map(),requests=[],report={},lineage=data.lineage;
const key=r=>JSON.stringify([r.country,r.channel,...scope.map(k=>r[k]),r.session.startAt,r.session.timeZone,r.session.energy,r.session.seconds,r.session.chargeSeconds,r.session.parkSeconds,r.session.includeCongestionFees]);
if(phase==='verify'){
 const values=JSON.parse(fs.readFileSync(responsePath,'utf8'));
 for(const {request,response} of values){const k=key(request);assert.ok(!map.has(k));map.set(k,response);}
}
const options={g66DiagnosticEnabled:true,g66NationalSha256:lineage.nationalCanonicalSha256,g66GateCodeSha:lineage.codeSha,
 g66QuoteTransport:r=>{if(phase==='collect'){requests.push(r);return null;}const q=map.get(key(r));assert.ok(q,'request not replayed exactly');return q;}};
const extract=(e,id)=>[e.best,...e.alternatives,...e.incomplete].filter(Boolean).find(x=>x.offerId===id);
const money=x=>Math.round((x+Number.EPSILON)*1e6)/1e6;
const distance=(a,b)=>{const rad=x=>x*Math.PI/180,dlat=rad(a.latitude-b.latitude),dlon=rad(a.longitude-b.longitude);return 6371*2*Math.asin(Math.min(1,Math.sqrt(Math.sin(dlat/2)**2+Math.cos(rad(a.latitude))*Math.cos(rad(b.latitude))*Math.sin(dlon/2)**2)));};
function make(row){
 const {station,evse,connector,binding}=row;
 const m=Object.fromEntries(scope.map(k=>[k,binding[k]]));
 const offer={id:'g66-'+binding.national_id,provider:'Electroverse',kind:'roaming',currency:'EUR',countries:['FR'],
  evseIds:[evse.id],connectorIds:[connector.id],connectorKinds:[connector.kind],pricing:{type:'rules',rules:[]},metadata:{g66Dynamic:true,...m}};
 return{id:station.id,name:station.name+' | '+connector.id,countryCode:'FR',timeZone:'Europe/Paris',latitude:station.latitude,longitude:station.longitude,physicalOperator:station.cpoId,
  evses:[{id:evse.id,evseId:evse.officialEvseId,connectors:[{id:connector.id,kind:connector.kind,powerKw:connector.powerKw,plugName:binding.national_plug}]}],offers:[offer]};
}
const allowed=new Set(['DIAGNOSTIC_ESTIMATE_AGREEMENT','SEGMENT_ROUNDING_EXPLAINED']);
let checks=0;
for(const [name,s] of Object.entries(data.sessions)){
 const rank=[],stats={priced:0,unpriced:0,zeroKm:0,changedTotal:0},diagnostics={};
 for(const row of data.rows){
  const st=make(row),ev=engine.evaluateStation(st,s,options);
  if(phase==='collect')continue;
  const item=extract(ev,st.offers[0].id);assert.ok(item,'exact offer missing');
  const r={country:'FR',channel:'Electroverse',...Object.fromEntries(scope.map(k=>[k,row.binding[k]])),session:{startAt:s.startAt,timeZone:s.timeZone,energy:s.energyKwh,seconds:Math.round(s.durationMinutes*60),chargeSeconds:Math.round(s.chargingMinutes*60),parkSeconds:Math.round(s.postChargeMinutes*60),includeCongestionFees:s.includeCongestionFees}};
  const q=map.get(key(r));assert.ok(q,'exact session');
  const good=allowed.has(q.decision);
  assert.equal(Boolean(ev.best),good,JSON.stringify({id:row.binding.national_id,q:q.decision,actual:item.result.reason}));
  if(good){
   assert.equal(ev.best.total,Number(q.estimateEur));assert.equal(ev.best.connectorId,row.connector.id);
   assert.equal(ev.best.costPerRecoveredKm,s.energyKwh>0?money(Number(q.estimateEur)/(s.energyKwh/(s.consumptionKwhPer100Km/100))):null);
   assert.equal(ev.best.result.diagnosticOnly,true);stats.priced++;if(ev.best.costPerRecoveredKm===null)stats.zeroKm++;
  }else{assert.equal(item.total,null);assert.ok(item.result.reason);stats.unpriced++;diagnostics[item.result.reason]=(diagnostics[item.result.reason]||0)+1;}
  const lane=bridge.tariffLaneState(ev,st,'electroverse');
  assert.equal(lane.status,good?'priced':'unresolved');
  checks++;
  // Filter on real geography, real national plug, and power using the shell predicate.
  const km=distance({latitude:48.8566,longitude:2.3522},st);
  const c=st.evses[0].connectors[0];
  const variant={station:st,powerLine:{kind:c.kind,powerKw:c.powerKw}};
  if(km<=75&&c.plugName==='CCS'&&bridge.variantMatchesFilters(variant,{connectorKinds:['DC'],minPowerKw:50,maxPowerKw:350})){
   rank.push({station:st,evaluation:ev,total:ev.best?.total??null,costPerKm:ev.best?.costPerRecoveredKm??null,distanceKm:km});
  }
 }
 if(phase==='verify'){
  for(const mode of ['price','costPerKm']){
   const all=bridge.rankRows(rank.slice(),mode,rank.length);
   const rev=bridge.rankRows(rank.slice().reverse(),mode,rank.length);
   assert.deepEqual(all.map(x=>x.station.name),rev.map(x=>x.station.name));
   let previous=-Infinity,unknown=false;
   for(const r of all){const v=mode==='price'?r.total:r.costPerKm;if(v===null){unknown=true;continue;}assert.equal(unknown,false);assert.ok(v>=previous);previous=v;}
   assert.deepEqual(bridge.rankRows(rank.slice(),mode,20).map(x=>x.station.name),all.slice(0,20).map(x=>x.station.name));
   // Existing shell rankRows is used; slicing proves disjoint pages, not browser navigation.
   const pages=[];for(let i=0;i<all.length;i+=20)pages.push(all.slice(i,i+20).map(x=>x.station.name));
   assert.equal(new Set(pages.flat()).size,all.length);
   stats[mode]={filtered:rank.length,priced:rank.filter(x=>x.total!==null).length,pages:pages.length,first:pages[0]||[]};
  }
  report[name]={...stats,diagnostics};
 }
}
if(phase==='collect'){fs.writeFileSync(output,JSON.stringify(requests));}
else{
 assert.equal(map.size,checks);
 const first=make(data.rows[0]),s=Object.values(data.sessions)[0];
 const base=first.offers[0];
 const controls=[
  ['Direct','direct',.4,'FR'],['Electra','roaming',.45,'FR'],['Tesla','direct',.39,'FR'],
  ...['IT','CH','DE','ES','NL','GB','MA','BE'].map(cc=>['Other','direct',.5,cc])];
 let laneChecks=0;
 for(const [provider,kind,rate,cc] of controls){
  const other={...first,countryCode:cc,offers:[{id:'control',provider,kind,currency:'EUR',countries:[cc],pricing:{type:'rules',rules:[{scope:'allDay',pricePerKwh:rate}]}}]};
  assert.equal(JSON.stringify(engine.evaluateStation(other,s)),JSON.stringify(engine.evaluateStation(other,s,options)));laneChecks++;
 }
 const refused=(ss,expected)=>{const x=extract(engine.evaluateStation(first,ss,options),base.id);assert.equal(x.result.reason,expected);assert.equal(x.total,null);};
 refused({...s,includeCongestionFees:false},'CONGESTION_EXCLUSION_NOT_PROVEN');
 refused({...s,chargeTimeline:[{durationMinutes:1,energyKwh:1}]},'g66_charge_timeline_not_supported');
 const old=extract(engine.evaluateStation(first,s),base.id);assert.equal(old.result.reason,'g66_transport_disabled');
 fs.writeFileSync(output,JSON.stringify({checks,coverage:report,laneChecks,guards:3,scope:'actual session and shell functions in Node; controls synthetic; not browser'}));
}
