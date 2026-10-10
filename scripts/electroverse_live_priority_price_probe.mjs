/**
 * Read-only official Electroverse app API (GraphQL) inspection of every station
 * in the full-reconciliation high-priority list, plus published S81 discrepancy.
 * No writes to the tariff cache, mapping, or V9 offers.
 */
import fs from 'node:fs/promises';
import {DirectElectroverseClient,PAGED_LOCATION_QUERY} from './lib/electroverse_direct_client.mjs';

const OUT='reports/electroverse/live-priority-price-probe-2026-10-10.json';
const INPUT='reports/electroverse/full-reconciliation/priority-review-evidence.json';
const spec=JSON.parse(await fs.readFile(INPUT,'utf8'));
const norm=s=>String(s??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const targets=new Map();
for(const r of [...(spec.reviewRows||[]),...(spec.rawGroupWarnings||[])]){
 const id=String(r.locPk||'');if(!id)continue;
 let t=targets.get(id);
 if(!t){t={pk:id,stationId:r.stationId||'',name:r.stationName||r.sourceName||'',refs:new Set(),sourcePks:new Set(),reasons:new Set()};targets.set(id,t);}
 if(r.evse||r.reference)t.refs.add(norm(r.evse||r.reference));
 if(r.sourcePk)t.sourcePks.add(String(r.sourcePk));
 for(const e of r.rawSources||[])if(e.pk)t.sourcePks.add(String(e.pk));
 const reasons=(r.reason||'').split('|').filter(Boolean);
 for(const reason of reasons)t.reasons.add(reason);
}
const list=[...targets.values()].sort((a,b)=>a.stationId.localeCompare(b.stationId)||a.pk.localeCompare(b.pk));
if(!list.length||list.length>100)throw Error('unexpected priority target population: '+list.length);
const client=new DirectElectroverseClient();
const results=[],summary={expectedLocations:list.length,complete:0,partial:0,failed:0,expectedReferences:0,foundReferences:0,missingReferences:0,ambiguousLiveRefs:0,uniqueLiveTariffRefs:0,changedVersusCacheUnknown:0};
function components(c){return (c||[]).map(x=>({type:x?.__typename||null,value:x?.formattedValue||null}));}
function corePricing(c){
 return{
  kw:c?.kilowatts??null,connector:c?.standard?.name||c?.standard?.humanName||null,
  free:c?.isChargingFree===true,
  simple:components(c?.priceComponents),
  currency:c?.complexPricingDetail?.currency||'EUR',
  restrictions:(c?.complexPricingDetail?.restrictions||[]).map(r=>({
    restrictionTypes:r.restrictionTypes||[],time:r.timeRestrictions||null,
    date:r.dateRestrictions||null,weekday:r.weekdayRestrictions||null,
    duration:r.durationRestrictions||null,components:components(r.priceComponents)
  }))
 };
}
function sem(c){
 const base=(c.simple||[]).filter(x=>x.type!=='VAT').map(x=>[x.type,x.value]).sort();
 const vals=new Set(base.map(x=>JSON.stringify(x)));
 const restrictions=(c.restrictions||[]).filter(r=>{
  const unbounded=!r.restrictionTypes?.length&&!r.time&&!r.date&&!r.weekday&&!r.duration;
  const repeated=(r.components||[]).length>0&&(r.components||[]).every(x=>vals.has(JSON.stringify([x.type,x.value])));
  return!(unbounded&&repeated);
 });
 return JSON.stringify({free:c.free,currency:c.currency,base,restrictions});
}
async function probe(t){
 let cursor=null,pages=0,all=[],complete=false,error=null,lastCursor=null,status=null;
 for(let page=1;page<=150;page++){
  pages=page;
  const res=await client.request(PAGED_LOCATION_QUERY,{pk:t.pk,first:15,after:cursor},{attempts:2});
  status=res.status;
  const raw=res.json?.data?.chargingLocation;
  if(res.status!==200||!raw?.evses){error='http_or_graphql_missing_location';break;}
  all.push(...(raw.evses.edges||[]).map(x=>x?.node).filter(Boolean));
  const pg=raw.evses.pageInfo||{};
  if(!pg.hasNextPage){complete=true;break;}
  cursor=pg.endCursor;
  if(!cursor||cursor===lastCursor){error='pagination_cursor_stalled';break;}
  lastCursor=cursor;
  await sleep(350);
 }
 if(!complete&&!error)error='pagination_limit';
 const live=all.map(e=>({pk:String(e?.pk??''),reference:String(e?.physicalReference??''),status:e?.status||null,connectors:(e?.connectors?.edges||[]).map(x=>corePricing(x.node))}));
 const byRef=new Map();
 for(const e of live){const id=norm(e.reference);if(!id)continue;let arr=byRef.get(id);if(!arr){arr=[];byRef.set(id,arr);}arr.push(e);}
 const matches=[...t.refs].map(ref=>{
  const entries=byRef.get(ref)||[];
  const signatures=[...new Set(entries.flatMap(e=>e.connectors.map(sem)))];
  return{reference:ref,found:entries.length,livePricingVariants:signatures.length,entries,
    verdict:!entries.length?'MISSING_FROM_LIVE_SNAPSHOT':signatures.length>1?'LIVE_SOURCE_PRICE_CONFLICT':'ONE_LIVE_PRICING_SIGNATURE_NEEDS_PROVENANCE_CHECK'};
 });
 return {
  locationPk:t.pk,stationId:t.stationId,name:t.name,status:complete?'complete':all.length?'partial':'failed',
  pages,httpStatus:status,error,sourceEvseCount:live.length,
  sourceRefCount:byRef.size,expectedRefs:[...t.refs],expectedSourcePks:[...t.sourcePks],
  sourceReasons:[...t.reasons],matches,live
 };
}
for(const [i,t] of list.entries()){
 summary.expectedReferences+=t.refs.size;
 try{
  const result=await probe(t);results.push(result);
  summary[result.status]++;
  for(const m of result.matches){
   if(m.found){summary.foundReferences++;if(m.verdict==='LIVE_SOURCE_PRICE_CONFLICT')summary.ambiguousLiveRefs++;else summary.uniqueLiveTariffRefs++;}
   else summary.missingReferences++;
  }
  console.log(JSON.stringify({n:i+1,total:list.length,pk:t.pk,station:t.name,status:result.status,pages:result.pages,evses:result.sourceEvseCount,found:result.matches.filter(x=>x.found).length,livePriceConflicts:result.matches.filter(x=>x.verdict==='LIVE_SOURCE_PRICE_CONFLICT').length,error:result.error}));
 }catch(e){
  summary.failed++;
  results.push({locationPk:t.pk,stationId:t.stationId,name:t.name,status:'failed',error:String(e?.message||e),expectedRefs:[...t.refs],live:[]});
  console.log(JSON.stringify({pk:t.pk,error:String(e?.message||e)}));
 }
 await sleep(750);
}
const report={schemaVersion:1,generatedAt:new Date().toISOString(),appVersion:process.env.ELECTROVERSE_APP_VERSION||'2026.09.08',
 endpoint:'official Electroverse GraphQL chargingLocation(paged), read-only',
 sourceFile:INPUT,scope:'27 hold EVSEs + 90 parent ambiguous source entries + 4 exact local unpublished + 8 full reused + 4 S81 source fee conflicts',
 summary,results,interpretation:[
 'Live source results are evidence; data are not automatically promoted or published.',
 'An API tariff differing from the CPO direct guest tariff is an independent eMSP offer.',
 'If live has one signature, old cache alternatives are likely obsolete but the currently applicable session context still requires verification.',
 'A live source conflict must remain tariff ambiguous until a verified tariff is selected.'
 ]};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(report,null,2)+'\n');
console.log('RESULT '+JSON.stringify(summary));
if(summary.failed>0||summary.partial>0)process.exitCode=2;
