'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const [prod,input,phase,output,responsePath]=process.argv.slice(2);
const data=JSON.parse(fs.readFileSync(input,'utf8'));
const context={TCCV9OfferEngine:require(path.join(prod,'runtime-owned/assets/v9/offer-engine.js'))};
for(const name of ['pricing-engine','session-engine'])vm.runInNewContext(fs.readFileSync(path.join(prod,'runtime-overrides/assets/v9/'+name+'.js'),'utf8'),context);
const engine=context.TCCV9SessionEngine,planner=require(path.join(prod,'runtime-owned/assets/v9/session-planner-engine.js')),bridge=require(path.join(prod,'v9-production-shell/bridge.js'));
const scope=['nationalStationKey','nationalEvseKey','nationalConnectorKey','source_id','tariff_signature'];
const stable=v=>v!==null&&typeof v==='object'?(Array.isArray(v)?v.map(stable):Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])]))):v;
const key=r=>JSON.stringify(stable(r));
const responses=new Map(),requests=[],coverage={},seen=new Set(),paired=new Map();
if(phase==='verify')for(const row of JSON.parse(fs.readFileSync(responsePath,'utf8'))){const k=key(row.request);assert.ok(!responses.has(k));responses.set(k,row.response);}
const opts={g66DiagnosticEnabled:true,g66PlannerProtocol:true,g66SessionZeroTemporalProof:true,g66NationalSha256:data.lineage.nationalCanonicalSha256,g66GateCodeSha:data.lineage.codeSha,
 g66QuoteTransport:r=>{if(phase==='collect'){requests.push(r);return null;}const k=key(r),q=responses.get(k);assert.ok(q,'missing exact runtime planner response');seen.add(k);return q;}};
