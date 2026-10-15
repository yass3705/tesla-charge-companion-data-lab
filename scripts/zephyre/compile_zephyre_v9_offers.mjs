#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';

const args=Object.fromEntries(process.argv.slice(2).map((v,i,a)=>v.startsWith('--')?[v.slice(2),a[i+1]&&!a[i+1].startsWith('--')?a[i+1]:true]:null).filter(Boolean));
const snapshotPath=String(args.snapshot||'data/zephyre/france/current/zephyre.json.gz');
const outPath=String(args.out||'v9-production-runtime/data/v9/france-zephyre-offers.json');

function readSnapshot(p){const b=fs.readFileSync(p);return JSON.parse((p.endsWith('.gz')?zlib.gunzipSync(b):b).toString('utf8'));}
const clean=v=>{const n=Number(v);return Number.isFinite(n)?Number(n.toFixed(9)):null;};
const positive=v=>typeof v==='number'&&Number.isFinite(v)&&v>0;

const snapshot=readSnapshot(snapshotPath);
if(snapshot?.country!=='FR'||snapshot?.network!=='Zephyre')throw new Error('Unexpected Zephyre snapshot');
const stations=Array.isArray(snapshot.stations)?snapshot.stations:[];
const rankable=stations.filter(s=>s?.multitenantDirectPaymentAvailable===true&&Array.isArray(s?.tariff?.priceComponents)&&s.tariff.priceComponents.some(p=>positive(clean(p?.price))));
if(!rankable.length)throw new Error('No rankable Zephyre direct EVSEs');

function normalizeComponents(tariff){
  return (tariff?.priceComponents||[]).map(p=>({
    priceUnit:String(p?.priceUnit||'').toUpperCase(),
    price:clean(p?.price),
    freeParkingCostMinutes:Math.max(0,clean(p?.freeParkingCostMinutes)||0),
    restrictionStartTime:p?.restrictionStartTime||null,
    restrictionEndTime:p?.restrictionEndTime||null,
    taxAmount:p?.taxAmount==null?null:clean(p.taxAmount)
  })).sort((a,b)=>a.priceUnit.localeCompare(b.priceUnit)||(a.price??0)-(b.price??0));
}
function signature(station){return JSON.stringify({currency:String(station?.tariff?.currency||station?.currency||'EUR').toUpperCase(),currentType:station?.tariff?.currentType||null,components:normalizeComponents(station.tariff)});}

const groups=new Map();
for(const station of rankable){const key=signature(station);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(station);}

function pricingFromSignature(def){
  const rule={scope:'allDay',start:'00:00',end:'24:00',billing:'kwh',currency:def.currency||'EUR',pricePerKwh:0};
  const pricing={type:'rules',rules:[rule]};
  let recognized=0;
  for(const c of def.components){
    if(c.restrictionStartTime||c.restrictionEndTime)throw new Error(`Unsupported Zephyre component restriction ${JSON.stringify(c)}`);
    if(!positive(c.price))continue;
    switch(c.priceUnit){
      case 'CHARGING_KWH':rule.pricePerKwh=c.price;recognized++;break;
      case 'CHARGING_TIME':rule.chargingTimePerMinuteEur=c.price;recognized++;break;
      case 'CHARGING_SESSION':rule.sessionFeeEur=c.price;recognized++;break;
      case 'PARKING_TIME':
        if(pricing.postChargeFee)throw new Error('Multiple Zephyre PARKING_TIME components are not yet supported');
        pricing.postChargeFee={eurPerMinute:c.price,graceMinutes:c.freeParkingCostMinutes||0};recognized++;break;
      case 'PARKING_SESSION':
        throw new Error('Zephyre PARKING_SESSION requires an explicit V9 post-charge flat-fee model; refusing unsafe approximation');
      default:throw new Error(`Unknown Zephyre price unit ${c.priceUnit}`);
    }
  }
  if(!recognized)throw new Error(`No recognized positive component in ${JSON.stringify(def)}`);
  return pricing;
}

const directOffers=[];
let i=0;
for(const [key,members] of [...groups.entries()].sort((a,b)=>a[0].localeCompare(b[0]))){
  const def=JSON.parse(key);
  const evseIds=[...new Set(members.map(s=>s.evseId).filter(Boolean))].sort();
  const internalNames=[...new Set(members.map(s=>s.internalName).filter(Boolean))].sort();
  if(!evseIds.length)continue;
  const id=`zephyre-direct-profile-${String(++i).padStart(2,'0')}`;
  directOffers.push({
    id,selectionId:id,provider:'Zephyre direct',
    operatorAliases:['Zephyre','Zephyre SAS','FR*ZP1','FRZP1'],
    countries:['FR'],currency:def.currency||'EUR',priority:132,
    pricing:pricingFromSignature(def),
    source:'ePowerDirect /pay/api/stations/chargepoint/{internalName}',
    directOperatorOnly:true,verifiedScope:'exact_evse',defaultSelected:false,evseIds,
    metadata:{pricingContext:'anonymous_direct_payment',currentType:def.currentType,exactEvseCount:evseIds.length,internalNames,rawPriceComponents:def.components,fallback:'Electra then Electroverse for unresolved/non-exposed EVSEs',priceBasis:'ePowerDirect displayed direct price'}
  });
}

const exactEvseIds=[...new Set(directOffers.flatMap(x=>x.evseIds))];
const output={
  schemaVersion:1,country:'FR',generatedAt:new Date().toISOString(),mode:'verified_zephyre_direct',
  policy:{source:'Vaylens ePowerDirect first-party public BFF joined to official data.gouv national IRVE',resolver:snapshot?.sources||null,exactEvseRequired:true,directPaymentRequired:true,nationalConstantAllowed:false,sameSiteExtrapolationAllowed:false,fallbackOrder:['Electra','Electroverse'],bindingPricingOfferTokenStored:false},
  directOffers,subscriptionOffers:[],
  sourceEvidence:{summary:snapshot.summary||{},liveDirectEvse:rankable.length,exactEvseIds:exactEvseIds.length,priceProfiles:directOffers.length}
};
if(directOffers.length<5)throw new Error(`Unexpectedly few Zephyre price profiles: ${directOffers.length}`);
if(exactEvseIds.length<100)throw new Error(`Unexpectedly low Zephyre EVSE coverage: ${exactEvseIds.length}`);
if(directOffers.some(o=>!o.evseIds.length||o.verifiedScope!=='exact_evse'||o.directOperatorOnly!==true))throw new Error('Invalid Zephyre direct offer scope');

fs.mkdirSync(path.dirname(outPath),{recursive:true});
fs.writeFileSync(outPath,JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify({directOffers:directOffers.length,exactEvseIds:exactEvseIds.length,out:outPath},null,2));
