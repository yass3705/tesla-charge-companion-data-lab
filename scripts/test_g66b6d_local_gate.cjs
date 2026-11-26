'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const [prod,input,responsePath,out,url]=process.argv.slice(2);
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
 let httpRequests=0;const report={kind:'localhost HTTP live existing DynamicPlannerGate and real browser components',fullShell:false,productionService:false,scenarios:[],filtersChanged:false};
 try{
 for(const [label,width,height] of [['desktop',1280,900],['mobile',390,844]]){
  const page=await browser.newPage({viewport:{width,height},timezoneId:'UTC'});const errors=[],external=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/*',route=>{if(route.request().url().startsWith(url+'/'))return route.continue();external.push(route.request().url());return route.abort();});
  await page.goto(url);await page.evaluate(()=>{window.__TCC_V9_SHELL__={ready:true};});
  for(const a of assets)await page.addScriptTag({path:path.join(prod,a)});
  await page.addScriptTag({content:testBridge});
  const obs=await page.evaluate(({stations,responses,base,lineage})=>{
   const ui=window.TCCV9ProductionShell;
   const stable=v=>v!==null&&typeof v==='object'?(Array.isArray(v)?v.map(stable):Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])]))):v;
   const key=r=>JSON.stringify(stable(r));const assert=(c,m)=>{if(!c)throw Error(m);};
   const map=new Map(responses.map(r=>[key(r.request),r.response]));
   const byConnector=new Map(stations.map(s=>[s.evses[0].connectors[0].id,s]));
   const pairs=[];
   for(const {request:q,response:r} of responses){
    if(q.session.includeCongestionFees!==true||r.estimateEur===null||r.estimateEur===undefined)continue;
    const excluded=map.get(key({...q,session:{...q.session,includeCongestionFees:false}}));
    if(!excluded)continue;
    pairs.push({q,r,excluded,station:byConnector.get(q.nationalConnectorKey)});
   }
   const temporal=pairs.find(x=>Number(x.r.components.time)+Number(x.r.components.parking)>0&&x.excluded.estimateEur===null&&x.excluded.congestionEvidence==='TEMPORAL_COMPONENT_NOT_CLASSIFIED_AS_CONGESTION');
   const zero=pairs.find(x=>x.excluded.estimateEur!==null&&x.excluded.congestionEvidence==='NO_POSITIVE_TEMPORAL_AMOUNT_PROVEN_FOR_EXACT_ARCHIVED_SESSION')||pairs.find(x=>x.excluded.estimateEur!==null&&x.excluded.congestionEvidence==='NO_POSITIVE_TEMPORAL_COMPONENT_IN_ARCHIVED_SIGNATURE');
   assert(temporal&&zero,'real included/excluded pair not found');
   ui.installV9MobileLayout(window);ui.bindCongestionToggles(window);
   let count=0;const observations=[];
   const opts={g66DiagnosticEnabled:true,g66PlannerProtocol:true,g66SessionZeroTemporalProof:true,g66NationalSha256:lineage.nationalCanonicalSha256,g66GateCodeSha:lineage.codeSha};
   function run(st,session,mode='normal'){
    let req,answer;
    const v=ui.variantsByPower(window,[{station:st,distanceKm:1+Math.abs(st.latitude-48.8)+Math.abs(st.longitude-2.3),distanceEstimated:true}],session,[],{...opts,g66QuoteTransport:r=>{
     req=r;const sent=mode==='wrongScope'?{...r,source_id:'invalid-test-scope'}:r;
     const xhr=new XMLHttpRequest();xhr.open('POST','/quote',false);xhr.setRequestHeader('Content-Type','application/json');xhr.send(JSON.stringify(sent));count++;
     assert(xhr.status===200,'HTTP '+xhr.status);answer=JSON.parse(xhr.responseText);return answer;
    }})[0];
    assert(req&&answer,'missing actual HTTP response');
    const item=[v.evaluation.best,...v.evaluation.alternatives,...v.evaluation.incomplete].filter(Boolean).find(x=>String(x.offerId).startsWith('g66-'));
    assert(item,'missing Electroverse lane');
    const expected=map.get(key(req));if(mode==='normal'&&expected)assert(key(expected)===key(answer),'prior response mismatch');
    if(mode==='normal'&&answer.estimateEur!=null){assert(item.result.complete===true&&Math.abs(item.total-Number(answer.estimateEur))<.000001,'price mismatch');assert(item.result.diagnosticOnly===true&&item.result.publicationEligible===false,'diagnostic guards');}
    else assert(item.total===null&&item.result.complete===false,'unproved amount displayed');
    const cards=ui.stationCards([v],[]);ui.renderCandidate(window,{displayFxRates:{EUR:1},selectedSubscriptions:[],stations:cards,diagnostics:{sourceStationCount:1},query:{stationOffset:0}},cards,'Recette service local');
    const row=document.querySelector('[data-v9-lane-label="Electroverse"]');assert(row,'lane absent');assert((row.hasAttribute('data-v9-effective-total')?Number(row.dataset.v9EffectiveTotal):null)===item.total,'DOM amount mismatch');
    const state={decision:answer.decision,reason:answer.reason,evidence:answer.congestionEvidence??null,amount:answer.estimateEur??null,time:answer.components?.time??null,parking:answer.components?.parking??null,uiState:row.dataset.v9TariffState,uiReason:item.result.reason??null,known:!!expected,connector:req.nationalConnectorKey};
    observations.push(state);return state;
   }
   const inc=run(temporal.station,base),exc=run(temporal.station,{...base,includeCongestionFees:false});
   assert(inc.known&&exc.known&&inc.amount!==null&&exc.amount===null&&exc.evidence==='TEMPORAL_COMPONENT_NOT_CLASSIFIED_AS_CONGESTION','unclassified fees must not be subtracted');
   const zi=run(zero.station,base),ze=run(zero.station,{...base,includeCongestionFees:false});
   assert(zi.known&&ze.known&&zi.amount!==null&&ze.amount===zi.amount&&Number(ze.time)===0&&Number(ze.parking)===0,'zero temporal proof');
   const novel=run(zero.station,{...base,startAt:'2026-11-26T15:19:21Z'});
   assert(!novel.known&&novel.amount!==null,'new quote required');
   const invalid=run(zero.station,base,'wrongScope');assert(invalid.amount===null&&invalid.uiReason==='g66_response_scope_mismatch','wrong-scope guard');
   // Reuse the production SOC80 fee contract as a labelled UI regression
   // fixture, never as evidence of actual Electroverse congestion pricing.
   const station={id:'fixture-congestion',countryCode:'FR',name:'Fixture de contrôle du bouton existant',physicalOperator:{name:'CPO'},evses:[{id:'fixture-evse',connectors:[{id:'fixture-ccs',kind:'DC',powerKw:150}]}],offers:[{id:'fixture-direct',kind:'direct',provider:'CPO',currency:'EUR',pricing:{type:'component_groups',componentGroups:[{kind:'ENERGY+CONGESTION_TIME',rules:[{scope:'allDay',start:'00:00',end:'24:00',pricePerKwh:.4,congestionTimePerMinute:.2,congestionTimeStepSeconds:300,congestionStartSoc:80,congestionThresholdSource:'default_soc80'}]}]}},{id:'fixture-evr',kind:'roaming',provider:'Electroverse',currency:'EUR',pricing:{type:'rules',rules:[{scope:'allDay',pricePerKwh:.9}]}}]};
   const s={startAt:'2026-10-08T10:00:00Z',startSoc:75,arrivalSoc:75,targetSoc:85,energyKwh:10,durationMinutes:30,chargingMinutes:20,postChargeMinutes:10,chargeTimeline:[{offsetMinutes:0,durationMinutes:20,startSoc:75,endSoc:85,energyKwh:10,powerKw:35}]};
   const evaluated=window.TCCV9SessionEngine.evaluateStation(station,s);
   document.getElementById('results').innerHTML=ui.renderTariffs(evaluated,station,{EUR:1});
   return {count,observations};
  },{stations,responses,base,lineage:data.lineage});
  httpRequests+=obs.count;
  const direct=page.locator('[data-v9-lane-label="Direct"]'),evr=page.locator('[data-v9-lane-label="Electroverse"]'),toggle=direct.locator('.v9-congestion-toggle');
  assert.equal(await toggle.count(),1);assert.equal(Number(await direct.getAttribute('data-v9-effective-total')),8);const before=await evr.getAttribute('data-v9-effective-total');assert.equal(Number(before),9);
  await toggle.click();assert.equal(Number(await direct.getAttribute('data-v9-effective-total')),4);assert.equal(await evr.getAttribute('data-v9-effective-total'),before);
  await page.screenshot({path:path.join(out,label+'-congestion-fixture.png'),fullPage:true});
  await toggle.click();assert.equal(Number(await direct.getAttribute('data-v9-effective-total')),8);assert.equal(await evr.getAttribute('data-v9-effective-total'),before);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  report.scenarios.push({label,...obs,congestionButtonFixture:'PASS',electroversePositiveCongestionExclusion:'NOT_PROVEN_FAIL_CLOSED',externalRequests:external.length,overflow:false});
  await page.close();
 }
 }finally{await browser.close();}
 report.httpRequests=httpRequests;fs.writeFileSync(path.join(out,'local-browser.json'),JSON.stringify(report));
})().catch(err=>{console.error(err);process.exitCode=1;});
