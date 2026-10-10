import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const base='reports/france/irve/', outbase='reports/france/electra/';
const load=async p=>JSON.parse(zlib.gunzipSync(await fs.readFile(p)).toString('utf8'));
const [archive,sources,manifest]=await Promise.all([
 load(base+'electra-pricing-residual-cases-2026-10-08.json.gz'),
 load('data/platforms/electra/france/source-locations.json.gz'),
 fs.readFile('data/platforms/electra/france/manifest.json','utf8').then(JSON.parse)
]);
const cases=archive.cases||[],byLocation=new Map((sources.locations||[]).map(x=>[String(x.id),x]));
const knownVerified=new Set(['04a04882-7e07-40b2-bf67-3f757548054d',
 '5338d58c-c8be-4719-964e-cab7f61438e4',
 '01df2390-d20f-4199-9b15-b2b6c95c94c3',
 '428364b3-2b55-4f1f-802b-819b9af0403a',
 '137e6395-b5a0-4832-987b-84a22331b3aa',
 '0a05897d-13f9-44ee-a64e-5d4ec1422239']);
const str=x=>String(x??'').trim();
const safe=x=>Number.isFinite(Number(x))?Number(x):null;
const unique=arr=>[...new Set(arr)];
function details(loc){
 const energy=[],fees=[],restrictions=[],tariffDetails=[];
 for(const t of loc?.chargeTariffs||[]){
  const rates=[],extras=[],restr=[];
  for(const e of t.elements||[]){
   const r=e.restrictions||{};
   const rr=Object.fromEntries(Object.entries(r).filter(([k,v])=>v!=null&&v!==''&&(!Array.isArray(v)||v.length)));
   if(Object.keys(rr).length)restr.push(rr);
   for(const p of e.priceComponents||[]){
    const type=str(p.type).toUpperCase(),price=safe(p.price);if(price==null)continue;
    if(type==='ENERGY'){rates.push(price);energy.push(price);}
    else {extras.push({type,price});fees.push(type+':'+price);}
   }
  }
  tariffDetails.push({id:t.chargeTariffId||t.id||null,
   energyEurPerKwh:unique(rates).sort((a,b)=>a-b),
   fees:unique(extras.map(x=>x.type+':'+x.price)),
   restrictions:restr.slice(0,12)});
  restrictions.push(...restr);
 }
 return {candidateEnergyEurPerKwh:unique(energy).sort((a,b)=>a-b),
  candidateExtraFees:unique(fees).slice(0,15),
  restrictionFields:unique(restrictions.flatMap(r=>Object.keys(r))).sort(),
  tariffDetails:tariffDetails.slice(0,6)};
}
function variationKey(t){
 const e=Boolean(t.energyPriceVariation),f=Boolean(t.ancillaryPriceVariation),r=Boolean(t.restrictionVariation);
 return [e?'energy':null,f?'fees':null,r?'restrictions':null].filter(Boolean).join('+')||'same_signature_or_other';
}
function powerTopology(p){
 if(p.length<2)return'powers_not_multiple';
 if(p.some(x=>x<=22)&&p.some(x=>x>=50))return'low_to_fast_22_or_less_and_50_plus';
 if(p.every(x=>x<=22))return'all_powers_22_or_less';
 if(p.every(x=>x>=50))return'all_powers_50_plus';
 return'other_mixed_powers';
}
const summaries=cases.map(c=>{
 const loc=byLocation.get(c.locationId)||{},t=c.triage||{};
 return {locationId:c.locationId,cpo:str(c.cpo||loc.cpo?.name||''),name:str(loc.name||c.name),
  city:str(loc.city),postalCode:str(loc.postalCode),address:str(loc.address),latitude:safe(loc.coordinates?.latitude),
  longitude:safe(loc.coordinates?.longitude),sourceMaxPowerKw:safe(loc.maxPower)!=null?Number(loc.maxPower)/1000:null,
  connectorTypes:loc.connectorTypes||[],evseIds:c.evseIds||[],evsePowerGroups:c.powerGroups||{},
  evseCount:t.sourceEvseCount??c.evseCount,knownEvseCount:t.knownPowerCount??0,unknownEvseCount:t.unknownPowerCount??0,
  powersKw:t.distinctKnownPowers||[],tariffCount:c.tariffCount,tariffSignatureCount:c.tariffSignatureCount,
  variationKey:variationKey(t),class:t.class,powerTopology:powerTopology(t.distinctKnownPowers||[]),
  tariffPowerScopeCount:t.tariffPowerScopeCount,reason:c.reason,...details(loc)};
});
function score(x){
 return (x.name.length>12?12:0)+(x.city?12:0)+(x.address?7:0)+(x.postalCode?4:0)
  +(x.evseIds.length>=2&&x.evseIds.length<=5?18:0)+(x.tariffCount===2?9:0)
  +(x.candidateEnergyEurPerKwh.length>=2?9:0)+(x.evseIds.length<=8?5:0)
  -(knownVerified.has(x.locationId)?100:0);
}
function choose(rows,n=3,operatorDistinct=true){
 const ordered=rows.slice().sort((a,b)=>score(b)-score(a)||a.locationId.localeCompare(b.locationId));
 const seenCpo=new Set(),seenCity=new Set(),result=[];
 for(const r of ordered){if(result.length>=n)break;
  if(operatorDistinct&&seenCpo.has(r.cpo))continue;
  const cityKey=r.city.toLowerCase();if(cityKey&&seenCity.has(cityKey))continue;
  result.push(r);seenCpo.add(r.cpo);if(cityKey)seenCity.add(cityKey);
 }
 for(const r of ordered){if(result.length>=n)break;if(result.some(x=>x.locationId===r.locationId))continue;result.push(r);}
 return result;
}
const groups={
 multiple_known_powers_without_tariff_mapping:summaries.filter(x=>x.class==='multiple_known_powers_without_tariff_mapping'),
 all_evse_powers_unknown:summaries.filter(x=>x.class==='all_evse_powers_unknown'),
 some_evse_powers_unknown:summaries.filter(x=>x.class==='some_evse_powers_unknown'),
 single_known_power_without_tariff_mapping:summaries.filter(x=>x.class==='single_known_power_without_tariff_mapping')
};
const multiple=groups.multiple_known_powers_without_tariff_mapping;
if(Object.values(groups).reduce((sum,rows)=>sum+rows.length,0)!==cases.length)
 throw Error('Canonical class counts do not reconcile to all residual cases: '+
 JSON.stringify(Object.fromEntries(Object.entries(groups).map(([k,v])=>[k,v.length]))));
