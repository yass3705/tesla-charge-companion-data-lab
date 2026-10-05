import fs from 'node:fs/promises';
import fss from 'node:fs';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import path from 'node:path';

const OUT=process.argv[2]||'data/platforms/electra/france';
const NATIONAL=process.argv[3]||'stable/v9-production-runtime/data/v9/france-static/all.json.gz';
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
  const base={energy:0,time:0,parking:0,flat:0},windows=new Map(),duration=[];
  const unsupported=[];
  for(const el of t?.elements||[]){
    const rr=el?.restrictions||{},values={energy:0,time:0,parking:0,flat:0},present=new Set();
    for(const pc of el?.priceComponents||[]){
      const kind=componentKind(pc?.type),raw=Number(pc?.price);
      if(!kind||!Number.isFinite(raw)){unsupported.push(pc?.type||'unknown');continue;}
      if(kind==='congestion'){unsupported.push('CONGESTION_TIME');continue;}
      let value=raw;if(kind==='time'||kind==='parking')value/=60;
      values[kind]+=value;present.add(kind);
    }
    if(unsupported.length)return null;
    const start=rr.startTime||null,end=rr.endTime||null;
    const minDur=Number(rr.minDuration);
    const threshold=Number.isFinite(minDur)&&minDur>0?minDur/60:0;
    const days=Array.isArray(rr.dayOfWeek)&&rr.dayOfWeek.length?rr.dayOfWeek.map(x=>weekdays[x]).filter(Number.isInteger):null;
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
const nationalEvse=new Set();
for(const row of nationalRows)for(const cfg of row?.[8]||[])for(const id of Array.isArray(cfg?.[6])?cfg[6]:[])nationalEvse.add(norm(id));

const first=await page(0);if(!first.data)throw new Error('first Electra page failed '+JSON.stringify(first.error));
const total=first.data.totalCount,totalPages=Math.ceil(total/PAGE_SIZE),locations=[];
const failures=[];
function acceptItems(items){for(const x of items||[])if(x?.country==='FR'&&compatible(x))locations.push(x);}
acceptItems(first.data.items);
let next=1;
async function worker(){while(true){const i=next++;if(i>=totalPages)return;const r=await page(i*PAGE_SIZE);if(!r.data)failures.push({page:i,...r});else acceptItems(r.data.items);if(i%250===0)console.log(`Electra ${i}/${totalPages}, FR=${locations.length}, failures=${failures.length}`);}}
await Promise.all(Array.from({length:CONCURRENCY},worker));
if(failures.length)throw new Error(`Electra extraction has ${failures.length} failed pages; refusing snapshot`);

const tiles=new Map(),residualLocations=[],reasons={},cpoSummary=new Map(),stats={franceCompatibleLocations:locations.length,locationsWithNationalEvse:0,publishedLocations:0,publishedEvseIds:0,publishedOffers:0};
for(const x of locations){
  const cpo=String(x.cpo?.name||'CPO inconnu');
  if(!cpoSummary.has(cpo))cpoSummary.set(cpo,{cpo,totalCompatibleLocations:0,locationsWithNationalEvse:0,matchedEvseIds:0,publishedLocations:0,publishedEvseIds:0,rejected:{}});
  const cs=cpoSummary.get(cpo);cs.totalCompatibleLocations++;
  const reject=reason=>{reasons[reason]=(reasons[reason]||0)+1;cs.rejected[reason]=(cs.rejected[reason]||0)+1;residualLocations.push({electraLocationId:String(x.id),name:x.name||null,address:x.address||null,city:x.city||null,postalCode:x.postalCode||null,country:x.country||null,coordinates:x.coordinates||null,connectorTypes:x.connectorTypes||[],maxPower:x.maxPower??null,cpo,operator:x.operator?.name||null,reason,evses:(x.evses||[]).map(e=>({id:e.id||null,evseId:e.evseId||null,status:e.status||null,physicalReference:e.physicalReference||null}))});};
  const exact=[...new Set((x.evses||[]).map(e=>e?.evseId).filter(Boolean).filter(id=>nationalEvse.has(norm(id))))];
  if(!exact.length){reject('no_national_evse');continue;}
  stats.locationsWithNationalEvse++;cs.locationsWithNationalEvse++;cs.matchedEvseIds+=exact.length;
  const compiled=(x.chargeTariffs||[]).map(compileTariff);
  if(!compiled.length){reject('no_tariff');continue;}
  if(compiled.some(v=>!v)){reject('unsupported_tariff');continue;}
  const uniq=[...new Map(compiled.map(v=>[signature(v),v])).values()];
  if(uniq.length!==1){reject('heterogeneous_location_tariffs');continue;}
  const lat=Number(x.coordinates?.latitude),lon=Number(x.coordinates?.longitude);
  if(!Number.isFinite(lat)||!Number.isFinite(lon)){reject('no_coordinates');continue;}
  const offer={
    id:`electra-platform:${x.id}`,provider:'Electra',countries:['FR'],currency:uniq[0].rules?.[0]?.currency||'EUR',priority:82,
    evseIds:exact,pricing:uniq[0],metadata:{verified:true,identityMode:'exact_national_irve_evse',electraLocationId:String(x.id),cpo:x.cpo?.name||null,operator:x.operator?.name||null,source:'Electra eMSP GraphQL'}
  };
  const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);
  tiles.get(id).push(offer);stats.publishedLocations++;stats.publishedEvseIds+=exact.length;stats.publishedOffers++;cs.publishedLocations++;cs.publishedEvseIds+=exact.length;
}
const manifestTiles=[];
for(const [id,offers] of [...tiles.entries()].sort((a,b)=>a[0].localeCompare(b[0]))){
  const payload={schemaVersion:1,country:'FR',emspOffers:offers};
  const gz=zlib.gzipSync(Buffer.from(JSON.stringify(payload)),{level:9});
  const file=`${id}.json.gz`;await fs.writeFile(path.join(OUT,file),gz);
  const [a,b]=id.slice(2).split('_').map(Number);
  manifestTiles.push({id,file,minLat:a*TILE,maxLat:(a+1)*TILE,minLon:b*TILE,maxLon:(b+1)*TILE,count:offers.length,bytes:gz.length,sha256:sha(gz)});
}
const manifest={schemaVersion:1,dataset:'electra-france-platform-national-evse-overlay',generatedAt:new Date().toISOString(),source:{endpoint:URL,globalTotalCount:total,totalPages},country:'FR',tileSizeDegrees:TILE,tileCount:manifestTiles.length,stats,rejected:reasons,cpoSummary:Object.fromEntries([...cpoSummary.entries()].sort((a,b)=>a[0].localeCompare(b[0]))),policy:{nationalFranceIsIdentityHub:true,exactNationalEvseOnly:true,electroverseDependency:false,heterogeneousLocationTariffsFailClosed:true,unsupportedComponentsFailClosed:true},tiles:manifestTiles};
await fs.writeFile(path.join(OUT,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
const residualGz=zlib.gzipSync(Buffer.from(JSON.stringify({schemaVersion:1,country:'FR',generatedAt:manifest.generatedAt,locations:residualLocations})),{level:9});
await fs.writeFile(path.join(OUT,'residuals.json.gz'),residualGz);
console.log(JSON.stringify(manifest,null,2));
if(stats.publishedOffers<1000)throw new Error(`too few safe Electra platform offers: ${stats.publishedOffers}`);
