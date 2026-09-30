import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const MANIFEST=CACHE+'/manifest.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse-fr-real-pdc-coverage-gap.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const txt=x=>String(x??'').trim();
const inc=(o,k,n=1)=>o[k]=(o[k]||0)+n;
const top=o=>Object.entries(o).sort((a,b)=>b[1]-a[1]).slice(0,50).map(([operator,count])=>({operator,count}));
const opOf=p=>{const m=String(p||'').match(/^FR([A-Z0-9]{1,6})E/);return m?m[1]:'UNKNOWN';};

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const tariffManifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const overlayManifest=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));

const published=new Set();
for(const t of overlayManifest.tiles||[]){
  const gz=await fs.readFile(OVERLAY+'/'+t.file);
  const payload=JSON.parse(zlib.gunzipSync(gz).toString('utf8'));
  for(const o of payload.emspOffers||[])for(const id of o.evseIds||[])published.add(norm(id));
}

let locationsWithUnmatched=0,fullyCoveredLocations=0,partialLocations=0,zeroCoveredLocations=0;
let localPdcsAtUnmatchedLocations=0,publishedPdcsAtUnmatchedLocations=0,uncoveredPdcs=0,unmatchedRefs=0;
const uncoveredByOperator={},unmatchedOnFullyCoveredByOperator={},partialByOperator={},samples=[];

for(const sh of tariffManifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk));if(!m)continue;
    const localRaw=(m.irvePdcIds||row.irvePdcIds||[]).filter(Boolean);
    const local=[...new Set(localRaw.map(norm).filter(Boolean))];
    if(!local.length)continue;

    const unresolved=[];
    for(const e of row.tariff?.evses||[]){
      const raw=txt(e?.physicalReference);if(!raw)continue;
      const k=norm(raw);
      if(local.includes(k))continue;
      const parents=local.filter(p=>k.startsWith(p)&&k.length>p.length&&/^\d{1,2}$/.test(k.slice(p.length)));
      if(parents.length)continue;
      if(k.length>=4&&local.filter(p=>p.endsWith(k)).length===1)continue;
      unresolved.push(raw);
    }
    if(!unresolved.length)continue;

    locationsWithUnmatched++;unmatchedRefs+=unresolved.length;
    const covered=local.filter(p=>published.has(p));
    const missing=local.filter(p=>!published.has(p));
    localPdcsAtUnmatchedLocations+=local.length;
    publishedPdcsAtUnmatchedLocations+=covered.length;
    uncoveredPdcs+=missing.length;
    const operator=opOf(local[0]);
    if(missing.length===0){
      fullyCoveredLocations++;inc(unmatchedOnFullyCoveredByOperator,operator,unresolved.length);
    }else if(covered.length===0){
      zeroCoveredLocations++;inc(uncoveredByOperator,operator,missing.length);
    }else{
      partialLocations++;inc(partialByOperator,operator,1);inc(uncoveredByOperator,operator,missing.length);
    }
    if(samples.length<120&&missing.length)samples.push({
      locationPk:String(row.electroverseLocationPk),operator,
      localPdcCount:local.length,coveredPdcCount:covered.length,missingPdcCount:missing.length,
      missingPdcs:missing.slice(0,30),unmatchedRefs:unresolved.slice(0,20)
    });
  }
}

const report={
  generatedAt:new Date().toISOString(),
  overlayPublishedEvses:overlayManifest.stats?.publishedEvses??null,
  overlayPublishedConnectorCount:overlayManifest.stats?.publishedConnectorCount??null,
  unmatchedRefs,
  locationsWithUnmatched,
  fullyCoveredLocations,
  partialLocations,
  zeroCoveredLocations,
  localPdcsAtUnmatchedLocations,
  publishedPdcsAtUnmatchedLocations,
  uncoveredPdcs,
  pdcCoverageRateAtUnmatchedLocations:localPdcsAtUnmatchedLocations?publishedPdcsAtUnmatchedLocations/localPdcsAtUnmatchedLocations:null,
  uncoveredPdcsByOperator:top(uncoveredByOperator),
  unmatchedRefsOnFullyCoveredLocationsByOperator:top(unmatchedOnFullyCoveredByOperator),
  partialLocationsByOperator:top(partialByOperator),
  samplesWithRealMissingPdcs:samples
};
await fs.mkdir('reports',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