const profile=(rows,n=3)=>({
 stations:rows.length,knownEvseIds:rows.reduce((a,x)=>a+x.knownEvseCount,0),
 operatorCounts:Object.entries(rows.reduce((m,x)=>(m[x.cpo]=(m[x.cpo]||0)+1,m),{}))
  .sort((a,b)=>b[1]-a[1]).slice(0,15).map(([operator,stations])=>({operator,stations})),
 powerTopologies:Object.entries(rows.reduce((m,x)=>(m[x.powerTopology]=(m[x.powerTopology]||0)+1,m),{}))
  .sort((a,b)=>b[1]-a[1]).map(([type,stations])=>({type,stations})),
 commonPowerSets:Object.entries(rows.reduce((m,x)=>(m[x.powersKw.join('+')]=(m[x.powersKw.join('+')]||0)+1,m),{}))
  .sort((a,b)=>b[1]-a[1]).slice(0,12).map(([powers,stations])=>({powers,stations})),
 numberOfTariffGrids:Object.entries(rows.reduce((m,x)=>(m[x.tariffCount]=(m[x.tariffCount]||0)+1,m),{}))
  .sort((a,b)=>b[1]-a[1]).map(([tariffs,stations])=>({tariffs:Number(tariffs),stations})),
 examples:choose(rows,n)
});
const patternKeys=['energy','fees','restrictions','energy+fees','energy+restrictions','fees+restrictions','energy+fees+restrictions','same_signature_or_other'];
const patterns=patternKeys.map(key=>({key,...profile(multiple.filter(x=>x.variationKey===key),3)})).filter(x=>x.stations);
const total=patterns.reduce((a,x)=>a+x.stations,0);
if(total!==multiple.length)throw Error('Pattern typology did not reconcile');
const topologyTypes=['low_to_fast_22_or_less_and_50_plus','all_powers_22_or_less','all_powers_50_plus','other_mixed_powers'];
const topologies=topologyTypes.map(key=>({key,...profile(multiple.filter(x=>x.powerTopology===key),2)})).filter(x=>x.stations);
const examples={
 allUnknown:choose(groups.all_evse_powers_unknown,6),
 partialUnknown:choose(groups.some_evse_powers_unknown,6),
 singleKnownPower:choose(groups.single_known_power_without_tariff_mapping,10)
};
function problemPrompt(x){
 const pw=x.powersKw.length?x.powersKw.join(' / ')+' kW':'puissance IRVE inconnue';
 const evseDesc=Object.entries(x.evsePowerGroups||{}).map(([p,ids])=>p+' kW : '+ids.join(', ')).join(' ; ');
 return {locationId:x.locationId,station:x.name,city:x.city,postalCode:x.postalCode,cpo:x.cpo,
 address:x.address,coordinate:[x.latitude,x.longitude],powerGroups:x.powersKw,unknownEvseCount:x.unknownEvseCount,
 evseIds:x.evseIds,evseDescription:evseDesc,tariffCount:x.tariffCount,pricesEurPerKwh:x.candidateEnergyEurPerKwh,
 extraFeesCandidates:x.candidateExtraFees,restrictions:x.restrictionFields,
 checkInApp:x.class==='all_evse_powers_unknown'?
 'Retrouver la station via nom/adresse; noter la puissance visible pour chaque borne et ses prix; vérifier identifiants des prises':
 x.class==='some_evse_powers_unknown'?
 'Vérifier les seules bornes dont la puissance IRVE est inconnue, avec puissance affichée et prix par borne':
 'Vérifier si les '+x.tariffCount+' grilles concernent des horaires, frais, abonnements ou connecteurs pour une puissance IRVE unique de '+pw};
}
const report={schemaVersion:1,generatedAt:new Date().toISOString(),sourceGeneratedAt:manifest.generatedAt,
 inputCases:cases.length,classificationCounts:Object.fromEntries(Object.entries(groups).map(([k,v])=>[k,v.length])),
 primaryGroup:{class:'multiple_known_powers_without_tariff_mapping',count:multiple.length,
 typologyDefinition:'Mutually exclusive combination of price-energy, extra-fee and restriction variation; source provides no proof of assignment to EVSE',
 tariffPatterns:patterns,technicalTopologies:topologies,
 dimensionCounts:{varyingEnergy:multiple.filter(x=>x.variationKey.includes('energy')).length,
 varyingFees:multiple.filter(x=>x.variationKey.includes('fees')).length,
 varyingRestrictions:multiple.filter(x=>x.variationKey.includes('restrictions')).length},
 sharedCpoPatterns:Object.entries(multiple.reduce((m,x)=>{
  (m[x.cpo]??={total:0,patterns:{}}).total++;m[x.cpo].patterns[x.variationKey]=(m[x.cpo].patterns[x.variationKey]||0)+1;return m;
 },{})).sort((a,b)=>b[1].total-a[1].total).slice(0,20).map(([cpo,data])=>({cpo,...data}))},
 requestExamples:{
  powerEntirelyUnknown:{count:groups.all_evse_powers_unknown.length,
   totalUnknownEvseIds:groups.all_evse_powers_unknown.reduce((n,x)=>n+x.unknownEvseCount,0),
   examples:examples.allUnknown.map(problemPrompt)},
  powerPartiallyUnknown:{count:groups.some_evse_powers_unknown.length,
   totalUnknownEvseIds:groups.some_evse_powers_unknown.reduce((n,x)=>n+x.unknownEvseCount,0),
   examples:examples.partialUnknown.map(problemPrompt)},
  singleKnownPower:{count:groups.single_known_power_without_tariff_mapping.length,
   examples:examples.singleKnownPower.map(problemPrompt)}
 },
 methodology:{powerEvidence:'French national IRVE EVSE groups, missing=not identified by exact EVSE ID',
 priceEvidence:'Electra eMSP GraphQL chargeTariffs at station-level; candidate only',
 checkedExcludes:'Previously checked Albi, Jarville, Saint-Quentin, Marseille, Pessac, Bellentre are excluded from selected new examples',
 interpretation:'Tariff variation at a location does not prove a same-EVSE tariff conflict. No tariff assigned automatically.',
 noPublicationOfUnprovenTariffs:true}};
