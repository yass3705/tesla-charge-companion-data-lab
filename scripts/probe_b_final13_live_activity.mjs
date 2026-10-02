import fs from 'node:fs/promises';
import {DirectElectroverseClient} from './lib/electroverse_direct_client.mjs';
const RES='reports/electroverse/b-residual-analysis.json';
const OUT='reports/electroverse/b-final13-live-activity-probe.json';
const res=JSON.parse(await fs.readFile(RES,'utf8'));
const targets=(res.unresolvedSamples||[]).map(g=>({
  locationPk:String(g.electroverseLocationPk),
  station:g.irveStationId,
  residualPks:new Set((g.refs||[]).map(r=>String(r.evsePk)))
}));
const client=new DirectElectroverseClient({timeoutMs:60000});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const Q=`query($pk:String!){chargingLocation(pk:$pk){chargingLocationPk evses(first:100){edges{node{
  pk physicalReference status isActive lastSessionStartedAt supportsInAppCharging capabilities
  connectors{edges{node{pk kilowatts speed standard{... on EJNConnectorStandardType{name humanName}}}}}
}} pageInfo{hasNextPage endCursor}}}}`;
const rows=[];
for(let i=0;i<targets.length;i++){
  const t=targets[i];
  const r=await client.request(Q,{pk:t.locationPk},{attempts:2});
  const loc=r.json?.data?.chargingLocation||null;
  const all=(loc?.evses?.edges||[]).map(x=>x?.node).filter(Boolean).map(e=>({
    pk:e.pk??null,physicalReference:e.physicalReference??null,status:e.status??null,
    isActive:e.isActive??null,lastSessionStartedAt:e.lastSessionStartedAt??null,
    supportsInAppCharging:e.supportsInAppCharging??null,capabilities:e.capabilities??null,
    residual:t.residualPks.has(String(e.pk)),
    connectors:(e.connectors?.edges||[]).map(x=>x?.node).filter(Boolean).map(c=>({
      pk:c.pk??null,kilowatts:c.kilowatts??null,speed:c.speed??null,
      standard:c.standard?.name??c.standard??null
    }))
  }));
  rows.push({locationPk:t.locationPk,station:t.station,httpStatus:r.status,errors:(r.json?.errors||[]).map(e=>e.message),evses:all});
  if(i<targets.length-1)await sleep(1000);
}
const out={generatedAt:new Date().toISOString(),locations:rows.length,residualEvses:targets.reduce((n,t)=>n+t.residualPks.size,0),rows};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
const active={};const status={};
for(const r of rows)for(const e of r.evses.filter(e=>e.residual)){
  active[String(e.isActive)]=(active[String(e.isActive)]||0)+1;
  status[String(e.status)]=(status[String(e.status)]||0)+1;
}
console.log(JSON.stringify({generatedAt:out.generatedAt,locations:out.locations,residualEvses:out.residualEvses,active,status,errors:rows.filter(r=>r.errors.length).length},null,2));
