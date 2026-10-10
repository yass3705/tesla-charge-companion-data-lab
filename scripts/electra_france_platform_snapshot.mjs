import fs from 'node:fs/promises';
import fss from 'node:fs';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import path from 'node:path';

const OUT=process.argv[2]||'data/platforms/electra/france';
const NATIONAL=process.argv[3]||'data/national/france-irve-static-v9/all.json.gz';
const ASSOCIATIONS=process.argv[4]||'data/platforms/electra/irve-associations-batch-01.json';
const ASSOCIATION_DIR=process.argv[5]||'data/platforms/electra/irve-association-batches';
const VERIFIED_APP_LINKS=process.argv[6]||'data/platforms/electra/verified-app-evse-tariff-map.json';
const URL='https://emsp.go-electra.com/graphql';
const PAGE_SIZE=100,CONCURRENCY=8,MAX_RETRIES=5,TILE=.5;
await fs.mkdir(OUT,{recursive:true});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const round=(x,d=6)=>Number(Number(x).toFixed(d));
const weekdays={SUNDAY:0,MONDAY:1,TUESDAY:2,WEDNESDAY:3,THURSDAY:4,FRIDAY:5,SATURDAY:6};

const Q=`query Rich($limit:Int,$offset:Int){locations(limit:$limit,offset:$offset){totalCount items{
 id name address city postalCode country coordinates{latitude longitude} connectorTypes maxPower
 cpo{name} operator{name}
 evses{id status physicalReference evseId}
 chargeTariffs{
  chargeTariffId currency currentPricePerKwh
  elements{
   restrictions{dayOfWeek startTime endTime minDuration maxDuration startDate endDate minKwh maxKwh minPower maxPower}
   priceComponents{type price}
  }
 }
}}}`;

