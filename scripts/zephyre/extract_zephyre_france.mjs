#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';

const args=Object.fromEntries(process.argv.slice(2).map((v,i,a)=>v.startsWith('--')?[v.slice(2),a[i+1]&&!a[i+1].startsWith('--')?a[i+1]:true]:null).filter(Boolean));
const outPath=String(args.out||'data/zephyre/france/current/zephyre.json.gz');
const summaryPath=String(args.summary||'data/zephyre/france/current/summary.json');
const concurrency=Math.max(1,Math.min(12,Number(args.concurrency||8)));
const irveUrl=String(args.irve||process.env.IRVE_URL||'https://www.data.gouv.fr/api/1/datasets/r/eb76d20a-8501-400e-b336-d85724de5435');
const bff=String(args.bff||process.env.EPOWERDIRECT_BFF||'https://api.services-emobility.com/pay/api');

const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const normEvse=v=>String(v||'').replaceAll('*','').trim().toUpperCase();
const stampOf=x=>String(x?.lastModified||x?.dateMaj||'');

async function fetchJson(url,options={},retry=0){
  try{
    const response=await fetch(url,{...options,headers:{Accept:'application/json','User-Agent':'Tesla-Charge-Companion-Zephyre-Extractor/1.0',...(options.headers||{})}});
    const text=await response.text();
    let body;try{body=JSON.parse(text);}catch{body=text;}
    if((response.status===429||response.status>=500)&&retry<5){
      await sleep(Math.min(15000,750*Math.pow(2,retry)));
      return fetchJson(url,options,retry+1);
    }
    return {ok:response.ok,status:response.status,body};
  }catch(error){
    if(retry<5){await sleep(Math.min(15000,750*Math.pow(2,retry)));return fetchJson(url,options,retry+1);}
    return {ok:false,status:0,body:{networkError:String(error?.message||error)}};
  }
}

async function mapLimit(items,limit,fn){
  const out=new Array(items.length);let cursor=0;
  async function worker(){while(true){const i=cursor++;if(i>=items.length)return;out[i]=await fn(items[i],i);}}
  await Promise.all(Array.from({length:Math.min(limit,items.length)},()=>worker()));
  return out;
}

async function readCsvRows(response,onRow){
  if(!response.body)throw new Error('IRVE response body unavailable');
  const reader=response.body.getReader(),decoder=new TextDecoder();
  let buffer='';
  while(true){
    const {value,done}=await reader.read();
    if(done)break;
    buffer+=decoder.decode(value,{stream:true});
    let newline;
    while((newline=buffer.indexOf('\n'))>=0){
      const line=buffer.slice(0,newline);
      buffer=buffer.slice(newline+1);
      if(line)onRow(parseCsvLine(line));
    }
  }
  buffer+=decoder.decode();
  if(buffer)onRow(parseCsvLine(buffer));
}

function parseCsvLine(line){
  const out=[];let field='',quoted=false;
  for(let i=0;i<line.length;i++){
    const c=line[i];
    if(quoted){
      if(c==='"'){
        if(line[i+1]==='"'){field+='"';i++;}
        else quoted=false;
      }else field+=c;
    }else{
      if(c==='"')quoted=true;
      else if(c===','){out.push(field);field='';}
      else if(c!=='\r')field+=c;
    }
  }
  out.push(field);
  return out;
}

function cleanTariff(tariff){
  if(!tariff||typeof tariff!=='object')return null;
  return {
    currency:tariff.currency||null,
    currentType:tariff.currentType||null,
    invalidationTimestamp:tariff.invalidationTimestamp||null,
    priceComponents:(tariff.priceComponents||[]).map(p=>({
      price:Number.isFinite(Number(p.price))?Number(p.price):null,
      priceUnit:p.priceUnit||null,
      freeParkingCostMinutes:Number(p.freeParkingCostMinutes||0),
      restrictionStartTime:p.restrictionStartTime||null,
      restrictionEndTime:p.restrictionEndTime||null,
      taxAmount:p.taxAmount==null?null:Number(p.taxAmount)
    }))
  };
}

