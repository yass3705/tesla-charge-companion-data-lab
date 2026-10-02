import fs from 'node:fs/promises';
const RES='reports/electroverse/b-residual-analysis.json';
const SES='reports/electroverse/b-final13-live-session-probe.json';
const HIST='reports/electroverse/b-electric55-history-audit.json';
const OUT='reports/electroverse/b-fr55c-7kw-power-variant-audit.json';
const res=JSON.parse(await fs.readFile(RES,'utf8'));
const ses=JSON.parse(await fs.readFile(SES,'utf8'));
const hist=JSON.parse(await fs.readFile(HIST,'utf8'));
const wanted=new Set(['378568','4076975','4097604','4584733','1291235']);
const sessByLoc=new Map((ses.rows||[]).map(x=>[String(x.locationPk),x]));
const latest=hist.snapshots?.[hist.snapshots.length-1]?.rows||[];
const latestByStation=new Map(latest.map(x=>[String(x.stationId),x]));
function pSig(r){return JSON.stringify((r.connectors||[]).map(c=>({
 isChargingFree:c.isChargingFree,
 priceComponents:c.priceComponents,
 complexPricingDetail:c.complexPricingDetail
})));}
const ready=[];
const audit=[];
for(const g of res.unresolvedSamples||[]){
 if(!wanted.has(String(g.electroverseLocationPk)))continue;
 const loc=String(g.electroverseLocationPk), st=String(g.irveStationId);
 const refs=(g.refs||[]).filter(r=>r.connectors?.length===1 && Number(r.connectors[0]?.kilowatts)===7 && String(r.connectors[0]?.standard)==='IEC_62196_T2');
 const sigs=new Set(refs.map(pSig));
 const live=sessByLoc.get(loc);
 const liveRows=(live?.evses||[]).filter(e=>refs.some(r=>String(r.evsePk)===String(e.pk)));
 const direct=latestByStation.get(st);
 const targetPdcs=(direct?.chargePoints||[]).filter(p=>Math.abs(Number(p.powerKw)-22.08)<=1 && (p.connectors||[]).includes('TYPE_2')).map(p=>p.evseId);
 const histStable=(hist.snapshots||[]).every(s=>{
   const row=(s.rows||[]).find(x=>String(x.stationId)===st);
   if(!row)return false;
   const cps=row.chargePoints||[];
   return cps.length===2 && cps.every(p=>Math.abs(Number(p.powerKw)-22.08)<=1 && (p.connectors||[]).includes('TYPE_2'));
 });
 const recentOrLive=liveRows.every(e=>e.status==='AVAILABLE'||e.status==='CHARGING') &&
   liveRows.some(e=>e.lastSessionStartedAt);
 const ok=refs.length===3 && sigs.size===1 && targetPdcs.length===2 && histStable && recentOrLive;
 const row={locationPk:loc,station:st,sourceCount:refs.length,sourcePks:refs.map(r=>r.evsePk),physicalReferences:refs.map(r=>r.physicalReference),pricingSignatureCount:sigs.size,targetPdcs,historicalInventoryStable:histStable,live:liveRows.map(e=>({pk:e.pk,status:e.status,lastSessionStartedAt:e.lastSessionStartedAt})),ready:ok};
 audit.push(row);
 if(ok)ready.push({
   mode:'homogeneous_target_subset',
   operator:'B_FR55C_7KW_POWER_VARIANT',
   electroverseLocationPk:loc,
   irveStationId:st,
   sourceEvsePks:refs.map(r=>r.evsePk),
   physicalReferences:refs.map(r=>r.physicalReference),
   targetPdcs,
   uniformConnectorCount:true,
   profile:{kilowatts:7,standard:'IEC_62196_T2'},
   evidence:{
     source:'Electric55 direct station history + Electroverse live session evidence',
     observed:'2026-10-02',
     note:'Three live Electroverse 7 kW Type-2 aliases at this station have identical compiled pricing. Five Electric55 snapshots since August consistently expose exactly two current 22.08 kW Type-2 physical PDCs. Publish the 7 kW Electroverse tariff as a connector-power alias variant on the current station PDC set without asserting source-to-branch identity.'
   }
 });
}
const out={generatedAt:new Date().toISOString(),readyGroupCount:ready.length,readySourceEvses:ready.reduce((n,g)=>n+g.sourceEvsePks.length,0),readyLocations:ready.length,ready,audit};
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));