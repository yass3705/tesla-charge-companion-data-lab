// Read-only audit: never attribute a price to EVSE from recurring station-level patterns.
import fs from 'node:fs/promises';import zlib from 'node:zlib';
const gunzip=async p=>JSON.parse(zlib.gunzipSync(await fs.readFile(p)).toString());
const [archive,locations,manifest,verified]=await Promise.all([
 gunzip('reports/france/irve/electra-pricing-residual-cases-2026-10-08.json.gz'),
 gunzip('data/platforms/electra/france/source-locations.json.gz'),
 fs.readFile('data/platforms/electra/france/manifest.json','utf8').then(JSON.parse),
 fs.readFile('data/manual_verification/electra_app_residual_evidence_2026-10-10.json','utf8').then(JSON.parse)
]);
const lookup=new Map(locations.locations.map(x=>[String(x.id),x]));
const arr=archive.cases.filter(c=>c.cpo==='Powerdot');
const counts={},byFamily={},rateGroups={},powerSets={},all=[];
const count=(m,k)=>(m[k]=(m[k]||0)+1);
const comparable=(x,y)=>Math.abs(Number(x)-Number(y))<0.01;
for(const c of arr){
 const loc=lookup.get(c.locationId)||{},triage=c.triage||{};
 const e=triage.energyPriceVariation,f=triage.ancillaryPriceVariation,r=triage.restrictionVariation;
 const kind=[e?'energy':null,f?'fees':null,r?'restrictions':null].filter(Boolean).join('+')||'other';
 const p=(triage.distinctKnownPowers||[]).map(Number).sort((a,b)=>a-b);
 const powerKey=p.map(x=>x.toFixed(1)).join('|');
 const tariffs=(loc.chargeTariffs||[]).map(t=>({
  tariffId:t.chargeTariffId||t.id,components:(t.elements||[]).flatMap(e=>(e.priceComponents||[]).map(pc=>({
   type:pc.type,price:Number(pc.price),restriction:e.restrictions||{}
  })))
 }));
 const rates=[...new Set(tariffs.flatMap(t=>t.components.filter(p=>p.type==='ENERGY').map(p=>p.price)))].sort((a,b)=>a-b);
 const rateKey=rates.map(x=>x.toFixed(3)).join('|');
 const outside=tariffs.map(t=>[...new Set(t.components.filter(x=>x.type!=='ENERGY').map(x=>x.type+':'+x.price))].sort().join('|'));
 const row={locationId:c.locationId,cpo:c.cpo,name:loc.name||c.name,city:loc.city||null,
  postcode:loc.postalCode||null,address:loc.address||null,latitude:loc.coordinates?.latitude??null,
  longitude:loc.coordinates?.longitude??null,knownPowersKw:p,evseIds:c.evseIds||[],
  sourceConnectorKinds:loc.connectorTypes||[],sourceStationMaxPowerKw:Number(loc.maxPower||0)/1000,
  tariffCount:c.tariffCount,kind,pricesEurPerKwh:rates,rateKey,powerKey,
  ancillaryTariffSignatures:outside,tariffIds:tariffs.map(x=>x.tariffId)};
 all.push(row);count(counts,kind);count(powerSets,powerKey);
 const famKey=powerKey+' / '+rateKey;count(byFamily,famKey);count(rateGroups,rateKey);
}
const energy=all.filter(x=>x.kind==='energy');
const sharedTariffIdPairs={};
const tariffProfiles={};
const cohortExamples={};
const powersByPair={};
for(const station of all){
 const pair=station.tariffIds.filter(Boolean).slice().sort().join('|');
 if(!pair)continue;
 count(sharedTariffIdPairs,pair);
 if(!cohortExamples[pair])cohortExamples[pair]={name:station.name,city:station.city,locationId:station.locationId,powers:station.knownPowersKw,rates:station.pricesEurPerKwh};
 const l=lookup.get(station.locationId);
 for(const tariff of l?.chargeTariffs||[]){
  const id=String(tariff.chargeTariffId||tariff.id||'');
  if(!id)continue;
  const p=tariffProfiles[id]??={stations:0,seen:new Set(),rates:new Set(),components:new Set()};
  if(!p.seen.has(station.locationId)){p.stations++;p.seen.add(station.locationId);}
  for(const e of tariff.elements||[])for(const c of e.priceComponents||[]){
   if(c.type==='ENERGY'&&Number.isFinite(Number(c.price)))p.rates.add(Number(c.price));
   else p.components.add(String(c.type)+':'+c.price);
  }
 }
 if(!powersByPair[pair])powersByPair[pair]=new Set();
 powersByPair[pair].add(station.powerKey);
}
const canonicalIds=['deb8f441-4306-4735-9990-3165dbeefffc','9d3380b6-bfef-4f52-a50e-11f72cff552c'].sort().join('|');
const repeatedPairStations=all.filter(x=>x.tariffIds.slice().sort().join('|')===canonicalIds);
const exactPairRateStations=repeatedPairStations.filter(x=>x.rateKey==='0.490|0.620');
const candidate=energy.filter(x=>x.knownPowersKw.length>=2&&x.tariffCount===2&&x.pricesEurPerKwh.length===2&&
 x.knownPowersKw.some(p=>p<=22.2)&&x.knownPowersKw.some(p=>p>=50));