const response=await fetch(irveUrl,{redirect:'follow',headers:{'User-Agent':'Tesla-Charge-Companion-Zephyre-Extractor/1.0'}});
if(!response.ok)throw new Error(`IRVE download failed HTTP ${response.status}`);
const resolvedIrveUrl=response.url;
let header=null,index=null,rawFrZp1Rows=0;
const latestByEvse=new Map();

await readCsvRows(response,row=>{
  if(!header){header=row;index=Object.fromEntries(header.map((name,i)=>[name,i]));return;}
  const evse=normEvse(row[index.id_pdc_itinerance]);
  if(!evse.startsWith('FRZP1'))return;
  rawFrZp1Rows++;
  const item={
    evse,
    evseId:row[index.id_pdc_itinerance]||null,
    stationId:row[index.id_station_itinerance]||null,
    stationLocalId:row[index.id_station_local]||null,
    stationName:row[index.nom_station]||null,
    operator:row[index.nom_operateur]||null,
    address:row[index.adresse_station]||null,
    latitude:Number(row[index.consolidated_latitude]),
    longitude:Number(row[index.consolidated_longitude]),
    nominalPowerKw:Number(row[index.puissance_nominale])||null,
    irveTarification:row[index.tarification]||null,
    dateMaj:row[index.date_maj]||null,
    lastModified:row[index.last_modified]||null,
    datasetId:row[index.datagouv_dataset_id]||null,
    resourceId:row[index.datagouv_resource_id]||null
  };
  if(!Number.isFinite(item.latitude)||!Number.isFinite(item.longitude))return;
  const old=latestByEvse.get(evse);
  if(!old||stampOf(item)>stampOf(old))latestByEvse.set(evse,item);
});

const irve=[...latestByEvse.values()];
const coordinateMap=new Map();
for(const row of irve){
  const key=`${row.latitude.toFixed(6)},${row.longitude.toFixed(6)}`;
  if(!coordinateMap.has(key))coordinateMap.set(key,{latitude:row.latitude,longitude:row.longitude});
}
const coordinates=[...coordinateMap.values()];
const nearbyErrors=[];
const liveByEvse=new Map();
const nearbyCandidatesBySeed=new Map();

const nearby=await mapLimit(coordinates,concurrency,async coord=>{
  const r=await fetchJson(`${bff}/stations/nearby`,{
    method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({latitude:coord.latitude,longitude:coord.longitude})
  });
  if(!r.ok){
    nearbyErrors.push({latitude:coord.latitude,longitude:coord.longitude,http:r.status,error:typeof r.body==='string'?r.body.slice(0,240):r.body});
    return {coord,stations:[]};
  }
  return {coord,stations:Array.isArray(r.body)?r.body:[]};
});

for(const {coord,stations} of nearby){
  const seedKey=`${coord.latitude.toFixed(6)},${coord.longitude.toFixed(6)}`;
  const candidates=[];
  for(const station of stations){
    for(const cp of station?.chargePoints||[]){
      const evse=normEvse(cp?.evseId);
      if(!evse.startsWith('FRZP1'))continue;
      candidates.push({evse,evseId:cp.evseId||null,internalName:cp.name||null,status:cp.evseStatus||null});
      if(!liveByEvse.has(evse)){
        liveByEvse.set(evse,{
          evse,evseId:cp.evseId||null,internalName:cp.name||null,
          status:cp.evseStatus||null,available:cp.available??null,
          multitenantDirectPaymentAvailable:cp.multitenantDirectPaymentAvailable??null,
          paymentMethods:Array.isArray(cp.paymentMethods)?cp.paymentMethods:[],
          maxChargingPowerKw:Number(cp.maxChargingPower)||null,
          nearbyAddress:station.address||null
        });
      }
    }
  }
  nearbyCandidatesBySeed.set(seedKey,candidates);
}

