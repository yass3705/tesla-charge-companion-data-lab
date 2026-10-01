#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';

const args=Object.fromEntries(process.argv.slice(2).map((v,i,a)=>v.startsWith('--')?[v.slice(2),a[i+1]&&!a[i+1].startsWith('--')?a[i+1]:true]:null).filter(Boolean));
const currentDir=String(args.current||'data/loadmotion/france/current');
const outPath=String(args.out||'v9-production-runtime/data/v9/france-loadmotion-offers.json');
const tenants=['yes55','loadstations','reveo','mobisdec'];
const missing=tenants.filter(t=>!fs.existsSync(path.join(currentDir,`${t}.json.gz`)));
if(missing.length){console.log(`[loadmotion compiler] missing snapshots (${missing.join(', ')}); keeping existing ${outPath}`);process.exit(0);}
const readGz=p=>JSON.parse(zlib.gunzipSync(fs.readFileSync(p)).toString('utf8'));
const current=Object.fromEntries(tenants.map(t=>[t,readGz(path.join(currentDir,`${t}.json.gz`))]));
const clean=v=>String(v??'').trim();
const round=v=>v==null?null:Number(Number(v).toFixed(9));
const compactId=v=>clean(v).toUpperCase().replace(/[^A-Z0-9]/g,'');

function baseRule(){return{scope:'allDay',start:'00:00',end:'24:00',billing:'kwh',currency:'EUR',pricePerKwh:0};}
function parkingFeeFromDefinition(def,rule){
  const dim=def?.dimensions?.parkingTime;
  if(!dim?.active)return null;
  const fee={eurPerMinute:round(Number(dim.price||0)/60),graceMinutes:Math.max(0,Math.round(Number(dim.freeMins||0)))};
  if(rule.scope==='timeWindow'&&rule.start&&rule.end&&!(rule.start==='00:00'&&rule.end==='24:00'))fee.exemptLocalWindows=[{start:rule.end==='24:00'?'00:00':rule.end,end:rule.start}];
  return fee;
}
function ruleFromDefinition(def){
  const r=baseRule(),dims=def?.dimensions||{},restr=def?.restrictions||{},stat=def?.staticRestrictions||{};
  if(restr.timeFrom||restr.timeTo){r.scope='timeWindow';r.start=restr.timeFrom||'00:00';r.end=restr.timeTo||'24:00';}
  if(dims.energy?.active)r.pricePerKwh=round(dims.energy.price);
  if(dims.flatFee?.active)r.sessionFeeEur=round(dims.flatFee.price);
  if(dims.chargingTime?.active)r.chargingTimePerMinuteEur=round(Number(dims.chargingTime.price||0)/60);
  if(dims.sessionTime?.active){r.connectedTimePerMinuteAfterFreeEur=round(Number(dims.sessionTime.price||0)/60);r.connectedTimeFreeMinutes=Math.max(0,Math.round(Number(dims.sessionTime.freeMins||0)));}
  return{rule:r,postChargeFee:parkingFeeFromDefinition(def,r),connectorType:stat.connectorType||null,minPowerKw:stat.connectorPowerMinkW??null,maxPowerKw:stat.connectorPowerMaxkW??null};
}
function bundleFromDefinitions(defs){
  const mapped=defs.map(ruleFromDefinition),fees=mapped.map(x=>x.postChargeFee).filter(Boolean),unique=[...new Set(fees.map(x=>JSON.stringify(x)))];
  return{rules:mapped.map(x=>x.rule),postChargeFee:unique.length===1?JSON.parse(unique[0]):null,ambiguousPostCharge:unique.length>1,mapped};
}
function offer(id,provider,bundle,extra={}){
  const b=Array.isArray(bundle)?{rules:bundle}:bundle,pricing={type:'rules',rules:b.rules};
  if(b.postChargeFee)pricing.postChargeFee=b.postChargeFee;
  return{id,selectionId:id,provider,countries:['FR'],currency:'EUR',priority:130,pricing,source:'Load Motion matching-pricing-definitions/resolve',directOperatorOnly:true,verifiedScope:'exact_evse',defaultSelected:false,...extra};
}
function isNoTariff(d){return clean(d?.name).toLowerCase()==='no tariff';}
function isSubscriberOnly(name){const n=clean(name).toLowerCase();return n.includes('abonné')&&!n.includes('non abonné')&&!n.includes('non abonne');}
function departmentFromSite(row){const v=[row?.site,row?.siteArea].map(clean).join(' ');return v.match(/(?:^|\s)(09|11|46|65|66)(?:\s|[-–—])/)?.[1]||null;}
const directOffers=[];

