'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const [prod,input,phase,output,responsePath]=process.argv.slice(2);
const data=JSON.parse(fs.readFileSync(input,'utf8'));
const mod=n=>require(path.join(prod,'runtime-owned/assets/v9/'+n+'.js'));
const context={TCCV9OfferEngine:mod('offer-engine')};
for(const name of ['pricing-engine','session-engine'])vm.runInNewContext(fs.readFileSync(path.join(prod,'runtime-overrides/assets/v9/'+name+'.js'),'utf8'),context);
const engine=context.TCCV9SessionEngine,planner=mod('session-planner-engine'),score=mod('station-score-engine'),bridge=require(path.join(prod,'v9-production-shell/bridge.js'));
const scope=['nationalStationKey','nationalEvseKey','nationalConnectorKey','source_id','tariff_signature'];
const stable=v=>v!==null&&typeof v==='object'?(Array.isArray(v)?v.map(stable):Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])]))):v;
const key=r=>JSON.stringify(stable(r));
const responses=new Map(),requests=new Map(),seen=new Set(),missing=new Set();
if(phase==='verify')for(const row of JSON.parse(fs.readFileSync(responsePath,'utf8'))){assert.ok(!responses.has(key(row.request)));responses.set(key(row.request),row.response);}
let calls=0;
const quote=r=>{calls++;const k=key(r);requests.set(k,r);if(phase==='collect')return null;const q=responses.get(k);if(!q){missing.add(k);return null;}seen.add(k);return q;};
const transport={enabled:true,nationalCanonicalSha256:data.lineage.nationalCanonicalSha256,gateCodeSha:data.lineage.codeSha,quote};
const opts={g66DiagnosticEnabled:true,g66PlannerProtocol:true,g66SessionZeroTemporalProof:true,g66NationalSha256:transport.nationalCanonicalSha256,g66GateCodeSha:transport.gateCodeSha,g66QuoteTransport:quote};
const w={TCCV9SessionPlannerEngine:planner,TCCV9SessionEngine:engine,TCCV9StationScoreEngine:score,sessionStorage:{getItem:()=> 'FR'},localStorage:{getItem:()=>null}};
const stationMap=new Map();
for(const row of data.rows){
 const r=row.binding,c=row.connector,e=row.evse,s=row.station;
 let st=stationMap.get(s.id);
 if(!st){st={id:s.id,canonicalId:s.id,countryCode:'FR',timeZone:'Europe/Paris',name:s.name,latitude:s.latitude,longitude:s.longitude,physicalOperator:{id:s.cpoId,name:s.cpoId},evses:[],offers:[]};stationMap.set(s.id,st);}
 let ev=st.evses.find(x=>x.id===e.id);
 if(!ev){ev={id:e.id,officialEvseId:e.officialEvseId,evseId:e.officialEvseId,connectors:[]};st.evses.push(ev);}
 assert.ok(!ev.connectors.some(x=>x.id===c.id));
 ev.connectors.push({id:c.id,kind:c.kind,powerKw:c.powerKw,plugName:r.national_plug});
 st.offers.push({id:'g66-'+r.national_id,provider:'Electroverse',kind:'roaming',currency:'EUR',countries:['FR'],evseIds:[e.id],connectorIds:[c.id],connectorKinds:[c.kind],pricing:{type:'rules',rules:[]},metadata:{g66Dynamic:true,...Object.fromEntries(scope.map(k=>[k,r[k]]))}});
}
const stations=[...stationMap.values()];
assert.equal(stations.reduce((n,s)=>n+s.offers.length,0),579);
const byOffer=new Map(stations.flatMap(s=>s.offers.map(o=>[o.id,o])));
const money=x=>Math.round((x+Number.EPSILON)*1e6)/1e6;
const items=e=>[e?.best,...(e?.alternatives||[]),...(e?.incomplete||[])].filter(Boolean);
const lex=(a,b)=>a<b?-1:a>b?1:0;
const tie=(a,b)=>String(a.station.name||'').localeCompare(String(b.station.name||''),'fr')||lex(a.station.id,b.station.id);
const distance=(a,b)=>a.distanceKm-b.distanceKm;
function expectedRank(cards,mode){
 const priced=cards.filter(x=>x.total!==null),unknown=cards.filter(x=>x.total===null).sort((a,b)=>distance(a,b)||tie(a,b));
 if(mode==='price')priced.sort((a,b)=>a.total-b.total||distance(a,b)||tie(a,b));
 else{const cost=x=>Math.min(...x.rankingChoices.map(c=>c.costPerKm??Infinity));priced.sort((a,b)=>cost(a)-cost(b)||a.total-b.total||distance(a,b)||tie(a,b));}
 return priced.concat(unknown).map(x=>x.station.id);
}
function checkCards(cards,variants,tag){
 const ids=cards.map(x=>x.station.id);assert.equal(ids.length,new Set(ids).size,tag+' station duplicates');
 const offered=new Set(),priced=new Set();
 for(const v of variants){
  const evseIds=new Set(v.station.evses.map(e=>e.id)),connectorIds=new Set(v.station.evses.flatMap(e=>e.connectors.map(c=>c.id)));
  for(const x of items(v.evaluation)){
   const o=byOffer.get(x.offerId);assert.ok(o,tag+' unknown offer');assert.ok(evseIds.has(o.evseIds[0])&&connectorIds.has(o.connectorIds[0]),tag+' offer crossed connector');offered.add(x.offerId);
   if(x.total!==null&&x.total!==undefined){assert.equal(x.connectorId,o.connectorIds[0]);assert.equal(x.result.diagnosticOnly,true);assert.equal(x.result.publicationEligible,false);assert.equal(x.costPerRecoveredKm,money(x.total/(v.plan.effectiveSession.energyKwh/(v.plan.effectiveSession.consumptionKwhPer100Km/100))));priced.add(x.offerId);}
  }
 }
 for(const c of cards){
  const vv=variants.filter(v=>v.station.id===c.station.id);
  const values=vv.flatMap(v=>items(v.evaluation)).filter(i=>Number.isFinite(i.total)&&i.result?.complete===true).map(i=>i.total);
  assert.equal(c.total,values.length?Math.min(...values):null,tag+' wrong station minimum');
  assert.equal(bridge.tariffLaneState(c.evaluation,c.station,'direct').status,'missing');
  assert.equal(bridge.tariffLaneState(c.evaluation,c.station,'electra').status,'missing');
  if(c.total!==null)assert.equal(c.bestChoice.lane,'electroverse');
  const actual=new Set(c.station.evses.flatMap(e=>e.connectors.map(x=>x.id)));
  const expected=new Set(vv.flatMap(v=>v.station.evses.flatMap(e=>e.connectors.map(x=>x.id))));
  assert.deepEqual([...actual].sort(),[...expected].sort(),tag+' topology');
 }
 for(const mode of ['price','costPerKm']){
  const expected=expectedRank(cards,mode),ranked=bridge.rankRows(cards.slice(),mode,cards.length);
  assert.deepEqual(ranked.map(c=>c.station.id),expected,tag+' oracle '+mode);
  assert.deepEqual(bridge.rankRows(cards.slice().reverse(),mode,cards.length).map(c=>c.station.id),expected,tag+' order '+mode);
  for(const limit of [20,40,60])assert.deepEqual(bridge.rankRows(cards.slice(),mode,limit).map(c=>c.station.id),expected.slice(0,limit),tag+' prefix '+limit);
 }
 return{stations:cards.length,offers:offered.size,pricedOffers:priced.size,pricedStations:cards.filter(c=>c.total!==null).length,unpricedStations:cards.filter(c=>c.total===null).length};
}
const base={startAt:'2026-11-26T15:18:21Z',timeZone:'Europe/Paris',startSoc:22,targetSoc:83,batteryCapacityKwh:75,vehicleMaxAcKw:11,vehicleMaxDcKw:250,chargeEfficiency:.92,consumptionKwhPer100Km:17.4,postChargeMinutes:6,includeCongestionFees:true};
const directStats={};
const rows=stations.map(s=>({station:s,distanceKm:1+Math.abs(s.latitude-48.8)+Math.abs(s.longitude-2.3),distanceEstimated:true}));
for(const [label,s] of Object.entries({day:base,excluded:{...base,includeCongestionFees:false},changed:{...base,startAt:'2026-11-26T22:51:09Z',startSoc:47,targetSoc:92,postChargeMinutes:17,consumptionKwhPer100Km:21.2,includeCongestionFees:false}})){
 const before=requests.size;const variants=bridge.variantsByPower(w,rows,s,[],opts);
 const cards=bridge.stationCards(variants,[]);
 assert.equal(cards.length,stations.length);assert.equal(requests.size-before,579,label+' exact request count');
 if(phase==='verify'){
  directStats[label]=checkCards(cards,variants,label);
  assert.equal(directStats[label].offers,579);
  for(const [name,filter] of Object.entries({ac:{connectorKinds:['AC']},dc:{connectorKinds:['DC']},power:{minPowerKw:50,maxPowerKw:150}})){
   const vv=variants.filter(v=>bridge.variantMatchesFilters(v,filter));
   const oracle=variants.filter(v=>(!filter.connectorKinds||filter.connectorKinds.includes(v.powerLine.kind))&&(filter.minPowerKw==null||v.powerLine.powerKw>=filter.minPowerKw)&&(filter.maxPowerKw==null||v.powerLine.powerKw<=filter.maxPowerKw));
   assert.deepEqual(vv,oracle);directStats[label][name]=checkCards(bridge.stationCards(vv,[]),vv,label+name);
  }
 }
}
// Exercise the genuine geographic data engine and executeV9 rankedPage, not a
// fabricated list of ranking summaries. Pick a real dense search center.
const km=(a,b)=>{const r=Math.PI/180,d=(b.latitude-a.latitude)*r,e=(b.longitude-a.longitude)*r;return 6371*2*Math.asin(Math.sqrt(Math.sin(d/2)**2+Math.cos(a.latitude*r)*Math.cos(b.latitude*r)*Math.sin(e/2)**2));};
const centers=stations.filter(s=>Number.isFinite(s.latitude)&&Number.isFinite(s.longitude));
const center=centers.map(s=>({s,count:centers.filter(t=>km(s,t)<=99).length})).sort((a,b)=>b.count-a.count||lex(a.s.id,b.s.id))[0];
assert.ok(center.count>20,'need real multi-page search');
w.resolveOrigin=async()=>({lat:center.s.latitude,lon:center.s.longitude,label:'offline real catalogue origin'});
const spatial=mod('runtime-engine').createEngine({registry:{sources:[{id:'g66-offline',countries:['FR'],active:true}]},loaders:{'g66-offline':async()=>stations}});
const cfg={mode:'candidate',engineScopeCountries:['FR'],g66DiagnosticTransport:transport};
const search={originText:'offline real catalogue origin',radiusKm:100,startSoc:22,targetSoc:83,startAt:base.startAt,batteryCapacityKwh:75,vehicleMaxDcKw:250,vehicleMaxAcKw:11,consumptionKwhPer100Km:17.4,postChargeMinutes:6,includeCongestionFees:true,rankingMode:'price'};
const spatialStats={};
async function searchAll(label,input,config=cfg){
 const all=[];let first=await bridge.executeV9(w,spatial,config,input);all.push(...first.rows);
 const summaries=first.area.mapRankingRows;
 for(let offset=160;offset<summaries.length;offset+=160){const p=await bridge.executeV9(w,spatial,config,{...input,stationOffset:offset});all.push(...p.rows);}
 assert.deepEqual(all.map(c=>c.station.id),summaries.map(c=>c.station.id),'global page identity '+label);
 assert.equal(new Set(all.map(c=>c.station.id)).size,all.length);
 assert.equal(first.area.mapStations.length,summaries.length);
 if(phase==='verify'){
  assert.deepEqual(all.map(c=>c.station.id),expectedRank(all,input.rankingMode),label+' price order');
  for(const c of all){
   const sum=summaries.find(s=>s.station.id===c.station.id);assert.equal(c.total,sum.total,label+' cache/full amount');
   assert.ok(c.variants.every(v=>bridge.variantMatchesFilters(v,input)),label+' filter leakage');
  }
  spatialStats[label]={stations:all.length,priced:all.filter(c=>c.total!==null).length,unpriced:all.filter(c=>c.total===null).length,first20:all.slice(0,20).map(c=>c.station.id),next20:all.slice(20,40).map(c=>c.station.id)};
 }
 return all;
}
(async()=>{
 const first=await searchAll('price',search);assert.ok(first.length>20);
 await searchAll('costPerKm',{...search,rankingMode:'costPerKm'});
 await searchAll('ac',{...search,connectorKinds:['AC']});
 await searchAll('dc_range',{...search,connectorKinds:['DC'],minPowerKw:50,maxPowerKw:150});
 const operator=first[0].station.physicalOperator.id;
 const op=await searchAll('operator',{...search,operatorIds:[operator]});assert.ok(op.length&&op.every(c=>c.station.physicalOperator.id===operator));
 const before=calls;await searchAll('changed',{...search,targetSoc:92,startAt:'2026-11-26T22:51:09Z',postChargeMinutes:17,includeCongestionFees:false});assert.ok(calls>before,'changed parameters not recalculated');
 const disabled=await searchAll('disabled',search,{mode:'candidate',engineScopeCountries:['FR']});
 if(phase==='verify')assert.ok(disabled.every(c=>c.total===null),'diagnostic ranking leaked into disabled mode');
 const reenabled=await searchAll('reenabled',search);if(phase==='verify')assert.deepEqual(reenabled.map(c=>[c.station.id,c.total]),first.map(c=>[c.station.id,c.total]));
 if(phase==='collect')fs.writeFileSync(output,JSON.stringify([...requests.values()]));
 else{
  assert.equal(missing.size,0,'missing exact runtime requests');assert.equal(seen.size,responses.size,'unreplayed responses');
  assert.ok(directStats.day.pricedOffers>0&&directStats.day.pricedOffers<579);assert.ok(spatialStats.price.priced>0);
  fs.writeFileSync(output,JSON.stringify({uniqueRequests:seen.size,transportCalls:calls,representativeStations:stations.length,representativeConnectors:579,direct:directStats,spatial:spatialStats,scope:'actual bridge, per-power runtime, spatial query engine, global ranking and 20/40/60 prefixes; DOM and explicit physical plug/channel UI selectors not tested'}));
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