const detailErrors=[];
const live=[...liveByEvse.values()].filter(x=>x.internalName);
const stations=(await mapLimit(live,concurrency,async item=>{
  const r=await fetchJson(`${bff}/stations/chargepoint/${encodeURIComponent(item.internalName)}`);
  if(!r.ok){
    detailErrors.push({evse:item.evse,internalName:item.internalName,http:r.status,error:typeof r.body==='string'?r.body.slice(0,240):r.body});
    return null;
  }
  const station=r.body||{},chargePoints=Array.isArray(station.chargePoints)?station.chargePoints:[];
  const cp=chargePoints.find(x=>x?.name===item.internalName)||chargePoints.find(x=>normEvse(x?.evseId)===item.evse);
  if(!cp){detailErrors.push({evse:item.evse,internalName:item.internalName,error:'charge_point_missing_in_detail'});return null;}
  return {
    evse:normEvse(cp.evseId),evseId:cp.evseId||item.evseId,internalName:cp.name||item.internalName,
    provider:station.provider?{id:station.provider.id||null,name:station.provider.name||null}:null,
    address:station.address||item.nearbyAddress||null,vat:station.vat??null,currency:station.currency||cp?.tariff?.currency||null,
    status:cp.evseStatus||item.status||null,available:cp.available??item.available??null,
    multitenantDirectPaymentAvailable:cp.multitenantDirectPaymentAvailable??item.multitenantDirectPaymentAvailable??null,
    paymentMethods:Array.isArray(cp.paymentMethods)?cp.paymentMethods:item.paymentMethods,
    maxChargingPowerKw:Number(cp.maxChargingPower)||item.maxChargingPowerKw||null,
    tariff:cleanTariff(cp.tariff),
    irve:latestByEvse.get(normEvse(cp.evseId))||null
  };
})).filter(Boolean).sort((a,b)=>a.evse.localeCompare(b.evse));

const resolvedEvses=new Set(stations.map(x=>x.evse));
const unresolved=irve.filter(x=>!resolvedEvses.has(x.evse)).map(row=>{
  const key=`${row.latitude.toFixed(6)},${row.longitude.toFixed(6)}`;
  return {...row,reason:'not_exposed_by_current_epowerdirect_fail_closed',nearbyCandidatesAtSeed:(nearbyCandidatesBySeed.get(key)||[]).filter(x=>x.evse!==row.evse)};
});

const unresolvedByDataset={};
for(const row of unresolved){const k=row.datasetId||'unknown';unresolvedByDataset[k]=(unresolvedByDataset[k]||0)+1;}
const direct=stations.filter(x=>x.multitenantDirectPaymentAvailable===true&&x.tariff?.priceComponents?.some(p=>Number(p.price)>0));
const providers=[...new Set(stations.map(x=>x.provider?.name).filter(Boolean))].sort();

const summary={
  schemaVersion:1,generatedAt:new Date().toISOString(),country:'FR',network:'Zephyre',partyId:'FR*ZP1',
  source:{irveRequestedUrl:irveUrl,irveResolvedUrl:resolvedIrveUrl,bff,nearby:'POST /stations/nearby',detail:'GET /stations/chargepoint/{internalName}'},
  rawFrZp1Rows,irveUniqueEvse:irve.length,seedCoordinates:coordinates.length,
  liveDetailStations:stations.length,liveDirectEvse:direct.length,
  liveTariffPresent:stations.filter(x=>x.tariff?.priceComponents?.length).length,
  directPaymentEnabled:stations.filter(x=>x.multitenantDirectPaymentAvailable===true).length,
  nearbyErrors:nearbyErrors.length,detailErrors:detailErrors.length,unresolvedIrveEvse:unresolved.length,
  unresolvedByDataset,providers,
  policy:{directRankable:'exact FR*ZP1 EVSE returned by current ePowerDirect + multitenantDirectPaymentAvailable=true + positive tariff component',nationalConstantAllowed:false,sameSiteExtrapolationAllowed:false,unresolved:'fail_closed_then_Electra_then_Electroverse',bindingPricingOfferTokenStored:false}
};

const output={schemaVersion:1,country:'FR',network:'Zephyre',partyId:'FR*ZP1',generatedAt:summary.generatedAt,sources:summary.source,summary,stations,unresolved,errors:{nearby:nearbyErrors,detail:detailErrors}};

fs.mkdirSync(path.dirname(outPath),{recursive:true});
fs.mkdirSync(path.dirname(summaryPath),{recursive:true});
fs.writeFileSync(outPath,zlib.gzipSync(Buffer.from(JSON.stringify(output)),{level:9}));
fs.writeFileSync(summaryPath,JSON.stringify(summary,null,2)+'\n');
console.log(JSON.stringify(summary,null,2));
console.log(`wrote ${outPath}`);
console.log(`wrote ${summaryPath}`);