// YES55: exact EVSE offers only; No Tariff/empty/errors never become rankable.
{
  const groups=new Map();
  for(const row of current.yes55.tarifs||[]){const defs=(row.definitions||[]).filter(d=>!isNoTariff(d));if(!defs.length)continue;const bundle=bundleFromDefinitions(defs);if(bundle.ambiguousPostCharge)continue;const ids=defs.map(d=>d?.ocpiData?.id||d?.id).filter(Boolean),key=JSON.stringify({rules:bundle.rules,postChargeFee:bundle.postChargeFee,ids});if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row.station);}
  let i=0;for(const [key,evses] of [...groups.entries()].sort((a,b)=>a[0].localeCompare(b[0]))){const k=JSON.parse(key);directOffers.push(offer(`loadmotion-yes55-profile-${String(++i).padStart(2,'0')}`,'YES55 direct',{rules:k.rules,postChargeFee:k.postChargeFee},{evseIds:[...new Set(evses)].sort(),operatorAliases:['YES55','Y55'],priority:132,metadata:{tenant:'yes55',tariffIds:k.ids,exactEvseCount:new Set(evses).size,fallback:'Electra then Electroverse'}}));}
}

// Load Stations: only station-specific issuer=false definitions; generic tenant defaults are ambiguous.
{
  const groups=new Map();
  for(const row of current.loadstations.tarifs||[]){const defs=(row.definitions||[]).filter(d=>d?.issuer===false&&!isNoTariff(d));if(!defs.length)continue;const bundle=bundleFromDefinitions(defs);if(bundle.ambiguousPostCharge)continue;const ids=defs.map(d=>d?.ocpiData?.id||d?.id).filter(Boolean),key=JSON.stringify({rules:bundle.rules,postChargeFee:bundle.postChargeFee,ids});if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row.station);}
  let i=0;for(const [key,evses] of [...groups.entries()].sort((a,b)=>a[0].localeCompare(b[0]))){const k=JSON.parse(key);directOffers.push(offer(`loadmotion-loadstations-profile-${String(++i).padStart(2,'0')}`,'Load Stations direct',{rules:k.rules,postChargeFee:k.postChargeFee},{evseIds:[...new Set(evses)].sort(),operatorAliases:['Load Stations','LoadStations'],priority:132,metadata:{tenant:'loadstations',definitionIds:k.ids,exactEvseCount:new Set(evses).size,stationSpecificIssuerFalse:true,ambiguousTenantDefaultsExcluded:true}}));}
}

const reveoAliases={
  '09':['SDE09','SDE 09','Syndicat Départemental d’Énergies de l’Ariège','Syndicat Departemental d Energies de l Ariege','REVEO SDE09'],
  '11':['SYADEN','REVEO SYADEN','Syndicat Audois d’Énergies','Syndicat Audois d Energies'],
  '46':['TE46','Territoire d’Énergie Lot','Territoire d Energie Lot','REVEO TE46'],
  '65':['SDE65','SDE Hautes-Pyrénées','SDE Hautes Pyrenees','REVEO SDE65'],
  '66':['SYDEEL','SYDEEL66','SYDEEL 66','REVEO SYDEEL']
};

