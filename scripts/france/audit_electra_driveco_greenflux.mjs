import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const unzip=async path=>JSON.parse(zlib.gunzipSync(await fs.readFile(path)).toString('utf8'));
const [source,irve,residual,manifest]=await Promise.all([
 unzip('data/platforms/electra/france/source-locations.json.gz'),
 unzip('data/national/france-irve-static-v9/all.json.gz'),
 unzip('reports/france/irve/electra-pricing-residual-cases-2026-10-08.json.gz'),
 fs.readFile('data/platforms/electra/france/manifest.json','utf8').then(JSON.parse)
]);
const norm=x=>String(x??'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const mkCount=()=>Object.create(null);
const inc=(o,k,n=1)=>o[k]=(o[k]||0)+n;
const tops=(o,n=20)=>Object.entries(o).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).slice(0,n).map(([key,locations])=>({key,locations}));
const U=a=>[...new Set(a)];
const compactNum=v=>Number.isFinite(Number(v))?Number(v):null;
const byId=new Map((source.locations||[]).map(x=>[String(x.id),x]));
const irveId=new Map();
for(const row of irve){
 for(const group of row[8]||[]){
  const kind=String(group[2]||'').toUpperCase(),kw=Number(group[3]);
  for(const id0 of group[6]||[]){
   const id=norm(id0);if(!id)continue;
   const x=irveId.get(id)||{kinds:new Set(),powers:new Set(),observedIds:new Set()};
   if(kind)x.kinds.add(kind);
   if(Number.isFinite(kw)&&kw>0)x.powers.add(kw);
   x.observedIds.add(id0);
   irveId.set(id,x);
  }
 }
}
const typeOf=(x)=>{
 if(!x)return'unknown';
 if(x.kinds.size!==1)return x.kinds.size?'mixed':'unknown';
 return [...x.kinds][0];
};
const detail=t=>{
 const e=t.elements||[];
 const priceComponents=e.flatMap(y=>(y.priceComponents||[]).map(z=>({kind:String(z.type||'').toUpperCase(),value:compactNum(z.price),r:y.restrictions||{}})));
 const values=U(priceComponents.filter(x=>x.kind==='ENERGY').map(x=>x.value).filter(x=>x!=null)).sort((a,b)=>a-b);
 const fee=U(priceComponents.filter(x=>x.kind!=='ENERGY').map(x=>x.kind+':'+x.value)).sort();
 const restrictions=U(e.flatMap(x=>Object.entries(x.restrictions||{}).filter(([_,v])=>v!=null&&v!==''&&!(Array.isArray(v)&&v.length===0)).map(([k,v])=>k+':'+JSON.stringify(v)))).sort();
 const priceKey=values.map(x=>x.toFixed(3)).join('/');
 return {tariffId:String(t.chargeTariffId||t.id||''),rates:values,fees:fee,restrictions,elementCount:e.length,
  pureUnrestrictedEnergy:values.length===1&&fee.length===0&&restrictions.length===0&&priceComponents.every(x=>x.kind==='ENERGY'),
  completeSignature:JSON.stringify([values,fee,restrictions,priceComponents.map(x=>[x.kind,x.value,x.r]).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)))]),
  priceKey};
};
const CPOs=['DRIVECO','Greenflux'];
const sourceCases=(residual.cases||[]).filter(x=>CPOs.includes(String(x.cpo)));
const groupResults={};
const appChecks=[];
const allRows=[];
for(const cpo of CPOs){
 const cases=sourceCases.filter(x=>x.cpo===cpo);
 const classCounts=mkCount(),patterns=mkCount(),ratePatterns=mkCount(),tariffIdPatterns=mkCount(),types=mkCount(),powerPatterns=mkCount(),
   restrictionTypes=mkCount(),feeTypes=mkCount(),priceVsType=mkCount(),onlyEnergyCategories=mkCount(),tids=mkCount(),sameKindDiffRates=mkCount();
 const family=new Map(),examples=[];
 let nationalEVSE=0,unknownTechnicalEVSE=0,acDcMixedLocations=0,acOnlyWithMultipleRates=0,dcOnlyWithMultipleRates=0,
      pureEnergyTwoRateMixedType=0,pureEnergyMultipleUnmapped=0,hasExplicitTariffPowerScope=0;
 for(const c of cases){
  const loc=byId.get(String(c.locationId))||{},ts=(loc.chargeTariffs||[]).map(detail);
  const evses=(loc.evses||[]).map(e=>{
   const k=irveId.get(norm(e.evseId)),typ=typeOf(k);
   return {id:String(e.evseId||''),kind:typ,powersKw:k?[...k.powers].sort((a,b)=>a-b):[],status:String(e.status||''),
    physicalReference:String(e.physicalReference||'')};
  });
  const kinds=U(evses.filter(e=>['AC','DC'].includes(e.kind)).map(e=>e.kind)).sort();
  const missing=evses.filter(e=>e.powersKw.length!==1||!['AC','DC'].includes(e.kind));
  const rates=U(ts.flatMap(t=>t.rates)).sort((a,b)=>a-b);
  const fees=U(ts.flatMap(t=>t.fees)).sort(),restr=U(ts.flatMap(t=>t.restrictions)).sort();
  const pure=ts.length>=2&&ts.every(t=>t.pureUnrestrictedEnergy);
  const typeKey=kinds.join('+')||'unknown',rateKey=rates.map(x=>x.toFixed(3)).join('|')||'none';
  const idKey=ts.map(t=>t.tariffId).sort().join('|');
  const sigKey=ts.map(t=>t.completeSignature).sort().join('||');
  const variation=[new Set(ts.map(t=>JSON.stringify(t.rates))).size>1?'energy':null,
    new Set(ts.map(t=>JSON.stringify(t.fees))).size>1?'fees':null,
    new Set(ts.map(t=>JSON.stringify(t.restrictions))).size>1?'restrictions':null].filter(Boolean).join('+')||'equivalent_or_other';
  inc(classCounts,c.triage?.class||'unknown');inc(patterns,variation);
  inc(ratePatterns,rateKey);inc(tariffIdPatterns,idKey);inc(types,typeKey);
  inc(powerPatterns,U(evses.flatMap(e=>e.powersKw)).sort((a,b)=>a-b).join('+')||'unknown');
  inc(priceVsType,rateKey+' / '+typeKey);inc(onlyEnergyCategories,pure?'all_pure_energy':'has_time_fees_or_restrictions');
  for(const t of ts){inc(tids,t.tariffId);for(const x of t.fees)inc(feeTypes,x.split(':')[0]);for(const x of t.restrictions)inc(restrictionTypes,x.split(':')[0]);}
  nationalEVSE+=evses.length;unknownTechnicalEVSE+=missing.length;
  if(typeKey==='AC+DC')acDcMixedLocations++;
  if(typeKey==='AC'&&rates.length>1){acOnlyWithMultipleRates++;inc(sameKindDiffRates,rateKey);}
  if(typeKey==='DC'&&rates.length>1)dcOnlyWithMultipleRates++;
  if(pure&&rates.length===2&&typeKey==='AC+DC'&&missing.length===0)pureEnergyTwoRateMixedType++;
  if(pure&&rates.length>1)pureEnergyMultipleUnmapped++;
  if((c.triage?.tariffPowerScopeCount||0)>0)hasExplicitTariffPowerScope++;
  const row={locationId:c.locationId,cpo,name:String(loc.name||c.name||''),city:String(loc.city||''),postalCode:String(loc.postalCode||''),
   address:String(loc.address||''),class:c.triage?.class||'unknown',variation,typeKey,rateKey,
   knownPowersKw:U(evses.flatMap(e=>e.powersKw)).sort((a,b)=>a-b),tariffCount:ts.length,tariffIds:ts.map(t=>t.tariffId),
   possibleEnergyRatesEurPerKwh:rates,pureEnergyTariffs:pure,feeTypes:U(fees.map(x=>x.split(':')[0])),feeValues:fees.slice(0,15),
   restrictionNames:U(restr.map(x=>x.split(':')[0])),unknownTechnicalEvseCount:missing.length,
   evses:evses.slice(0,25),tariffs:ts.map(t=>({tariffId:t.tariffId,rates:t.rates,fees:t.fees,restrictions:t.restrictions.slice(0,12),pureEnergy:t.pureUnrestrictedEnergy})),
   exactMatchEligible:false,reason:'Electra eMSP source chargeTariffs are at location level; no EVSE-to-chargeTariffId mapping'};
  allRows.push(row);
  const key=idKey||rateKey||sigKey;
  if(!family.has(key))family.set(key,{key,count:0,ratePatterns:mkCount(),typePatterns:mkCount(),pricingSignatures:mkCount(),examples:[]});
  const entry=family.get(key);entry.count++;inc(entry.ratePatterns,rateKey);inc(entry.typePatterns,typeKey);inc(entry.pricingSignatures,sigKey);
  if(entry.examples.length<3)entry.examples.push({name:row.name,city:row.city,locationId:row.locationId,powers:row.knownPowersKw,rates});
  const name=row.name.toLowerCase();
  let score=0;
  if(row.city)score+=8;if(row.address)score+=5;
  if(/supermarch|intermarch|carrefour|lidl|aldi|leclerc|boulangerie|hotel|hôtel|campanile|super u|parking/i.test(name))score+=14;
  if(/garage|concession|volkswagen|renault|bmw|porsche|toyota|peugeot|automobile/i.test(name))score-=60;
  if(typeKey==='AC+DC')score+=35;
  if(missing.length===0)score+=18;
  if(ts.length===2)score+=10;
  if(pure)score+=18;
  if(row.knownPowersKw.some(x=>x>100))score+=7;
  if(row.knownPowersKw.length>=2&&row.knownPowersKw.length<=4)score+=6;
  if(cpo==='DRIVECO'&&/campanile.*saint.?quentin|saint.?quentin.*campanile/i.test(name))score=-90;
  if(cpo==='Greenflux'&&/saint.?mihiel/i.test(name))score=-90;
  examples.push({score,...row});
 }
 const familySorted=[...family.values()].sort((a,b)=>b.count-a.count).map(f=>({
  key:f.key,stations:f.count,ratePatterns:tops(f.ratePatterns,6),typePatterns:tops(f.typePatterns,6),
  distinctCompleteTariffSignatures:Object.keys(f.pricingSignatures).length,
  sampleStations:f.examples}));
 const topCandidates=[];
 const seenCity=new Set(),seenRates=new Set();
 const sorted=examples.filter(x=>x.score>=0).sort((a,b)=>b.score-a.score);
 for(const row of sorted){
  if(topCandidates.length>=14)break;
  const city=row.city.toLowerCase(),uni=row.rateKey+'::'+row.typeKey;
  if(seenCity.has(city)&&seenRates.has(uni))continue;
  topCandidates.push(row);seenCity.add(city);seenRates.add(uni);
 }
 const compactExamples=topCandidates.map(x=>({name:x.name,city:x.city,address:x.address,postalCode:x.postalCode,locationId:x.locationId,
  nationalPowersKw:x.knownPowersKw,technicalTypes:x.typeKey,unknownEVSE:x.unknownTechnicalEvseCount,
  rates:x.possibleEnergyRatesEurPerKwh,feeTypes:x.feeTypes,fees:x.feeValues.slice(0,7),restrictions:x.restrictionNames,
  evseIds:x.evses.map(y=>y.id),evseTech:x.evses.slice(0,9),tariffIds:x.tariffIds,
  needFromApp:'Prix détaillé par connecteur/type AC-DC et conditions de frais/horaires; ne pas substituer prix CPO direct au prix Electra eMSP.'}));
 appChecks.push(...compactExamples.slice(0,8));
 groupResults[cpo]={inputCases:cases.length,totalStationLevelSourceTariffs:cases.reduce((t,c)=>t+(byId.get(String(c.locationId))?.chargeTariffs?.length||0),0),
  uniqueTariffIds:Object.keys(tids).length,
  technical:{evseCount:nationalEVSE,unknownTechnicalEvseCount:unknownTechnicalEVSE,acDcMixedLocations,acOnlyWithMultipleEnergyRates:acOnlyWithMultipleRates,
    dcOnlyWithMultipleEnergyRates:dcOnlyWithMultipleRates,explicitPowerScopeLocations:hasExplicitTariffPowerScope},
  hypothesis:{pureEnergyTwoRateMixedAcDcCandidates:pureEnergyTwoRateMixedType,
    pureEnergyMultiRateUnmapped:pureEnergyMultipleUnmapped,
    interpretation:'Energy rate co-occurrence and AC/DC mix are not proof of EVSE-level attribution.'},
  breakdown:{classes:classCounts,variationPatterns:patterns,
   allPureEnergyVsComplex:onlyEnergyCategories,typePatterns:tops(types),topRatePatterns:tops(ratePatterns,17),
   topPriceByType:tops(priceVsType,15),topPowerSets:tops(powerPatterns,15),topExtraFeeTypes:tops(feeTypes,15),
   topRestrictionTypes:tops(restrictionTypes,15),topTariffIdPatterns:tops(tariffIdPatterns,16)},
  reusableFamilies:familySorted.slice(0,28),appVerificationSamples:compactExamples};
}
const combined={schemaVersion:1,generatedAt:new Date().toISOString(),sourceSnapshot:manifest.generatedAt,
 residualCaseArchive:'reports/france/irve/electra-pricing-residual-cases-2026-10-08.json.gz',
 goals:['Find repeated eMSP tariff rule families within each CPO','Check AC/DC hypothesis without guessing any EVSE price',
  'Surface exact EVSE app-check examples','Distinguish ancillary/time restriction hazards'],
 operators:groupResults,appVerificationShortlist:appChecks,
 hardGuards:{notPublishedAutomatically:true,
   partnerTariffsNotDirectCpo:true,excludeNonPublicPremises:true,
   perEVSEAndPowerRequired:true,samePowerConflictingTariffsIncaclculable:true,
   uncertainDurationOrFeesIncalculable:true,unknownTechnicalKindNotAutoAssigned:true}};
