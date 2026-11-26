'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const [prod,baseline,input,phase,output,responsePath]=process.argv.slice(2);
const data=JSON.parse(fs.readFileSync(input));
const stable=v=>v!==null&&typeof v==='object'?(Array.isArray(v)?v.map(stable):Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])]))):v;
const key=r=>JSON.stringify(stable(r));
const sha=x=>crypto.createHash('sha256').update(key(x)).digest('hex');
function runtime(root){
 const mod=n=>require(path.join(root,'runtime-owned/assets/v9/'+n+'.js'));
 const context={TCCV9OfferEngine:mod('offer-engine')};
 for(const n of ['pricing-engine','session-engine'])vm.runInNewContext(fs.readFileSync(path.join(root,'runtime-overrides/assets/v9/'+n+'.js'),'utf8'),context);
 return{adapter:mod('adapters/canonical-v9'),tesla:require(path.join(root,'runtime-overrides/assets/v9/adapters/tesla-json.js')),pricing:require(path.join(root,'runtime-overrides/assets/v9/pricing-engine.js')),bridge:require(path.join(root,'v9-production-shell/bridge.js')),data:mod('data-engine'),w:{TCCV9SessionPlannerEngine:mod('session-planner-engine'),TCCV9SessionEngine:context.TCCV9SessionEngine,TCCV9StationScoreEngine:mod('station-score-engine')}};
}
const old=runtime(baseline),now=runtime(prod);
const items=e=>[e?.best,...(e?.alternatives||[]),...(e?.incomplete||[])].filter(Boolean);
const cases=[{startAt:'2026-11-26T12:00:00Z',energyKwh:10,chargingMinutes:30,postChargeMinutes:30,durationMinutes:60,connectedMinutes:60,parkingMinutes:30,startSoc:20,targetSoc:85,includeCongestionFees:true},{startAt:'2026-11-26T22:50:00Z',energyKwh:20,chargingMinutes:60,postChargeMinutes:15,durationMinutes:75,connectedMinutes:75,parkingMinutes:15,startSoc:35,targetSoc:90,includeCongestionFees:false},{startAt:'2026-10-25T00:50:00Z',energyKwh:12,chargingMinutes:40,postChargeMinutes:20,durationMinutes:60,connectedMinutes:60,parkingMinutes:20,startSoc:20,targetSoc:80,includeCongestionFees:true}];
const scope=['nationalStationKey','nationalEvseKey','nationalConnectorKey','source_id','tariff_signature'];
const maps={},stats={},fingerprints={};
const fragmentMap=new Map();
for(const [lane,file] of Object.entries(data.archives)){
 const canonical=JSON.parse(fs.readFileSync(file));
 const a=old.adapter.toFragments(canonical),b=now.adapter.toFragments(canonical);
 assert.equal(sha(a),sha(b),lane+' archive adapter parity');
 let count=0,priced=0,unpriced=0,raw=0;const digest=crypto.createHash('sha256');
 for(const st of b){
  raw+=(st.unparsedOffers||[]).length;
  for(const offer of st.offers){
   count++;
   assert.ok(offer.evseIds.every(id=>st.evses.some(e=>e.id===id)));
   for(const f of cases){
    const q=now.pricing.evaluateOffer(offer,{...f,timeZone:'Europe/Paris'}),p=old.pricing.evaluateOffer(offer,{...f,timeZone:'Europe/Paris'});
    assert.equal(key(q),key(p),lane+' actual price regression '+offer.id);
    if(q.complete!==false&&Number.isFinite(q.totalEur))priced++;else unpriced++;
    digest.update(key([offer.id,f.startAt,q]));
   }
  }
  if(data.mixedStationIds.includes(st.canonicalId)){
   const existing=fragmentMap.get(st.canonicalId)||[];
   existing.push(st);fragmentMap.set(st.canonicalId,existing);
  }
 }
 assert.ok(count>0&&priced>0,lane+' actual priced archive required');
 stats[lane]={canonicalOffers:canonical.offers.length,stations:b.length,compiledOffers:count,rawUnresolved:raw,pricedChecks:priced,unpricedChecks:unpriced};
 fingerprints[lane]=digest.digest('hex');
}
const mac=JSON.parse(fs.readFileSync(data.tesla));
const teslaCountries={};
const teslaRows=[];
for(const raw of mac){
 if(!['FR','IT','CH','DE','ES','NL','GB','MA','BE'].includes(raw.countryCode))continue;
 const a=old.tesla.normalizeStation(raw),b=now.tesla.normalizeStation(raw);
 a.offers=old.tesla.provedConfigurationOffers(raw,a);b.offers=now.tesla.provedConfigurationOffers(raw,b);
 assert.equal(key(a),key(b),'Tesla identity/configuration regression');
 assert.ok(b.evses.every(e=>!e.officialEvseId));
 const country=teslaCountries[b.countryCode]||={stations:0,configurations:0,offers:0,pricedChecks:0,unpricedChecks:0};
 country.stations++;country.configurations+=b.evses.length;country.offers+=b.offers.length;
 for(const offer of b.offers)for(const f of cases){
  const q=now.pricing.evaluateOffer(offer,{...f,currency:offer.currency}),p=old.pricing.evaluateOffer(offer,{...f,currency:offer.currency});
  assert.equal(key(q),key(p),'Tesla price regression '+offer.id);
  if(q.complete!==false&&Number.isFinite(q.totalEur))country.pricedChecks++;else country.unpricedChecks++;
 }
 if(b.offers.length)teslaRows.push(b);
}
assert.equal(Object.keys(teslaCountries).length,9);
assert.ok(Object.values(teslaCountries).every(c=>c.pricedChecks>0),'Tesla positive checks nine countries');
const mix=[];
for(const row of data.mixed){
 const r=row.binding,c=row.connector,e=row.evse,s=row.station;
 const oldOffers=fragmentMap.get(s.id)?.flatMap(f=>f.offers)||[];
 const offers=oldOffers.filter(o=>o.evseIds.includes(e.id)&&(!o.connectorIds?.length||o.connectorIds.includes(c.id)));
 if(!offers.length)continue;
 const dynamic={id:'g66-'+r.national_id,provider:'Electroverse',kind:'roaming',currency:'EUR',countries:['FR'],evseIds:[e.id],connectorIds:[c.id],connectorKinds:[c.kind],pricing:{type:'rules',rules:[]},metadata:{g66Dynamic:true,...Object.fromEntries(scope.map(k=>[k,r[k]]))}};
 mix.push({id:s.id,canonicalId:s.id,countryCode:'FR',timeZone:'Europe/Paris',name:s.name,latitude:s.latitude,longitude:s.longitude,physicalOperator:{id:s.cpoId,name:s.cpoId},evses:[{id:e.id,officialEvseId:e.officialEvseId,connectors:[{id:c.id,kind:c.kind,powerKw:c.powerKw,plugName:r.national_plug}]}],offers:offers.concat(dynamic)});
}
assert.ok(mix.length>0,'no actual scoped overlap');
const responses=new Map(),requests=new Map(),seen=new Set(),missing=new Set();
if(phase==='verify')for(const row of JSON.parse(fs.readFileSync(responsePath))){const k=key(row.request);assert.ok(!responses.has(k));responses.set(k,row.response);}
const transport=r=>{const k=key(r);requests.set(k,r);if(phase==='collect')return null;const q=responses.get(k);if(!q){missing.add(k);return null;}seen.add(k);return q;};
const opts={g66DiagnosticEnabled:true,g66PlannerProtocol:true,g66SessionZeroTemporalProof:true,g66NationalSha256:data.lineage.nationalCanonicalSha256,g66GateCodeSha:data.lineage.codeSha,g66QuoteTransport:transport};
const base={startAt:'2026-11-26T15:18:21Z',timeZone:'Europe/Paris',startSoc:22,targetSoc:83,batteryCapacityKwh:75,vehicleMaxAcKw:11,vehicleMaxDcKw:250,chargeEfficiency:.92,consumptionKwhPer100Km:17.4,postChargeMinutes:6,includeCongestionFees:true};
const mixStats={connectors:mix.length,withDirect:0,withElectra:0,withBoth:0,legacyChecks:0,legacyPriced:0,dynamicPriced:0,dynamicRefused:0,threePriced:0,rankingChecks:0};
const lane=o=>o.kind==='direct'?'direct':o.provider==='Electra'?'electra':null;
for(const st of mix){
 const have=new Set(st.offers.map(lane));if(have.has('direct'))mixStats.withDirect++;if(have.has('electra'))mixStats.withElectra++;if(have.has('direct')&&have.has('electra'))mixStats.withBoth++;
}
for(const [name,s] of Object.entries({included:base,excluded:{...base,includeCongestionFees:false},changed:{...base,startAt:'2026-11-26T22:51:09Z',startSoc:47,targetSoc:92,postChargeMinutes:17,consumptionKwhPer100Km:21.2,includeCongestionFees:false}})){
 const cards=[];
 for(const st of mix){
  const row={station:st,distanceKm:1+Math.abs(st.latitude-48.8)+Math.abs(st.longitude-2.3),distanceEstimated:true};
  const v=now.bridge.variantsByPower(now.w,[row],s,[],opts);
  assert.equal(v.length,1);
  if(phase==='collect')continue;
  const legacy={...st,offers:st.offers.filter(o=>!o.metadata?.g66Dynamic)};
  const before=old.bridge.variantsByPower(old.w,[{...row,station:legacy}],s,[]);
  const disabled=now.bridge.variantsByPower(now.w,[{...row,station:legacy}],s,[]);
  assert.equal(key(before),key(disabled),name+' baseline bridge regression');
  const relevant=x=>items(x.evaluation).filter(i=>!String(i.offerId).startsWith('g66-')).sort((a,b)=>a.offerId.localeCompare(b.offerId));
  assert.equal(key(relevant(v[0])),key(relevant(before[0])),name+' multichannel price or reason regression');
  const dynamic=items(v[0].evaluation).find(i=>String(i.offerId).startsWith('g66-'));assert.ok(dynamic);
  mixStats.legacyChecks+=relevant(v[0]).length;
  mixStats.legacyPriced+=relevant(v[0]).filter(i=>Number.isFinite(i.total)).length;
  if(Number.isFinite(dynamic.total)){mixStats.dynamicPriced++;assert.equal(dynamic.result.diagnosticOnly,true);assert.equal(dynamic.result.publicationEligible,false);assert.equal(dynamic.connectorId,st.evses[0].connectors[0].id);}
  else{mixStats.dynamicRefused++;assert.ok(dynamic.result.reason);}
  const c=now.bridge.stationCards(v,[])[0];
  const scoped=v[0].station;
  const lanes=['direct','electra','electroverse'].map(l=>now.bridge.tariffLaneState(v[0].evaluation,scoped,l));
  const totals=lanes.filter(l=>l.status==='priced').map(l=>l.item.total);
  assert.equal(c.total,totals.length?Math.min(...totals):null,'mixed best lane');
  if(totals.length===3)mixStats.threePriced++;
  cards.push(c);
 }
 if(phase==='verify'){
  // Duplicate station IDs in exact connector fixtures are merged only in the
  // genuine station-card builder, never by assigning a neighbouring price.
  const vv=mix.flatMap(st=>now.bridge.variantsByPower(now.w,[{station:st,distanceKm:1+Math.abs(st.latitude-48.8)+Math.abs(st.longitude-2.3),distanceEstimated:true}],s,[],opts));
  const grouped=now.bridge.stationCards(vv,[]);
  assert.equal(grouped.length,new Set(mix.map(st=>st.id)).size);
  for(const mode of ['price','costPerKm']){
   const ranked=now.bridge.rankRows(grouped.slice(),mode,grouped.length);
   assert.deepEqual(ranked.map(c=>c.station.id),now.bridge.rankRows(grouped.slice().reverse(),mode,grouped.length).map(c=>c.station.id));
   let last=-Infinity,unknown=false;
   for(const c of ranked){if(c.total===null){unknown=true;continue;}assert.equal(unknown,false);const v=mode==='price'?c.total:Math.min(...c.rankingChoices.map(x=>x.costPerKm??Infinity));assert.ok(v>=last);last=v;}
   mixStats.rankingChecks+=ranked.length;
  }
 }
}
if(phase==='collect')fs.writeFileSync(output,JSON.stringify([...requests.values()]));
else{
 assert.equal(missing.size,0);assert.equal(seen.size,responses.size);
 assert.ok(mixStats.legacyPriced>0&&mixStats.dynamicPriced>0,'actual multichannel price checks required');
 fs.writeFileSync(output,JSON.stringify({archives:stats,archiveResultSha256:fingerprints,teslaCountries,mixed:mixStats,uniqueRequests:seen.size}));
}