const requestFor=(st,row,s)=>({country:'FR',channel:'Electroverse',...Object.fromEntries(scope.map(k=>[k,row.binding[k]])),session:{protocol:'planner-v1',startAt:s.startAt,timeZone:s.timeZone||s.stationTimeZone,energy:s.energyKwh.toFixed(6),durationMinutes:s.durationMinutes.toFixed(6),chargingMinutes:s.chargingMinutes.toFixed(6),postChargeMinutes:s.postChargeMinutes.toFixed(6),includeCongestionFees:s.includeCongestionFees,chargeTimeline:s.chargeTimeline.map(x=>({offsetMinutes:x.offsetMinutes.toFixed(6),durationMinutes:x.durationMinutes.toFixed(6),energyKwh:x.energyKwh.toFixed(6)}))}});
const extract=(e,id)=>[e.best,...e.alternatives,...e.incomplete].filter(Boolean).find(x=>x.offerId===id);
const money=x=>Math.round((x+Number.EPSILON)*1e6)/1e6;
function station(row){
 const r=row.binding,c=row.connector,e=row.evse,s=row.station;
 return{id:s.id,name:s.name,countryCode:'FR',timeZone:'Europe/Paris',latitude:s.latitude,longitude:s.longitude,physicalOperator:s.cpoId,
  evses:[{id:e.id,evseId:e.officialEvseId,connectors:[{id:c.id,kind:c.kind,powerKw:c.powerKw,plugName:r.national_plug}]}],
  offers:[{id:'g66-'+r.national_id,provider:'Electroverse',kind:'roaming',currency:'EUR',countries:['FR'],evseIds:[e.id],connectorIds:[c.id],connectorKinds:[c.kind],pricing:{type:'rules',rules:[]},metadata:{g66Dynamic:true,...Object.fromEntries(scope.map(k=>[k,r[k]]))}}]};
}
const cases=[
 {name:'day',startAt:'2026-11-26T15:18:21Z',startSoc:22,targetSoc:83,postChargeMinutes:6,consumptionKwhPer100Km:17.4},
 {name:'night',startAt:'2026-11-26T22:51:09Z',startSoc:47,targetSoc:92,postChargeMinutes:17,consumptionKwhPer100Km:21.2},
 {name:'window_22',startAt:'2026-11-26T20:50:00Z',startSoc:22,targetSoc:83,postChargeMinutes:6,consumptionKwhPer100Km:17.4},
 {name:'midnight',startAt:'2026-11-26T22:50:00Z',startSoc:22,targetSoc:83,postChargeMinutes:6,consumptionKwhPer100Km:17.4},
 {name:'spring_dst',startAt:'2026-03-29T00:50:00Z',startSoc:22,targetSoc:83,postChargeMinutes:6,consumptionKwhPer100Km:17.4},
 {name:'autumn_dst',startAt:'2026-10-25T00:50:00Z',startSoc:22,targetSoc:83,postChargeMinutes:6,consumptionKwhPer100Km:17.4}
];
for(const fixture of cases)for(const fees of [true,false]){
 const label=fixture.name+(fees?'_included':'_excluded'),stats={priced:0,unpriced:0,steps:0,multiStep:0,fractional:0,invalidPlanner:0,reasons:{},weighted:0,weightedPriced:0};coverage[label]=stats;
 for(const row of data.rows){
  const st=station(row);
  const plan=planner.planStation(st,{...fixture,timeZone:'Europe/Paris',batteryCapacityKwh:75,vehicleMaxAcKw:11,vehicleMaxDcKw:250,chargeEfficiency:.92,includeCongestionFees:fees});
  const s=plan.effectiveSession;
  assert.ok(s.chargeTimeline.length>0&&s.chargingMinutes>0);stats.steps+=s.chargeTimeline.length;
  if(s.chargeTimeline.length>1)stats.multiStep++;
  if(Math.abs(s.chargingMinutes*60-Math.round(s.chargingMinutes*60))>1e-8)stats.fractional++;
  stats.weighted+=row.weight;
  const ev=engine.evaluateStation(st,s,opts);
  if(phase==='collect')continue;
  const item=extract(ev,st.offers[0].id);assert.ok(item);
  const expected=responses.get(key(requestFor(st,row,s)));assert.ok(expected);
  assert.equal(item.total,expected.estimateEur===null?null:Number(expected.estimateEur),'runtime amount must match exact gate');
  if(expected.estimateEur===null)assert.equal(item.result.reason,expected.reason||expected.decision);
  if(item.result.reason==='g66_planner_session_invalid'){stats.invalidPlanner++;throw Error('Valid planner transport rejected '+row.binding.national_id);}
  if(ev.best){
   assert.equal(ev.best.result.diagnosticOnly,true);assert.equal(ev.best.connectorId,row.connector.id);
   assert.equal(ev.best.costPerRecoveredKm,money(ev.best.total/(s.energyKwh/(s.consumptionKwhPer100Km/100))));
   assert.equal(bridge.tariffLaneState(ev,st,'electroverse').status,'priced');stats.priced++;stats.weightedPriced+=row.weight;
   if(!fees){assert.ok(['NO_POSITIVE_TEMPORAL_COMPONENT_IN_ARCHIVED_SIGNATURE','NO_POSITIVE_TEMPORAL_AMOUNT_PROVEN_FOR_EXACT_ARCHIVED_SESSION'].includes(expected.congestionEvidence));if(expected.congestionEvidence==='NO_POSITIVE_TEMPORAL_AMOUNT_PROVEN_FOR_EXACT_ARCHIVED_SESSION')assert.equal(ev.best.result.g66CongestionEvidence,expected.congestionEvidence);assert.equal(ev.best.result.components.chargingTime,0);assert.equal(ev.best.result.components.parkingTime,0);}
  }else{assert.equal(item.total,null);assert.ok(item.result.reason);stats.unpriced++;stats.reasons[item.result.reason]=(stats.reasons[item.result.reason]||0)+1;}
  const pair=fixture.name+'|'+row.binding.national_id;
  if(fees)paired.set(pair,ev.best?.total??null);
  else if(ev.best)assert.equal(ev.best.total,paired.get(pair),'congestion cannot change proven zero temporal amount');
 }
}
if(phase==='collect')fs.writeFileSync(output,JSON.stringify(requests));
else{assert.equal(seen.size,responses.size);assert.equal(seen.size,data.rows.length*cases.length*2);fs.writeFileSync(output,JSON.stringify({coverage,checks:seen.size,scope:'actual planner and session engines in Node; representatives by signature/current/nominal power, no browser'}));}