async function page(offset,attempt=1){
  try{
    const r=await fetch(URL,{method:'POST',headers:{'content-type':'application/json','accept':'application/json','user-agent':'tcc-v9-electra-france-platform/1.0'},body:JSON.stringify({query:Q,variables:{limit:PAGE_SIZE,offset}}),signal:AbortSignal.timeout(30000)});
    const text=await r.text();let json=null;try{json=JSON.parse(text)}catch{}
    if(r.status!==200||json?.errors?.length||!json?.data?.locations){
      if(attempt<MAX_RETRIES){await sleep(700*2**(attempt-1));return page(offset,attempt+1);}
      return {offset,error:json?.errors??text.slice(0,500),status:r.status,data:null};
    }
    return {offset,error:null,status:r.status,data:json.data.locations};
  }catch(e){
    if(attempt<MAX_RETRIES){await sleep(700*2**(attempt-1));return page(offset,attempt+1);}
    return {offset,error:String(e),status:0,data:null};
  }
}
function compatible(x){return (x?.connectorTypes??[]).some(v=>/combo|ccs|type.?2|schuko/i.test(String(v)));}
function componentKind(type){
  const t=String(type||'').toUpperCase();
  if(t==='ENERGY'||t.includes('CONSUMPTION'))return 'energy';
  if(t==='TIME')return 'time';
  if(t==='PARKING_TIME')return 'parking';
  if(t==='FLAT')return 'flat';
  if(t==='CONGESTION_TIME')return 'congestion';
  return '';
}
function compileTariff(t){
  const currency=String(t?.currency||'EUR').toUpperCase();
  const base={energy:0,time:0,parking:0,flat:0,congestion:0},windows=new Map(),duration=[],congestionBands=[];
  const unsupported=[];
  for(const el of t?.elements||[]){
    const rr=el?.restrictions||{},values={energy:0,time:0,parking:0,flat:0,congestion:0},present=new Set();
    for(const pc of el?.priceComponents||[]){
      const kind=componentKind(pc?.type),raw=Number(pc?.price);
      if(!kind||!Number.isFinite(raw)){unsupported.push(pc?.type||'unknown');continue;}
      let value=raw;if(kind==='time'||kind==='parking'||kind==='congestion')value/=60;
      values[kind]+=value;present.add(kind);
    }
    if(unsupported.length)return null;
    const start=rr.startTime||null,end=rr.endTime||null;
    const minDur=Number(rr.minDuration);
    const threshold=Number.isFinite(minDur)&&minDur>0?minDur/60:0;
    const days=Array.isArray(rr.dayOfWeek)&&rr.dayOfWeek.length?rr.dayOfWeek.map(x=>weekdays[x]).filter(Number.isInteger):null;
    // OCPI minDuration/maxDuration are seconds, not a reason to discard a valid
    // congestion component. Preserve the bounded rate and the user's SOC 80%
    // default; the runtime calculates the intersection of these conditions.
    if(present.has('congestion')&&(rr.minDuration!=null||rr.maxDuration!=null)){
      const min=rr.minDuration==null?0:Number(rr.minDuration);
      const max=rr.maxDuration==null?null:Number(rr.maxDuration);
      if(!Number.isFinite(min)||min<0||(max!=null&&(!Number.isFinite(max)||max<=min)))return null;
      congestionBands.push({min,max,rate:values.congestion,start,end,days});
      values.congestion=0;present.delete('congestion');
    }
    if(start||end){
      const key=`${start||'00:00'}|${end||'24:00'}|${(days||[]).join(',')}`;
      let w=windows.get(key);if(!w){w={values:{...base},present:new Set(),start:start||'00:00',end:end||'24:00',days};windows.set(key,w);}
      if(threshold>0){
        const surcharge=values.time+values.parking;
        if(surcharge>0)duration.push({threshold,rate:surcharge,start:w.start,end:w.end,days});
      }else for(const k of present){w.values[k]+=values[k];w.present.add(k);}
    }else if(threshold>0){
      const surcharge=values.time+values.parking;if(surcharge>0)duration.push({threshold,rate:surcharge});
    }else for(const k of present)base[k]+=values[k];
  }
  if(base.energy===0&&Number.isFinite(Number(t?.currentPricePerKwh)))base.energy=Number(t.currentPricePerKwh);
  const rule=(scope,start,end,r,days=null,after=null)=>({
    scope,start,end,billing:r.energy>0?'kwh':r.time>0?'minute':'kwh',currency,
    pricePerKwh:round(r.energy),chargePerMinute:round(r.time),connectionFee:round(r.flat),idlePerMinute:round(r.parking),
    congestionTimePerMinute:round(r.congestion),congestionStartSoc:80,congestionThresholdSource:'default_soc80',
    ocpiCongestionDurationBands:congestionBands
      .filter(x=>scope==='allDay'?!x.start:x.start===start&&x.end===end)
      .map(x=>[x.min,x.max,round(x.rate)]),
    afterMinutesRate:after?round(after.rate):0,afterMinutesThreshold:after?Math.round(after.threshold):0,days,ocpiDurationBands:[]
  });
  const baseAfter=duration.filter(x=>!x.start).sort((a,b)=>a.threshold-b.threshold)[0]||null;
  const rules=[rule('allDay','00:00','24:00',base,null,baseAfter)];
  for(const w of windows.values()){
    const r={...base};for(const k of w.present)r[k]=w.values[k];
    const after=duration.filter(x=>x.start===w.start&&x.end===w.end).sort((a,b)=>a.threshold-b.threshold)[0]||null;
    rules.push(rule('timeWindow',w.start,w.end,r,w.days,after));
  }
  return {type:'rules',rules};
}
function signature(p){return JSON.stringify(p);}
function tileId(lat,lon){const a=Math.floor(lat/TILE),b=Math.floor(lon/TILE);return `t_${a}_${b}`;}