function score(x){
 let n=0;
 if(/^7[578]|^9[12345]/.test(String(x.postcode)))n+=35;
 if(/^(78|91|92|93|94|95|75|77)/.test(String(x.postcode)))n+=24;
 if(/INTERMARCH|CARREFOUR|LIDL|U EXPRESS|SUPER U|E\.LECLERC|LECLERC|ALDI|MAGASIN|MARCHE|HYPERMARCHE/i.test(x.name||''))n+=25;
 if(/CONCESSION|GARAGE|PORSCHE|AUDI|RENAULT|BMW|MERCEDES|OPEL|CITROEN/i.test(x.name||''))n-=75;
 if(x.city)n+=8;if(x.address)n+=6;
 if(x.knownPowersKw.length===2)n+=12;
 if(x.evseIds.length>=2&&x.evseIds.length<=5)n+=6;
 if(x.pricesEurPerKwh.every(v=>v>=0.05&&v<=1))n+=6;
 return n;
}
candidate.sort((a,b)=>score(b)-score(a)||a.locationId.localeCompare(b.locationId));
const samples=[],cities=new Set();
for(const x of candidate){if(samples.length>=10)break;
 if(x.locationId==='01df2390-d20f-4199-9b15-b2b6c95c94c3'||cities.has(x.city))continue;
 samples.push(x);cities.add(x.city);
}
const top=(m,n=15)=>Object.entries(m).sort((a,b)=>b[1]-a[1]).slice(0,n).map(([key,stations])=>({key,stations}));
const powerdot={
 schemaVersion:1,generatedAt:new Date().toISOString(),snapshotGeneratedAt:manifest.generatedAt,
 totalUnresolvedPowerdotLocations:all.length,variationTypes:counts,
 sourceTariffsAreAtLocationLevel:true,energyOnly:energy.length,
 exactJarvilleTariffIdPairReusedOnStations:repeatedPairStations.length,
 exactTariffPairAndRatesConsistent:exactPairRateStations.length,
 repeatedTariffIdPairs:top(sharedTariffIdPairs,10).map(x=>({...x,sample:cohortExamples[x.key]})),
 tariffIdPriceProfiles:Object.entries(tariffProfiles).sort((a,b)=>b[1].stations-a[1].stations).slice(0,18)
  .map(([tariffId,p])=>({tariffId,stations:p.stations,rates:[...p.rates].sort((a,b)=>a-b),components:[...p.components].sort()})),
 reuseValidation:'Matching chargeTariffId is strong repeated schema evidence, but it is not an explicit EVSE binding at other stations and must not be automatically applied without second app test.',
 powerSetVariationAcrossCanonicalPair:powersByPair[canonicalIds]?.size??0,
 dualTariffTwoRatesOneSlowOneFastCandidateCount:candidate.length,
 topKnownPowerSets:top(powerSets,18),topPricePairs:top(rateGroups,18),
 topPowerPriceCohorts:top(byFamily,22),
 eligiblePatternOnlyNoUniqueEvseMapping:true,verifiedPowerdotComparison:{
  locationId:'01df2390-d20f-4199-9b15-b2b6c95c94c3',
  name:'Intermarché Jarville',slowKw:22,slowRateEurPerKwh:0.49,fastKw:60,fastRateEurPerKwh:0.62,
  note:'This is ONE verified station, not a national tariff rule.'},
 suggestedAppChecks:samples.map(x=>({...x,score:score(x),
  question:'Dans Electra, ouvrir « Prix et frais » : prix lente et rapide par puissance, éventuels frais additionnels et identifiants de connecteurs disponibles.'})),
 decision:'No mass-assign from statistical co-occurrence. Escalate exact EVSE-ID/power/chargeTariffId as separate proof.'
};
const output='reports/france/electra/powerdot-price-power-cohorts-2026-10-10.json';
await fs.writeFile(output,JSON.stringify(powerdot,null,2)+'\n');
const fixed=[
 {locationId:'16743f5c-12b1-4d64-be4d-baf96be974a3',expectedOriginal:'some_evse_powers_unknown',status:'two_exact_Evse_powers_from_app',
  evidence:'Four distinct FR*ALN*E25002101*1..4*1 Type2 at 22kW in user screenshot',newKnownKw:22,
  evseIds:['FR*ALN*E25002101*3*1','FR*ALN*E25002101*4*1']},
 {locationId:'023865cd-6b6a-4012-96c4-ba29ec7b09ec',expectedOriginal:'some_evse_powers_unknown',
  status:'station_power_mix_discovered_but_evse_hardware_mapping_missing',connectorPowers:[237,22,50],
  note:'IRVE 50/100 vs app CCS 237, Type2 22, CCS/CHAdeMO 50'},
 {locationId:'073cd4ab-af25-4494-8c61-1bb0a3cad16f',expectedOriginal:'all_evse_powers_unknown',
  status:'station_closed_and_technical_power_mix_discovered_without_explicit_evse_id',connectorPowers:[22,50],
  note:'Station closed despite hours panel showing Open'},
 {locationId:'8988e4f8-bfe7-4ede-a9a3-5a77435b26ff',expectedOriginal:'all_evse_powers_unknown',
  status:'wrong_station_left_vs_right_exclude_evidence',note:'App screenshot is LIBERATION GAUCHE, unresolved case is LIBERATION DROITE'},
 {locationId:'29249b75-f39f-48e9-9369-87ab751c5040',expectedOriginal:'single_known_power_without_tariff_mapping',
  status:'120kw_technical_support_price_remains_multiple',appHeadlineRate:0.40,candidateRates:[0.39,0.40],stationClosed:true},
 {locationId:'026a3ca9-95b4-46d5-9659-6a721a4f4349',expectedOriginal:'single_known_power_without_tariff_mapping',
  status:'wrong_aggregate_56kw_vs_connector_50_22_3',appSlowRate:0.30,appFastRate:0.40,feesPerHour:1.68,
  note:'Connector hardware powers not corresponding to national per-EVSE nominal 56kW; cannot safely remap precise IDs'}
];
const diagnostic=fixed.map(x=>({...x,originalClass:archive.cases.find(y=>y.locationId===x.locationId)?.triage?.class||null,
 sourceEvses:archive.cases.find(y=>y.locationId===x.locationId)?.evseIds||[],evidenceHashEntries:
 (verified.stations.find(y=>y.locationId===x.locationId)?.evidence||[]).map(y=>({file:y.file,sha256:y.sha256}))}));
