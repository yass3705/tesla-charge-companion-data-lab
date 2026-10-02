import fs from 'node:fs/promises';
import {DirectElectroverseClient,SINGLE_LOCATION_QUERY,PAGED_LOCATION_QUERY} from './lib/electroverse_direct_client.mjs';
const RES='reports/electroverse/b-residual-analysis.json';
const OUT='reports/electroverse/b-final13-live-status-probe.json';
const res=JSON.parse(await fs.readFile(RES,'utf8'));
const targets=(res.unresolvedSamples||[]).map(g=>({
  locationPk:String(g.electroverseLocationPk),
  residualPks:new Set((g.refs||[]).map(r=>String(r.evsePk))),
  station:g.irveStationId
}));
const client=new DirectElectroverseClient({timeoutMs:60000});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const nodes=x=>(x?.edges||[]).map(e=>e?.node).filter(Boolean);
async function fetchLoc(pk){
  let r=await client.request(SINGLE_LOCATION_QUERY,{pk},{attempts:2});
  let loc=r.json?.data?.chargingLocation||null;
  if(loc)return {loc,mode:'single',status:r.status,errors:r.json?.errors||[]};
  let edges=[],after=null,meta=null;
  for(let page=1;page<=50;page++){
    r=await client.request(PAGED_LOCATION_QUERY,{pk,first:10,after},{attempts:2});
    loc=r.json?.data?.chargingLocation||null;
    if(!loc?.evses)return {loc:null,mode:'failed',status:r.status,errors:r.json?.errors||[]};
    meta??=loc;edges.push(...(loc.evses.edges||[]));
    const pi=loc.evses.pageInfo||{};
    if(!pi.hasNextPage)return {loc:{...meta,evses:{edges,pageInfo:pi}},mode:'paged',status:r.status,errors:[]};
    if(!pi.endCursor)break; after=pi.endCursor;
  }
  return {loc:null,mode:'failed',status:r.status,errors:r.json?.errors||[]};
}
const rows=[];
for(let i=0;i<targets.length;i++){
  const t=targets[i],f=await fetchLoc(t.locationPk);
  const all=nodes(f.loc?.evses).map(e=>({
    pk:e?.pk??null,
    physicalReference:e?.physicalReference??null,
    status:e?.status??null,
    residual:t.residualPks.has(String(e?.pk)),
    connectors:nodes(e?.connectors).map(c=>({
      pk:c?.pk??null,kilowatts:c?.kilowatts??null,speed:c?.speed??null,
      standard:c?.standard?.name??c?.standard??null,isChargingFree:c?.isChargingFree??null
    }))
  }));
  rows.push({locationPk:t.locationPk,station:t.station,fetchMode:f.mode,httpStatus:f.status,errors:(f.errors||[]).map(e=>e.message),evses:all});
  if(i<targets.length-1)await sleep(1250);
}
const out={generatedAt:new Date().toISOString(),locations:rows.length,residualEvses:targets.reduce((n,t)=>n+t.residualPks.size,0),rows};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
const counts={};
for(const r of rows)for(const e of r.evses.filter(e=>e.residual))counts[String(e.status??'NULL')]=(counts[String(e.status??'NULL')]||0)+1;
console.log(JSON.stringify({generatedAt:out.generatedAt,locations:out.locations,residualEvses:out.residualEvses,residualStatusCounts:counts,failed:rows.filter(r=>r.fetchMode==='failed').length},null,2));