const nationalRows=JSON.parse(zlib.gunzipSync(fss.readFileSync(NATIONAL)).toString('utf8'));
const verifiedEvidence=JSON.parse(fss.readFileSync(VERIFIED_APP_LINKS,'utf8'));
if(verifiedEvidence.schemaVersion!==1||!Array.isArray(verifiedEvidence.verifiedLinks))throw new Error('Invalid verified Electra EVSE evidence ledger');
const verifiedByLocation=new Map();
for(const x of verifiedEvidence.verifiedLinks){
 if(verifiedByLocation.has(String(x.locationId)))throw new Error('Duplicate verified Electra location');
 if(!Array.isArray(x.mappings)||!x.mappings.length)throw new Error('Verified location without EVSE mappings');
 verifiedByLocation.set(String(x.locationId),x);
}
const nationalEvse=new Set(),nationalPowerByEvse=new Map();
for(const row of nationalRows)for(const cfg of row?.[8]||[])for(const id of Array.isArray(cfg?.[6])?cfg[6]:[]){
  const key=norm(id),power=Number(cfg?.[3]);
  nationalEvse.add(key);
  if(Number.isFinite(power)&&power>0){
    const old=nationalPowerByEvse.get(key);
    nationalPowerByEvse.set(key,old==null?power:old===power?power:null);
  }
}
// In a location with several distinct tariffs, only an explicit exclusive
// minPower/maxPower restriction proves which EVSE may use which tariff.
// Absent such a discriminator, do not guess a tariff from the station name.
function powerScope(t){
  const elements=t?.elements||[];
  if(!elements.length)return null;
  const scopes=elements.map(e=>{
    const r=e?.restrictions||{},min=r.minPower==null?null:Number(r.minPower),max=r.maxPower==null?null:Number(r.maxPower);
    if(min==null&&max==null)return null;
    if(min!=null&&(!Number.isFinite(min)||min<0))return null;
    if(max!=null&&(!Number.isFinite(max)||max<=0))return null;
    return {min:min??0,max:max??Infinity};
  });
  if(scopes.some(x=>!x))return null;
  const min=Math.max(...scopes.map(x=>x.min)),max=Math.min(...scopes.map(x=>x.max));
  return min<=max?{min,max}:null;
}

const first=await page(0);if(!first.data)throw new Error('first Electra page failed '+JSON.stringify(first.error));
const total=first.data.totalCount,totalPages=Math.ceil(total/PAGE_SIZE),locations=[];
const failures=[];
function acceptItems(items){for(const x of items||[])if(x?.country==='FR'&&compatible(x))locations.push(x);}
acceptItems(first.data.items);
let next=1;
async function worker(){while(true){const i=next++;if(i>=totalPages)return;const r=await page(i*PAGE_SIZE);if(!r.data)failures.push({page:i,...r});else acceptItems(r.data.items);if(i%250===0)console.log(`Electra ${i}/${totalPages}, FR=${locations.length}, failures=${failures.length}`);}}
await Promise.all(Array.from({length:CONCURRENCY},worker));
if(failures.length)throw new Error(`Electra extraction has ${failures.length} failed pages; refusing snapshot`);

const associationDocuments=[JSON.parse(fss.readFileSync(ASSOCIATIONS,'utf8'))];
let associationPartFiles=[];
try{associationPartFiles=(await fs.readdir(ASSOCIATION_DIR)).filter(name=>name.endsWith('.json')).sort();}
catch(error){if(error?.code!=='ENOENT')throw error;}
for(const file of associationPartFiles)associationDocuments.push(JSON.parse(fss.readFileSync(path.join(ASSOCIATION_DIR,file),'utf8')));
if(associationDocuments.some(doc=>doc.schemaVersion!==1||doc.status!=='curated_location_associations'||!Array.isArray(doc.associations)))throw new Error('Invalid curated IRVE association document');
const curatedAssociations=new Map();
for(const doc of associationDocuments)for(const association of doc.associations){
  const id=String(association[0]);
  if(curatedAssociations.has(id))throw new Error('Duplicate Electra location in curated IRVE associations: '+id);
  curatedAssociations.set(id,{association,document:doc});
}
const batchStats=new Map(associationDocuments.map(doc=>[doc.batch,{applied:0,conflicts:0}]));
const exactClaims=new Map();
for(const loc of locations)for(const evse of loc.evses||[]){
  const id=norm(evse?.evseId);
  if(!id||!nationalEvse.has(id))continue;
  if(!exactClaims.has(id))exactClaims.set(id,new Set());
  exactClaims.get(id).add(String(loc.id));
}

