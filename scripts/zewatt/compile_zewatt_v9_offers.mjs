#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';

const args=Object.fromEntries(process.argv.slice(2).map((v,i,a)=>v.startsWith('--')?[v.slice(2),a[i+1]&&!a[i+1].startsWith('--')?a[i+1]:true]:null).filter(Boolean));
const snapshotPath=String(args.snapshot||'data/zewatt/france/current/zewatt.json.gz');
const outPath=String(args.out||'v9-production-runtime/data/v9/france-zewatt-offers.json');

function readSnapshot(p){
  const buf=fs.readFileSync(p);
  const raw=p.endsWith('.gz')?zlib.gunzipSync(buf):buf;
  return JSON.parse(raw.toString('utf8'));
}
const cleanNumber=v=>{
  if(v===null||v===undefined||v==='') return null;
  const n=Number(v); return Number.isFinite(n)?Number(n.toFixed(9)):null;
};
const positive=v=>typeof v==='number'&&Number.isFinite(v)&&v>0;
const compact=s=>String(s||'').replace(/[^A-Za-z0-9]+/g,'-').replace(/^-+|-+$/g,'').toLowerCase();

const snapshot=readSnapshot(snapshotPath);
if(snapshot?.country!=='FR'||snapshot?.network!=='Ze-Watt') throw new Error('Unexpected Ze-Watt snapshot');
const stations=Array.isArray(snapshot.stations)?snapshot.stations:[];
const directStations=stations.filter(s=>s?.ok===true&&s?.visitorStripe===true&&s?.hasPositivePrice===true);
if(!directStations.length) throw new Error('No rankable Ze-Watt visitor/card stations in snapshot');

function normalizeProfile(p={}){
  return {
    perKwhEurTtc:cleanNumber(p.perKwhEurTtc),
    perMinuteEurTtc:cleanNumber(p.perMinuteEurTtc),
    postChargePerMinuteEurTtc:cleanNumber(p.postChargePerMinuteEurTtc),
    postChargeGraceMinutes:cleanNumber(p.postChargeGraceMinutes),
    connectedTimePerMinuteEurTtc:cleanNumber(p.connectedTimePerMinuteEurTtc),
    connectedTimeGraceMinutes:cleanNumber(p.connectedTimeGraceMinutes),
    perSessionEurTtc:cleanNumber(p.perSessionEurTtc)
  };
}
function profileKey(s){return JSON.stringify(normalizeProfile(s.normalizedPrice||{}));}
const groups=new Map();
for(const s of directStations){
  const key=profileKey(s);
  if(!groups.has(key)) groups.set(key,[]);
  groups.get(key).push(s);
}

function pricingFromProfile(p){
  const rule={
    scope:'allDay',
    start:'00:00',
    end:'24:00',
    billing:'kwh',
    currency:'EUR',
    pricePerKwh:positive(p.perKwhEurTtc)?p.perKwhEurTtc:0
  };
  if(positive(p.perSessionEurTtc)) rule.sessionFeeEur=p.perSessionEurTtc;
  if(positive(p.perMinuteEurTtc)) rule.chargingTimePerMinuteEur=p.perMinuteEurTtc;
  if(positive(p.connectedTimePerMinuteEurTtc)){
    rule.connectedTimePerMinuteAfterFreeEur=p.connectedTimePerMinuteEurTtc;
    rule.connectedTimeFreeMinutes=Math.max(0,Math.round(p.connectedTimeGraceMinutes||0));
  }
  const pricing={type:'rules',rules:[rule]};
  if(positive(p.postChargePerMinuteEurTtc)){
    pricing.postChargeFee={
      eurPerMinute:p.postChargePerMinuteEurTtc,
      graceMinutes:Math.max(0,Math.round(p.postChargeGraceMinutes||0))
    };
  }
  return pricing;
}

const directOffers=[];
let n=0;
for(const [key, members] of [...groups.entries()].sort((a,b)=>a[0].localeCompare(b[0]))){
  const profile=JSON.parse(key);
  const evseIds=[...new Set(members.flatMap(s=>(s?.static?.evses||[]).map(e=>e?.idPdcItinerance).filter(Boolean)))].sort();
  const serials=[...new Set(members.map(s=>s.serial).filter(Boolean))].sort();
  if(!evseIds.length) continue;
  const id=`zewatt-direct-profile-${String(++n).padStart(2,'0')}`;
  directOffers.push({
    id,
    selectionId:id,
    provider:'Ze-Watt direct',
    operatorAliases:['Ze-Watt','ZE-WATT','ZE WATT','FR*ZWO','FRZWO'],
    countries:['FR'],
    currency:'EUR',
    priority:132,
    pricing:pricingFromProfile(profile),
    source:'my.ze-watt.com /api/stripe-payment/v1/charge-point/{serial}/company',
    directOperatorOnly:true,
    verifiedScope:'exact_evse',
    defaultSelected:false,
    evseIds,
    metadata:{
      visitorStripeRequired:true,
      pricingContext:'anonymous_guest_card',
      stationSerials:serials,
      exactStationCount:serials.length,
      exactEvseCount:evseIds.length,
      structuredTtcProfile:profile,
      fallback:'Electra then Electroverse for non-guest or unresolved stations',
      priceMinNotRanked:true,
      priceMinReason:'retained in raw snapshot only; not proven to be a tariff component'
    }
  });
}

const output={
  schemaVersion:1,
  country:'FR',
  generatedAt:new Date().toISOString(),
  mode:'verified_zewatt_direct',
  policy:{
    source:'Ze-Watt first-party public guest/card company endpoint joined to official data.gouv static inventory',
    staticResource:snapshot?.sources?.staticResource||null,
    dynamicResource:snapshot?.sources?.dynamicResource||null,
    resolver:snapshot?.sources?.companyEndpoint||null,
    exactEvseRequired:true,
    visitorStripeRequired:true,
    authenticatedUserContextSeparated:true,
    roamingPricesExcluded:true,
    fallbackOrder:['Electra','Electroverse'],
    priceMinRanked:false
  },
  directOffers,
  subscriptionOffers:[],
  sourceEvidence:{
    summary:snapshot.summary||{},
    directGuestStations:directStations.length,
    exactEvseIds:[...new Set(directOffers.flatMap(x=>x.evseIds))].length,
    priceProfiles:directOffers.length
  }
};

if(directOffers.length<30) throw new Error(`Unexpectedly few Ze-Watt direct profiles: ${directOffers.length}`);
if(output.sourceEvidence.exactEvseIds<500) throw new Error(`Unexpectedly low Ze-Watt EVSE coverage: ${output.sourceEvidence.exactEvseIds}`);
if(directOffers.some(o=>!o.evseIds.length)) throw new Error('Ze-Watt offer without exact EVSE IDs');

fs.mkdirSync(path.dirname(outPath),{recursive:true});
fs.writeFileSync(outPath,JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify({
  directOffers:directOffers.length,
  directGuestStations:directStations.length,
  exactEvseIds:output.sourceEvidence.exactEvseIds,
  out:outPath
},null,2));
