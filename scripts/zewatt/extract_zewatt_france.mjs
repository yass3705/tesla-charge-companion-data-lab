#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';

const args = Object.fromEntries(process.argv.slice(2).map((v,i,a)=>v.startsWith('--')?[v.slice(2),a[i+1]&&!a[i+1].startsWith('--')?a[i+1]:true]:null).filter(Boolean));
const outPath = String(args.out || 'data/zewatt/france/current/zewatt.json.gz');
const summaryPath = String(args.summary || 'data/zewatt/france/current/summary.json');
const concurrency = Math.max(1, Math.min(8, Number(args.concurrency || 4)));
const staticResource = '1189bf16-bad6-410b-93c5-8dad856ae49c';
const dynamicResource = '5a9a3832-7461-4eab-b945-b856df055517';
const tabularBase = 'https://tabular-api.data.gouv.fr/api/resources';
const zeWattBase = 'https://my.ze-watt.com/api/stripe-payment/v1';

const sleep = ms => new Promise(r=>setTimeout(r,ms));

async function fetchJson(url, retry=0){
  try{
    const response = await fetch(url,{headers:{Accept:'application/json','User-Agent':'Tesla-Charge-Companion-ZeWatt-Extractor/1.0'}});
    const text = await response.text();
    let body; try{body=JSON.parse(text);}catch{body=text;}
    if((response.status===429 || response.status>=500) && retry<5){
      await sleep(Math.min(15000,750*Math.pow(2,retry)));
      return fetchJson(url,retry+1);
    }
    return {ok:response.ok,status:response.status,body};
  }catch(error){
    if(retry<5){
      await sleep(Math.min(15000,750*Math.pow(2,retry)));
      return fetchJson(url,retry+1);
    }
    return {ok:false,status:0,body:{networkError:String(error?.message||error)}};
  }
}

async function fetchTabular(resource){
  const rows=[];
  for(let page=1;page<100;page++){
    const url=`${tabularBase}/${resource}/data/?page=${page}&page_size=200`;
    const r=await fetchJson(url);
    if(!r.ok) throw new Error(`data.gouv tabular ${resource} page=${page} HTTP ${r.status}`);
    const batch=Array.isArray(r.body?.data)?r.body.data:[];
    rows.push(...batch);
    const total=Number(r.body?.meta?.total||rows.length);
    console.log(`tabular resource=${resource} page=${page} rows=${batch.length} total=${rows.length}/${total}`);
    if(rows.length>=total || batch.length===0) break;
  }
  return rows;
}

function serialFromStatic(row){
  const local=String(row?.id_station_local||'').trim().toUpperCase();
  if(/^ZW\d+$/.test(local)) return local;
  const itin=String(row?.id_station_itinerance||'').trim().toUpperCase();
  const m=itin.match(/(ZW\d+)/);
  return m?.[1] || null;
}
function numberOrNull(v){
  const n=Number(v);
  return Number.isFinite(n)?n:null;
}
function normalizePrice(p={}){
  return {
    perKwhEurTtc:numberOrNull(p.per_kwh_price),
    perMinuteEurTtc:numberOrNull(p.per_minute_price),
    postChargePerMinuteEurTtc:numberOrNull(p.per_minute_parking_price),
    postChargeGraceMinutes:numberOrNull(p.parking_delay_in_minutes),
    connectedTimePerMinuteEurTtc:numberOrNull(p.transaction_time_per_minute_parking_price),
    connectedTimeGraceMinutes:numberOrNull(p.transaction_time_parking_delay_in_minutes),
    perSessionEurTtc:numberOrNull(p.per_session_price)
  };
}
function hasPositivePrice(p){return Object.entries(p).some(([k,v])=>!k.toLowerCase().includes('grace') && typeof v==='number' && v>0);}

const staticRows=await fetchTabular(staticResource);
const dynamicRows=await fetchTabular(dynamicResource);

const bySerial=new Map();
const unresolvedStatic=[];
for(const row of staticRows){
  const serial=serialFromStatic(row);
  if(!serial){unresolvedStatic.push(row);continue;}
  if(!bySerial.has(serial)) bySerial.set(serial,[]);
  bySerial.get(serial).push(row);
}
const serials=[...bySerial.keys()].sort();
console.log(`static rows=${staticRows.length} serials=${serials.length} unresolvedStatic=${unresolvedStatic.length}`);