const path='reports/france/electra/driveco-greenflux-tariff-family-audit-latest.json';
await fs.mkdir('reports/france/electra',{recursive:true});
await fs.writeFile(path,JSON.stringify(combined,null,2)+'\n');
const csvPath='reports/france/electra/driveco-greenflux-residual-families-latest.csv';
const fields=['cpo','locationId','name','city','postalCode','class','variation','typeKey','knownPowersKw','tariffCount','tariffIds',
 'possibleEnergyRatesEurPerKwh','feeTypes','restrictionNames','unknownTechnicalEvseCount','evseIds'];
const quote=v=>{const s=String(Array.isArray(v)?v.join('|'):v??'');return /[;"\n]/.test(s)?'"'+s.replaceAll('"','""')+'"':s;};
const lines=['\ufeff'+fields.join(';')];
for(const row of allRows){const flat={...row,evseIds:row.evses.map(e=>e.id)};lines.push(fields.map(f=>quote(flat[f])).join(';'));}
await fs.writeFile(csvPath,lines.join('\n')+'\n');
console.log(JSON.stringify({report:path,csv:csvPath,summary:Object.fromEntries(Object.entries(groupResults).map(([k,v])=>[k,{
 cases:v.inputCases,technical:v.technical,hypothesis:v.hypothesis,
 variation:v.breakdown.variationPatterns,
 tariffs:v.breakdown.topTariffIdPatterns.slice(0,7),
 rates:v.breakdown.topRatePatterns.slice(0,9),
 priceKinds:v.breakdown.topPriceByType.slice(0,6),
 fees:v.breakdown.topExtraFeeTypes,restrictions:v.breakdown.topRestrictionTypes,
 examples:v.appVerificationSamples.slice(0,6).map(x=>({name:x.name,city:x.city,locationId:x.locationId,
  powers:x.nationalPowersKw,types:x.technicalTypes,rates:x.rates,fees:x.fees,evseIds:x.evseIds.slice(0,4)}))
}]))},null,2).slice(0,25000));