const report={schemaVersion:1,generatedAt:new Date().toISOString(),snapshotGeneratedAt:manifest.generatedAt,
 screenshotEvidenceFile:'data/manual_verification/electra_app_residual_evidence_2026-10-10.json',
 cases:diagnostic,noMassReclassificationUntilFutureAudit:true,
 appValidatedMissingPowers:2,
 partialUnknownBefore:300,partiallyResolvedTechnicalStations:1,
 knownButTariffAmbiguousRemaining:3,
 note:'App images provide technical evidence; this report does not alter source price/technical power when precise ID mapping is absent.'};
const out2='reports/france/electra/user-residual-screens-case-resolution-2026-10-10.json';
await fs.writeFile(out2,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({powerdot:{all:powerdot.totalUnresolvedPowerdotLocations,energyOnly:energy.length,candidate:candidate.length,variation:counts,cohorts:powerdot.topPowerPriceCohorts.slice(0,8),examples:samples.slice(0,6).map(s=>({name:s.name,city:s.city,postcode:s.postcode,locationId:s.locationId,powers:s.knownPowersKw,rates:s.pricesEurPerKwh,evseIds:s.evseIds,tariffCount:s.tariffCount,kind:s.kind}))},screens:report.cases.map(x=>({id:x.locationId,class:x.originalClass,status:x.status}))}).slice(0,16500));