const companyResults=[];
let cursor=0, done=0;
async function worker(){
  while(true){
    const i=cursor++; if(i>=serials.length) return;
    const serial=serials[i];
    const r=await fetchJson(`${zeWattBase}/charge-point/${encodeURIComponent(serial)}/company`);
    if(r.ok && r.body && typeof r.body==='object'){
      const rawPrice=r.body.json_ttc_price_for_legal_compliance||{};
      const normalizedPrice=normalizePrice(rawPrice);
      companyResults.push({
        serial,
        ok:true,
        http:r.status,
        name:r.body.name??null,
        pk:r.body.pk??null,
        visitorStripe:r.body.visitor_stripe===true,
        visitorGireve:r.body.visitor_gireve===true,
        priceTtcText:r.body.price_ttc??null,
        priceMinEur:numberOrNull(r.body.price_min),
        normalizedPrice,
        hasPositivePrice:hasPositivePrice(normalizedPrice),
        allowRegistration:r.body.allow_registration??null,
        connectors:Array.isArray(r.body.connectors)?r.body.connectors.map(c=>({
          pk:c.pk??null,ocppId:c.ocpp_id??null,currentAmp:c.current_amp??null,
          connectorType:c.connector_type??null,connectorPhase:c.connector_phase??null,
          available:c.available??null,bookable:c.bookable??null,status:c.status??null
        })):[]
      });
    }else{
      companyResults.push({serial,ok:false,http:r.status,error:typeof r.body==='string'?r.body:r.body?.detail??r.body?.networkError??null});
    }
    done++;
    if(done%50===0 || done===serials.length) console.log(`company ${done}/${serials.length}`);
    await sleep(125);
  }
}
await Promise.all(Array.from({length:concurrency},()=>worker()));
companyResults.sort((a,b)=>a.serial.localeCompare(b.serial));

const dynamicByStation=new Map();
for(const row of dynamicRows){
  const id=String(row?.id_pdc_itinerance||'').toUpperCase();
  const m=id.match(/(ZW\d+)/); const serial=m?.[1];
  if(!serial) continue;
  if(!dynamicByStation.has(serial)) dynamicByStation.set(serial,[]);
  dynamicByStation.get(serial).push({
    idPdcItinerance:row.id_pdc_itinerance??null,
    state:row.etat_pdc??null,
    occupancy:row.occupation_pdc??null,
    timestamp:row.horodatage??null
  });
}

const stations=companyResults.map(c=>{
  const rows=bySerial.get(c.serial)||[];
  const evses=rows.map(r=>({
    idPdcItinerance:r.id_pdc_itinerance??null,
    nominalPowerW:r.puissance_nominale??null,
    type2:r.prise_type_2??null,
    comboCcs:r.prise_type_combo_ccs??null,
    chademo:r.prise_type_chademo??null,
    ef:r.prise_type_ef??null,
    address:r.adresse_station??null,
    coordinates:r.coordonneesXY??null,
    access:r.condition_acces??null,
    hours:r.horaires??null,
    staticUpdatedAt:r.date_maj??null
  }));
  return {...c,static:{
    stationIdItinerance:rows[0]?.id_station_itinerance??null,
    stationLocalId:rows[0]?.id_station_local??null,
    stationName:rows[0]?.nom_station??null,
    evses
  },dynamic:dynamicByStation.get(c.serial)||[]};
});

const ok=stations.filter(x=>x.ok);
const directGuest=ok.filter(x=>x.visitorStripe && x.hasPositivePrice);
const visitorStripeNoPositive=ok.filter(x=>x.visitorStripe && !x.hasPositivePrice);
const accountOrRoamingOnly=ok.filter(x=>!x.visitorStripe);
const errors=stations.filter(x=>!x.ok);
const uniquePriceProfiles=new Map();
for(const s of directGuest){
  const key=JSON.stringify(s.normalizedPrice);
  if(!uniquePriceProfiles.has(key)) uniquePriceProfiles.set(key,{price:s.normalizedPrice,stations:[]});
  uniquePriceProfiles.get(key).stations.push(s.serial);
}

const summary={
  schemaVersion:1,
  generatedAt:new Date().toISOString(),
  source:{
    staticResource,dynamicResource,
    companyEndpoint:'https://my.ze-watt.com/api/stripe-payment/v1/charge-point/{serial}/company'
  },
  staticRows:staticRows.length,
  dynamicRows:dynamicRows.length,
  uniqueSerials:serials.length,
  unresolvedStaticRows:unresolvedStatic.length,
  companyOk:ok.length,
  companyErrors:errors.length,
  directGuestStations:directGuest.length,
  visitorStripeNoPositivePrice:visitorStripeNoPositive.length,
  accountOrRoamingOnlyStations:accountOrRoamingOnly.length,
  uniqueDirectGuestPriceProfiles:uniquePriceProfiles.size,
  policy:{
    directRankable:'visitor_stripe=true AND positive structured TTC component',
    visitorStripeFalse:'not anonymous direct; preserve evidence and use TCC fallback unless a separate authenticated direct context is intentionally selected',
    fallbackOrder:['Electra','Electroverse'],
    roamingNotDirect:true
  }
};

const output={
  schemaVersion:1,
  country:'FR',
  network:'Ze-Watt',
  generatedAt:summary.generatedAt,
  sources:summary.source,
  summary,
  directGuestProfiles:[...uniquePriceProfiles.values()].map(x=>({...x,stations:x.stations.sort()})),
  stations,
  unresolvedStaticRows:unresolvedStatic
};

fs.mkdirSync(path.dirname(outPath),{recursive:true});
fs.mkdirSync(path.dirname(summaryPath),{recursive:true});
fs.writeFileSync(outPath,zlib.gzipSync(Buffer.from(JSON.stringify(output)),{level:9}));
fs.writeFileSync(summaryPath,JSON.stringify(summary,null,2)+'\n');
console.log(JSON.stringify(summary,null,2));
console.log(`wrote ${outPath}`);
console.log(`wrote ${summaryPath}`);
