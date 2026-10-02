import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse/unpublished-source-evse-ranking.json';

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const opFromRef=raw=>{
  const s=String(raw??'').trim();
  const star=s.split('*').map(x=>x.trim()).filter(Boolean);
  if(star.length>=2 && /^FR$/i.test(star[0])) return star[1].toUpperCase();
  const n=norm(s);
  const m=n.match(/^FR([A-Z0-9]{1,8})E/);
  if(m)return m[1];
  if(/^MAT\d+/i.test(s))return 'MAT';
  if(/^B\d+/i.test(s))return 'B';
  if(/^\d+$/.test(s))return 'NUMERIC';
  return n.slice(0,12)||'MISSING';
};
const connectorStatus=e=>{
  const cs=e?.connectors||[];
  if(!cs.length)return 'no_connectors';
  let priced=0,complex=0;
  for(const c of cs){
    if(c?.isChargingFree===true || (c?.priceComponents||[]).length)priced++;
    if((c?.complexPricingDetail?.restrictions||[]).length)complex++;
  }
  if(priced===cs.length)return complex?'priced_complex':'priced_simple';
  if(priced)return 'partially_priced';
  return 'no_pricing';
};

const oman=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedSourcePks=new Set(),publishedTargets=new Set();
let offerCount=0;
for(const t of oman.tiles||[]){
  const gz=await fs.readFile(OVERLAY+'/'+t.file);
  const tile=JSON.parse(zlib.gunzipSync(gz));
  for(const o of tile.emspOffers||[]){
    offerCount++;
    for(const pk of o?.metadata?.electroverseEvsePks||[]) if(pk!=null) publishedSourcePks.add(String(pk));
    for(const pk of o?.metadata?.electroverseAliasEvsePks||[]) if(pk!=null) publishedSourcePks.add(String(pk));
    if(o?.metadata?.electroverseEvsePk!=null) publishedSourcePks.add(String(o.metadata.electroverseEvsePk));
    for(const id of o.evseIds||[]) publishedTargets.add(norm(id));
  }
}

const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const byOperator={},byConnectorStatus={},samples=[];
let sourceEvses=0,unpublished=0,missingPk=0;
for(const sh of cman.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    for(const e of row?.tariff?.evses||[]){
      sourceEvses++;
      const pk=e?.pk;
      if(pk==null){missingPk++;continue;}
      if(publishedSourcePks.has(String(pk)))continue;
      unpublished++;
      const op=opFromRef(e?.physicalReference);
      byOperator[op]=(byOperator[op]||0)+1;
      const st=connectorStatus(e);
      byConnectorStatus[st]=(byConnectorStatus[st]||0)+1;
      if(samples.length<250)samples.push({
        electroverseLocationPk:String(row.electroverseLocationPk),
        evsePk:pk,
        physicalReference:e?.physicalReference??null,
        operatorBucket:op,
        connectorStatus:st,
        connectorCount:(e?.connectors||[]).length,
        irveStationId:row.irveStationId??null,
        localPdcCount:(row.irvePdcIds||[]).length
      });
    }
  }
}
const ranking=Object.entries(byOperator)
  .map(([operator,count])=>({operator,count}))
  .sort((a,b)=>b.count-a.count||a.operator.localeCompare(b.operator));
const out={
  schemaVersion:1,
  generatedAt:new Date().toISOString(),
  sourceEvseCount:sourceEvses,
  publishedOfferCount:offerCount,
  publishedUniqueSourceEvsePks:publishedSourcePks.size,
  publishedUniqueNationalTargets:publishedTargets.size,
  unpublishedSourceEvseCount:unpublished,
  sourceEvsesWithoutPk:missingPk,
  coveragePct:sourceEvses?Number((100*(sourceEvses-unpublished)/sourceEvses).toFixed(3)):0,
  byConnectorStatus:Object.fromEntries(Object.entries(byConnectorStatus).sort((a,b)=>b[1]-a[1])),
  residualRanking:ranking,
  top20:ranking.slice(0,20),
  policy:'Counts source Electroverse EVSE PKs absent from every currently published France EVSE overlay offer. This is post-rule residual coverage, not a raw identity-pattern audit.',
  samples
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