// Reveo: territory-specific company/tenant rules only; generic REVEO alias intentionally excluded.
{
  const defs=new Map(),depIds=new Map(Object.keys(reveoAliases).map(d=>[d,new Set()]));
  for(const row of current.reveo.tarifs||[]){const dep=departmentFromSite(row);if(!dep||!depIds.has(dep))continue;for(const d of row.definitions||[]){if(isSubscriberOnly(d?.name))continue;const id=d?.ocpiData?.id||d?.id;if(!id)continue;defs.set(id,d);depIds.get(dep).add(id);}}
  for(const dep of Object.keys(reveoAliases))for(const id of [...depIds.get(dep)].sort()){const d=defs.get(id);if(!d)continue;const x=ruleFromDefinition(d),bundle=bundleFromDefinitions([d]),kinds=x.connectorType==='T2'?['AC']:x.connectorType==='CCS'?['DC']:[];directOffers.push(offer(`loadmotion-reveo-${dep}-${compactId(id).slice(-8).toLowerCase()}`,`Révéo direct ${dep}`,bundle,{operatorAliases:reveoAliases[dep],networkAliases:reveoAliases[dep],connectorKinds:kinds,minPowerKw:x.minPowerKw,maxPowerKw:x.maxPowerKw,priority:126,directOperatorOnly:false,verifiedScope:'territorial_network_power',metadata:{tenant:'reveo',department:dep,definitionId:id,definitionName:d.name,genericReveoAliasExcluded:true}}));}
}

// MobiSDEC: tenant-wide power-band/time rules. parkingTime is post-charge occupation.
{
  const defs=new Map();for(const row of current.mobisdec.tarifs||[])for(const d of row.definitions||[]){const id=d?.ocpiData?.id||d?.id;if(id)defs.set(id,d);}
  const aliases=['MobiSDEC','Mobi SDEC','SDEC Energie','SDEC Énergie','SDEC Energie Calvados'];
  for(const [id,d] of [...defs.entries()].sort((a,b)=>a[0].localeCompare(b[0]))){const x=ruleFromDefinition(d),bundle=bundleFromDefinitions([d]),kinds=x.connectorType==='T2'?['AC']:x.connectorType==='CCS'?['DC']:[];directOffers.push(offer(`loadmotion-mobisdec-${compactId(id).slice(-8).toLowerCase()}`,'MobiSDEC direct',bundle,{operatorAliases:aliases,networkAliases:aliases,connectorKinds:kinds,minPowerKw:x.minPowerKw,maxPowerKw:x.maxPowerKw,priority:128,directOperatorOnly:false,verifiedScope:'operator_or_network_power_time',metadata:{tenant:'mobisdec',definitionId:id,definitionName:d.name,parkingSemantics:'OCPI PARKING_TIME/time-not-charging; represented as V9 postChargeFee with grace/exempt windows'}}));}
}

const output={schemaVersion:1,country:'FR',generatedAt:new Date().toISOString(),mode:'verified_loadmotion_direct',policy:{source:'Load Motion production tenants',resolver:'matching-pricing-definitions/resolve',resolvedPriceField:'dimensions.*.price',noTariffIsFree:false,fallbackOrder:['Electra','Electroverse'],yes55ExactEvseOnly:true,loadstationsStationSpecificOnly:true,reveoGenericNetworkGeneralization:false,mobisdecPowerTimeRules:true,siti11SeparateImport:false},directOffers,subscriptionOffers:[],sourceEvidence:{yes55:current.yes55.summary||{},loadstations:current.loadstations.summary||{},reveo:current.reveo.summary||{},mobisdec:current.mobisdec.summary||{},siti11:{stations:0,coveredVia:'REVEO / SYADEN Aude / FR*S11',separateImport:false}}};
fs.mkdirSync(path.dirname(outPath),{recursive:true});fs.writeFileSync(outPath,JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify({offers:directOffers.length,yes55:directOffers.filter(x=>x.metadata?.tenant==='yes55').length,loadstations:directOffers.filter(x=>x.metadata?.tenant==='loadstations').length,reveo:directOffers.filter(x=>x.metadata?.tenant==='reveo').length,mobisdec:directOffers.filter(x=>x.metadata?.tenant==='mobisdec').length,out:outPath},null,2));