await fs.mkdir(outbase,{recursive:true});
const output=outbase+'residual-typologies-and-verification-examples-2026-10-10.json';
await fs.writeFile(output,JSON.stringify(report,null,2)+'\n');
const fields=['class','variationKey','locationId','cpo','name','city','postalCode','address','powersKw','evseIds','unknownEvseCount','tariffCount','energyPrices','fees','restrictionFields'];
const csv=v=>{const s=String(v??'');return /[;"\n\r]/.test(s)?'"'+s.replaceAll('"','""')+'"':s;};
const queue=[fields.join(';')];
for(const c of summaries){
 const item={...c,powersKw:c.powersKw.join('|'),evseIds:c.evseIds.join('|'),
  energyPrices:c.candidateEnergyEurPerKwh.join('|'),fees:c.candidateExtraFees.join('|'),
  restrictionFields:c.restrictionFields.join('|')};
 queue.push(fields.map(k=>csv(item[k])).join(';'));
}
const path=outbase+'electra-residual-station-typologies-latest.csv';
await fs.writeFile(path,String.fromCharCode(0xFEFF)+queue.join('\n')+'\n');
console.log(JSON.stringify({report:output,csv:path,counts:report.classificationCounts,
patterns:patterns.map(x=>({key:x.key,count:x.stations,examples:x.examples.slice(0,2).map(z=>({name:z.name,cpo:z.cpo,powers:z.powersKw,prices:z.candidateEnergyEurPerKwh}))})),
unknownExamples:report.requestExamples.powerEntirelyUnknown.examples.slice(0,4).map(x=>({station:x.station,cpo:x.cpo,city:x.city,evseIds:x.evseIds,prices:x.pricesEurPerKwh})),
partialExamples:report.requestExamples.powerPartiallyUnknown.examples.slice(0,4).map(x=>({station:x.station,cpo:x.cpo,city:x.city,evseIds:x.evseIds,unknown:x.unknownEvseCount,powers:x.powerGroups})),
singleExamples:report.requestExamples.singleKnownPower.examples.slice(0,5).map(x=>({station:x.station,cpo:x.cpo,powers:x.powerGroups,prices:x.pricesEurPerKwh}))}).slice(0,15000));
