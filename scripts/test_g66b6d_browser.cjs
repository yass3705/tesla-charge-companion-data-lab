'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const [prod,input,responsePath,out]=process.argv.slice(2);
const data=JSON.parse(fs.readFileSync(input));
const adapter=require(path.join(prod,'runtime-owned/assets/v9/adapters/canonical-v9.js'));
const fragmentMap=new Map();
for(const file of Object.values(data.archives)){
 for(const st of adapter.toFragments(JSON.parse(fs.readFileSync(file)))){
  if(!data.mixedStationIds.includes(st.canonicalId))continue;
  const rows=fragmentMap.get(st.canonicalId)||[];rows.push(st);fragmentMap.set(st.canonicalId,rows);
 }
}
const scope=['nationalStationKey','nationalEvseKey','nationalConnectorKey','source_id','tariff_signature'];
const stations=[];
for(const row of data.mixed){
 const r=row.binding,c=row.connector,e=row.evse,s=row.station;
 const offers=(fragmentMap.get(s.id)||[]).flatMap(f=>f.offers).filter(o=>o.evseIds.includes(e.id)&&(!o.connectorIds?.length||o.connectorIds.includes(c.id)));
 if(!offers.length)continue;
 const dynamic={id:'g66-'+r.national_id,provider:'Electroverse',kind:'roaming',currency:'EUR',countries:['FR'],evseIds:[e.id],connectorIds:[c.id],connectorKinds:[c.kind],pricing:{type:'rules',rules:[]},metadata:{g66Dynamic:true,...Object.fromEntries(scope.map(k=>[k,r[k]]))}};
 stations.push({id:s.id,canonicalId:s.id,countryCode:'FR',timeZone:'Europe/Paris',name:s.name,latitude:s.latitude,longitude:s.longitude,physicalOperator:{id:s.cpoId,name:s.cpoId},evses:[{id:e.id,officialEvseId:e.officialEvseId,connectors:[{id:c.id,kind:c.kind,powerKw:c.powerKw,plugName:r.national_plug}]}],offers:offers.concat(dynamic)});
}
assert.equal(stations.length,349);
const responses=JSON.parse(fs.readFileSync(responsePath));assert.equal(responses.length,1047);
const base={startAt:'2026-11-26T15:18:21Z',timeZone:'Europe/Paris',startSoc:22,targetSoc:83,batteryCapacityKwh:75,vehicleMaxAcKw:11,vehicleMaxDcKw:250,chargeEfficiency:.92,consumptionKwhPer100Km:17.4,postChargeMinutes:6,includeCongestionFees:true};
const sessions={included:base,excluded:{...base,includeCongestionFees:false},changed:{...base,startAt:'2026-11-26T22:51:09Z',startSoc:47,targetSoc:92,postChargeMinutes:17,consumptionKwhPer100Km:21.2,includeCongestionFees:false}};
const source=fs.readFileSync(path.join(prod,'v9-production-shell/bridge.js'),'utf8');
assert.ok(source.includes('return{congestionLaneKey,'));
// Expose only the existing private renderCandidate function in this test
// copy; no function body, production file or browser pricing logic changed.
const testBridge=source.replace('return{congestionLaneKey,','return{renderCandidate,congestionLaneKey,');
const assets=['runtime-owned/assets/v9/offer-engine.js','runtime-overrides/assets/v9/pricing-engine.js','runtime-overrides/assets/v9/session-engine.js','runtime-owned/assets/v9/charge-model-engine.js','runtime-owned/assets/v9/session-planner-engine.js','runtime-owned/assets/v9/station-score-engine.js'];
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const report={kind:'real-archive browser component recipe',fullShell:false,liveService:false,physicalPlugFilter:'NOT_IMPLEMENTED_IN_BRIDGE',tariffChannelFilter:'NOT_IMPLEMENTED_IN_BRIDGE',geocodingAndMap:'NOT_TESTED',serverPagination:'NOT_TESTED',scenarios:[]};
 try{
 for(const [label,width,height] of [['desktop',1280,900],['mobile',390,844]]){
  const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1,timezoneId:'UTC'});
  const errors=[],external=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/*',route=>{external.push(route.request().url());return route.abort();});
  await page.setContent('<!doctype html><html lang="fr"><head><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow"><style>body{box-sizing:border-box;margin:0;padding:12px;background:#101820;color:#f5f5f5;font:16px system-ui}main{max-width:760px;margin:auto}.box{box-sizing:border-box;padding:12px;border:1px solid #34404c;border-radius:8px}.small{font-size:13px;overflow-wrap:anywhere}input,select{box-sizing:border-box;max-width:100%}a{color:#9dc8ee}</style></head><body><main><div><label>Opérateur <select id="simOperatorFilter"><option value="">Tous</option></select></label></div><div id="routeStatus"></div><div id="results"></div></main></body></html>');
  await page.evaluate(()=>{window.__TCC_V9_SHELL__={ready:true};});
  for(const a of assets)await page.addScriptTag({path:path.join(prod,a)});
  await page.addScriptTag({content:testBridge});
  const obs=await page.evaluate(({stations,responses,sessions,lineage})=>{
   const ui=window.TCCV9ProductionShell;
   const stable=v=>v!==null&&typeof v==='object'?(Array.isArray(v)?v.map(stable):Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])]))):v;
   const key=r=>JSON.stringify(stable(r));
   const assert=(cond,msg)=>{if(!cond)throw Error(msg);};
   const map=new Map(responses.map(r=>[key(r.request),r.response])),seen=new Set(),missing=new Set();
   assert(map.size===1047,'duplicate replay requests');
   const opts={g66DiagnosticEnabled:true,g66PlannerProtocol:true,g66SessionZeroTemporalProof:true,g66NationalSha256:lineage.nationalCanonicalSha256,g66GateCodeSha:lineage.codeSha,g66QuoteTransport:r=>{const k=key(r);if(!map.has(k)){missing.add(k);return null;}seen.add(k);return map.get(k);}};
   ui.installV9MobileLayout(window);ui.installPowerTypeFilter(window);ui.bindCongestionToggles(window);
   const area={displayFxRates:{EUR:1},selectedSubscriptions:[]};
   const variants={},summary={},triple=[],refused=[],congestion=[];
   for(const [name,s] of Object.entries(sessions)){
    const vv=stations.flatMap(st=>ui.variantsByPower(window,[{station:st,distanceKm:1+Math.abs(st.latitude-48.8)+Math.abs(st.longitude-2.3),distanceEstimated:true}],s,[],opts));
    assert(vv.length===349,'lost exact connector');
    variants[name]=vv;
    const rows=ui.stationCards(vv,[]),counters={priced:0,refused:0,triple:0};
    for(const v of vv){
     const lanes=['direct','electra','electroverse'].map(l=>ui.tariffLaneState(v.evaluation,v.station,l));
     if(lanes[2].status==='priced')counters.priced++;else {counters.refused++;refused.push(v);}
     if(lanes.every(l=>l.status==='priced')){counters.triple++;triple.push(v);}
     if(lanes.some(l=>l.item?.congestion?.available&&Number.isFinite(l.item?.congestion?.totalWithoutCongestion)))congestion.push(v);
    }
    for(const mode of ['price','costPerKm']){
     const ranked=ui.rankRows(rows.slice(),mode,rows.length);
     let last=-Infinity,unknown=false;
     for(const c of ranked){if(c.total===null){unknown=true;continue;}assert(!unknown,'unpriced before priced');const v=mode==='price'?c.total:Math.min(...c.rankingChoices.map(x=>x.costPerKm??Infinity));assert(v>=last,'ranking order');last=v;}
    }
    summary[name]=counters;
   }
   assert(missing.size===0&&seen.size===1047,'exact transport replay mismatch '+missing.size+' / '+seen.size);
   assert(Object.values(summary).reduce((a,v)=>a+v.triple,0)===30,'triple proof mismatch');
   assert(Object.values(summary).reduce((a,v)=>a+v.priced,0)===707,'dynamic prices mismatch');
   assert(Object.values(summary).reduce((a,v)=>a+v.refused,0)===340,'refusals mismatch');
   window.__recipe={ui,area,variants,summary,triple,refused,congestion,render(vv,mode='price'){const rows=ui.stationCards(vv,[]);const ranked=ui.rankRows(rows,mode,rows.length);ui.renderCandidate(window,{...area,stations:ranked,diagnostics:{sourceStationCount:ranked.length},query:{stationOffset:0}},ranked,'Recette archives');return ranked.map(x=>x.station.id);},show(v){const cards=ui.stationCards([v],[]);ui.renderCandidate(window,{...area,stations:cards,diagnostics:{sourceStationCount:1},query:{stationOffset:0}},cards,'Recette archives');return ['direct','electra','electroverse'].map(l=>{const state=ui.tariffLaneState(v.evaluation,v.station,l);return{status:state.status,total:state.item?.total??null};});}};
   return {seen:seen.size,summary,triple:triple.length,refused:refused.length,congestion:congestion.length,physicalKinds:[...new Set(variants.included.map(v=>v.powerLine.kind))],physicalPlugs:[...new Set(stations.flatMap(st=>st.evses.flatMap(e=>e.connectors.map(c=>c.plugName))))]};
  },{stations,responses,sessions,lineage:data.lineage});
  const checkCard=async (which)=>{
   const expected=await page.evaluate(which=>{const h=window.__recipe;return h.show(h[which][0]);},which);
   await page.locator('.v9-power-group summary').first().click();await page.locator('.v9-pdc-detail summary').first().click();
   const dom=await page.locator('.v9-tariff-row').evaluateAll(rows=>rows.map(r=>({label:r.dataset.v9LaneLabel,status:r.dataset.v9TariffState,total:r.hasAttribute('data-v9-effective-total')?Number(r.dataset.v9EffectiveTotal):null,text:r.querySelector('.v9-lane-amount').textContent})));
   assert.deepEqual(dom.map(({status,total})=>({status,total})),expected);
   assert.deepEqual(dom.map(x=>x.label),['Direct','Electra','Electroverse']);
   for(const r of dom){if(r.status==='priced')assert.match(r.text,/Prix calculé/);else {assert.equal(r.total,null);assert.match(r.text,/Tarif incalculable|Prix non disponible/);}}
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,label+' overflow');
   await page.screenshot({path:path.join(out,label+'-'+which+'.png'),fullPage:true});
   return dom;
  };
  const triple=await checkCard('triple'),refused=await checkCard('refused');
  let toggle='NOT_OBSERVED';
  if(obs.congestion){
   await page.evaluate(()=>{const h=window.__recipe;h.show(h.congestion[0]);});
   await page.locator('.v9-power-group summary').first().click();await page.locator('.v9-pdc-detail summary').first().click();
   const button=page.locator('.v9-congestion-toggle').first(),row=button.locator('..');
   const old=await button.getAttribute('aria-pressed');await button.click();assert.notEqual(await button.getAttribute('aria-pressed'),old);await button.click();assert.equal(await button.getAttribute('aria-pressed'),old);toggle='PASS';
  }
  let ranked=await page.evaluate(()=>{const h=window.__recipe;return h.render(h.variants.included,'price');});
  assert.ok(ranked.length>40);assert.equal(await page.locator('.v9-result-card').count(),20);
  assert.deepEqual(await page.locator('.v9-result-card').evaluateAll(x=>x.map(e=>e.dataset.v9StationId)),ranked.slice(0,20));
  await page.locator('.v9-more-stations').click();assert.equal(await page.locator('.v9-result-card').count(),40);
  assert.deepEqual(await page.locator('.v9-result-card').evaluateAll(x=>x.map(e=>e.dataset.v9StationId)),ranked.slice(0,40));
  ranked=await page.evaluate(()=>{const h=window.__recipe;return h.render(h.variants.changed,'costPerKm');});
  assert.deepEqual(await page.locator('.v9-result-card').evaluateAll(x=>x.map(e=>e.dataset.v9StationId)),ranked.slice(0,20));
  await page.locator('#simPowerDc').check();await page.locator('#simMinPowerKw').fill('50');await page.locator('#simMaxPowerKw').fill('350');
  const filtered=await page.evaluate(()=>{const h=window.__recipe,input=h.ui.readInputs(window),vv=h.variants.included.filter(v=>h.ui.variantMatchesFilters(v,input));if(!vv.length||vv.some(v=>v.powerLine.kind!=='DC'||v.powerLine.powerKw<50||v.powerLine.powerKw>350))throw Error('power filter');h.render(vv);return {count:vv.length,input:h.ui.areaFiltersFromInputs(input)};});
  await page.locator('#simPowerDc').uncheck();await page.locator('#simPowerAc').check();await page.locator('#simMinPowerKw').fill('');await page.locator('#simMaxPowerKw').fill('');
  const ac=await page.evaluate(()=>{const h=window.__recipe,input=h.ui.readInputs(window),vv=h.variants.included.filter(v=>h.ui.variantMatchesFilters(v,input));if(!vv.length||vv.some(v=>v.powerLine.kind!=='AC'))throw Error('AC filter');h.render(vv);return vv.length;});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,label+' filter overflow');
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  report.scenarios.push({label,width,height,...obs,tripleDOM:triple,refusedDOM:refused,congestionToggle:toggle,pagination20plus20:'PASS',rankPriceAndCost:'PASS',dcFilter:filtered,acFilter:ac,externalRequests:external.length,overflow:false});
  await page.close();
 }
 }finally{await browser.close();}
 fs.writeFileSync(path.join(out,'browser-observations.json'),JSON.stringify(report));
})().catch(err=>{console.error(err);process.exitCode=1;});