const tiles=new Map(),residualLocations=[],reasons={},cpoSummary=new Map(),stats={franceCompatibleLocations:locations.length,locationsWithNationalEvse:0,curatedLocationAssociations:0,manualAssociationConflicts:0,publishedLocations:0,publishedEvseIds:0,publishedOffers:0,verifiedAppLocations:0,verifiedAppEvseOffers:0};
for(const x of locations){
  const cpo=String(x.cpo?.name||'CPO inconnu');
  if(!cpoSummary.has(cpo))cpoSummary.set(cpo,{cpo,totalCompatibleLocations:0,locationsWithNationalEvse:0,curatedLocationAssociations:0,matchedEvseIds:0,publishedLocations:0,publishedEvseIds:0,rejected:{}});
  const cs=cpoSummary.get(cpo);cs.totalCompatibleLocations++;
  const reject=reason=>{reasons[reason]=(reasons[reason]||0)+1;cs.rejected[reason]=(cs.rejected[reason]||0)+1;residualLocations.push({electraLocationId:String(x.id),name:x.name||null,address:x.address||null,city:x.city||null,postalCode:x.postalCode||null,country:x.country||null,coordinates:x.coordinates||null,connectorTypes:x.connectorTypes||[],maxPower:x.maxPower??null,cpo,operator:x.operator?.name||null,reason,evses:(x.evses||[]).map(e=>({id:e.id||null,evseId:e.evseId||null,status:e.status||null,physicalReference:e.physicalReference||null}))});};
  const exact=[...new Set((x.evses||[]).map(e=>e?.evseId).filter(Boolean).filter(id=>nationalEvse.has(norm(id))))];
  const associationMatch=curatedAssociations.get(String(x.id));
  const override=associationMatch?.association,associationDocument=associationMatch?.document;
  let associatedIds=exact,identityMode='exact_national_irve_evse',associationEvidence=null;
  if(!exact.length&&override){
    const legacyShape=Array.isArray(override[1]);
    const idsIndex=legacyShape?1:2,distanceIndex=legacyShape?2:3,similarityIndex=legacyShape?3:4;
    const overrideCpo=legacyShape?String(associationDocument.cpo||''):String(override[1]||'');
    const candidateIds=Array.isArray(override[idsIndex])?[...new Set(override[idsIndex].map(String))]:[];
    const evidenceValid=Number.isFinite(Number(override[distanceIndex]))&&Number(override[distanceIndex])<=15&&Number(override[similarityIndex])>=.70;
    const exactConflict=candidateIds.some(id=>[...(exactClaims.get(norm(id))||[])].some(owner=>owner!==String(x.id)));
    const cpoValid=overrideCpo===cpo&&associationDocument.status==='curated_location_associations';
    const idsValid=candidateIds.length>0&&candidateIds.every(id=>nationalEvse.has(norm(id)));
    if(cpoValid&&idsValid&&evidenceValid&&!exactConflict){
      associatedIds=candidateIds;identityMode='curated_irve_location';
      associationEvidence={batch:associationDocument.batch,distanceMeters:Number(override[distanceIndex]),nameAddressSimilarity:Number(override[similarityIndex])};
      stats.curatedLocationAssociations++;cs.curatedLocationAssociations++;
      const batchStat=batchStats.get(associationDocument.batch);if(batchStat)batchStat.applied++;
    }else{
      stats.manualAssociationConflicts++;
      const batchStat=batchStats.get(associationDocument.batch);if(batchStat)batchStat.conflicts++;
      if(exactConflict){reject('manual_irve_association_conflict');continue;}
    }
  }
  if(!associatedIds.length){reject('no_national_evse');continue;}
  stats.locationsWithNationalEvse++;cs.locationsWithNationalEvse++;cs.matchedEvseIds+=associatedIds.length;
  const compiled=(x.chargeTariffs||[]).map(compileTariff);
  // Electra's own app tariff is fixed at session start (official price terms,
  // go-electra.com/fr/price). This is NOT an assumption about partner CPOs
  // sold through Electra eMSP, which may set different charging conditions.
  if(cpo==='Electra')for(const pricing of compiled){
    if(!pricing)continue;
    pricing.priceSelectionBasis='session_start_local_time';
    pricing.tariffStartLockEvidence='electra_official_2026-10-10';
    for(const rule of pricing.rules||[])rule.congestionFeeCapEur=50;
  }
  if(!compiled.length){reject('no_tariff');continue;}
  if(compiled.some(v=>!v)){reject('unsupported_tariff');continue;}
  const uniq=[...new Map(compiled.map(v=>[signature(v),v])).values()];
  const assigned=new Map(),tariffs=x.chargeTariffs||[];
  const manual=verifiedByLocation.get(String(x.id));
  if(manual){
    let invalid=manual.cpo!==cpo||manual.locationName!==x.name;
    const seen=new Set();
    for(const proof of manual.mappings){
      const key=norm(proof.evseId);
      const ids=associatedIds.filter(id=>norm(id)===key);
      const power=nationalPowerByEvse.get(key);
      const tariffIndexes=tariffs.map((t,i)=>t.chargeTariffId===proof.chargeTariffId?i:-1).filter(i=>i>=0);
      if(seen.has(key)||ids.length!==1||!(power>0)||Math.abs(power-Number(proof.powerKw))>0.01||tariffIndexes.length!==1){invalid=true;break;}
      const i=tariffIndexes[0],t=tariffs[i];
      const allComponents=(t.elements||[]).flatMap(e=>e.priceComponents||[]);
      const energy=allComponents.filter(p=>p.type==='ENERGY').map(p=>Number(p.price));
      const kinds=[...new Set(allComponents.map(p=>String(p.type)))].sort();
      const expected=[...(proof.components||[])].sort();
      if(!energy.length||energy.some(v=>!Number.isFinite(v)||Math.abs(v-Number(proof.rateEurPerKwh))>0.0001)||
         kinds.length!==expected.length||kinds.some((v,j)=>v!==expected[j])){invalid=true;break;}
      assigned.set(key,compiled[i]);seen.add(key);
    }
    if(invalid||assigned.size!==manual.mappings.length){reject('verified_app_tariff_link_invalid');continue;}
  }else if(uniq.length===1){
    for(const id of associatedIds)assigned.set(norm(id),uniq[0]);
  }else{
    const scopes=tariffs.map(powerScope);
    if(scopes.some(x=>!x)){reject('tariff_attribution_missing_evse_evidence');continue;}
    // Multiple non-identical tariffs at the same power are a real assignment
    // conflict; different powers are expected and do not conflict.
    let ambiguous=false;
    for(const id of associatedIds){
      const power=nationalPowerByEvse.get(norm(id));
      if(!(power>0)){ambiguous=true;break;}
      const matches=scopes.map((b,i)=>({b,i})).filter(({b})=>power>=b.min&&power<=b.max);
      if(matches.length!==1){ambiguous=true;break;}
      assigned.set(norm(id),compiled[matches[0].i]);
    }
    if(ambiguous){reject('same_power_tariff_assignment_ambiguous');continue;}
  }
  if(manual&&assigned.size<associatedIds.length){
    const pending=(x.evses||[]).filter(e=>associatedIds.some(id=>norm(id)===norm(e.evseId))&&!assigned.has(norm(e.evseId)));
    const reason='verified_app_partial_attribution_pending';
    reasons[reason]=(reasons[reason]||0)+1;
    cs.rejected[reason]=(cs.rejected[reason]||0)+1;
    residualLocations.push({electraLocationId:String(x.id),name:x.name||null,address:x.address||null,
      city:x.city||null,postalCode:x.postalCode||null,country:x.country||null,coordinates:x.coordinates||null,
      connectorTypes:x.connectorTypes||[],maxPower:x.maxPower??null,cpo,operator:x.operator?.name||null,
      reason,evses:pending.map(e=>({id:e.id||null,evseId:e.evseId||null,status:e.status||null,
        physicalReference:e.physicalReference||null}))});
  }
  const lat=Number(x.coordinates?.latitude),lon=Number(x.coordinates?.longitude);
  if(!Number.isFinite(lat)||!Number.isFinite(lon)){reject('no_coordinates');continue;}
  const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);
  for(const pdc of associatedIds){
    const pricing=assigned.get(norm(pdc));
    if(!pricing)continue;
    const offer={
      id:`electra-platform:${x.id}:${norm(pdc)}`,provider:'Electra',countries:['FR'],
      currency:pricing.rules?.[0]?.currency||'EUR',priority:82,evseIds:[pdc],
      pricing,metadata:{verified:true,verifiedScope:'exact_evse',identityMode,associationEvidence,
      electraLocationId:String(x.id),nationalEvseId:pdc,cpo:x.cpo?.name||null,operator:x.operator?.name||null,
      source:identityMode==='exact_national_irve_evse'?'Electra eMSP GraphQL':'Electra eMSP GraphQL + curated national IRVE location crosswalk',
      tariffAttributionEvidence:manual?'user_electra_app_verified_per_power':null,
      screenshotSha256:manual?.screenshotSha256??null}
    };
    tiles.get(id).push(offer);stats.publishedOffers++;
  }
  stats.publishedLocations++;stats.publishedEvseIds+=assigned.size;
  cs.publishedLocations++;cs.publishedEvseIds+=assigned.size;
  if(manual){stats.verifiedAppLocations++;stats.verifiedAppEvseOffers+=assigned.size;}
}
const manifestTiles=[];
for(const [id,offers] of [...tiles.entries()].sort((a,b)=>a[0].localeCompare(b[0]))){
  const payload={schemaVersion:1,country:'FR',emspOffers:offers};
  const gz=zlib.gzipSync(Buffer.from(JSON.stringify(payload)),{level:9});
  const file=`${id}.json.gz`;await fs.writeFile(path.join(OUT,file),gz);
  const [a,b]=id.slice(2).split('_').map(Number);
  manifestTiles.push({id,file,minLat:a*TILE,maxLat:(a+1)*TILE,minLon:b*TILE,maxLon:(b+1)*TILE,count:offers.length,bytes:gz.length,sha256:sha(gz)});
}
const sourceEvseCount=locations.reduce((n,x)=>n+(x.evses||[]).length,0);
const sourceGz=zlib.gzipSync(Buffer.from(JSON.stringify({schemaVersion:1,country:'FR',generatedAt:new Date().toISOString(),source:'Electra GraphQL compatible France locations',locations})),{level:9});
await fs.writeFile(path.join(OUT,'source-locations.json.gz'),sourceGz);
stats.sourceLocationCount=locations.length;
stats.sourceEvseCount=sourceEvseCount;
stats.retainedUnmatchedLocations=residualLocations.length;
const manifest={schemaVersion:1,dataset:'electra-france-platform-national-evse-overlay',generatedAt:new Date().toISOString(),source:{endpoint:URL,globalTotalCount:total,totalPages},country:'FR',tileSizeDegrees:TILE,tileCount:manifestTiles.length,stats,rejected:reasons,cpoSummary:Object.fromEntries([...cpoSummary.entries()].sort((a,b)=>a[0].localeCompare(b[0]))),sourceArchive:{file:'source-locations.json.gz',locationCount:locations.length,evseCount:sourceEvseCount,sha256:sha(sourceGz)},associationBatches:associationDocuments.map(doc=>({batch:doc.batch,cpoCounts:doc.cpoCounts||{},candidateCount:doc.candidateCount,ambiguousExcluded:doc.ambiguousExcluded||0,collisionExcluded:doc.collisionExcluded||0,applied:batchStats.get(doc.batch)?.applied||0,conflicts:batchStats.get(doc.batch)?.conflicts||0})),policy:{nationalFranceIsIdentityHub:true,exactNationalEvseOnly:false,acceptedIdentityModes:['exact_national_irve_evse','curated_irve_location'],curatedMatchRequiresValidatedDistanceNameAddressPowerAndConnectorEvidence:true,electroverseDependency:false,heterogeneousLocationTariffsFailClosed:true,evseScopedTariffOffers:true,explicitDisjointPowerRestrictionRequiredForHeterogeneousTariffs:true,verifiedAppEvidenceForListedEVSEOnly:true,
    verifiedAppEvidenceDoesNotOverrideDirectCpo:true,verifiedAppMappingFailsClosedOnTariffChange:true,
    unsupportedComponentsFailClosed:true,overlayConservation:'all compatible source locations and EVSEs are retained in source-locations.json.gz; tiles contain only matched tariff enrichments'},tiles:manifestTiles};
await fs.writeFile(path.join(OUT,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
const residualGz=zlib.gzipSync(Buffer.from(JSON.stringify({schemaVersion:1,country:'FR',generatedAt:manifest.generatedAt,locations:residualLocations})),{level:9});
await fs.writeFile(path.join(OUT,'residuals.json.gz'),residualGz);
console.log(JSON.stringify(manifest,null,2));
if(stats.publishedOffers<1000)throw new Error(`too few safe Electra platform offers: ${stats.publishedOffers}`);
