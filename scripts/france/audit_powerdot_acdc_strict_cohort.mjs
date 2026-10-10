import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const ungzip=async p=>JSON.parse(zlib.gunzipSync(await fs.readFile(p)).toString('utf8'));
const [source,national,proof]=await Promise.all([
ungzip('data/platforms/electra/france/source-locations.json.gz'),
ungzip('data/national/france-irve-static-v9/all.json.gz'),
fs.readFile('data/manual_verification/electra_powerdot_action_angouleme_2026-10-11.json','utf8').then(JSON.parse)]);
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const wanted=new Set([
'9d3380b6-bfef-4f52-a50e-11f72cff552c',
'6f46ce9f-5f71-4266-a07e-0e07231670d9',
'deb8f441-4306-4735-9990-3165dbeefffc'
]);
const evidence=new Map();
for(const station of national)for(const group of station[8]||[]){
 const kind=group[2],kw=Number(group[3]);
 for(const evseId of group[6]||[]){
  const id=norm(evseId);
  if(!id||!Number.isFinite(kw)||kw<=0)continue;
  if(!evidence.has(id))evidence.set(id,{types:new Set(),powers:new Set(),names:new Set()});
  const row=evidence.get(id);
  row.types.add(kind);row.powers.add(kw);row.names.add(station[1]);
 }
}
const validRestrictions=r=>Object.values(r||{}).every(v=>v==null||v===''||(Array.isArray(v)&&v.length===0));
const breakdown={};
const count=k=>(breakdown[k]=(breakdown[k]||0)+1);
const all=(source.locations||[]).filter(l=>l.cpo?.name==='Powerdot');
const eligible=[],exceptions=[],cpos=[];
for(const loc of all){
 const ts=loc.chargeTariffs||[],tariffInfo=ts.map(t=>{
   const elements=t.elements||[];
   const rates=elements.flatMap(e=>(e.priceComponents||[]).filter(p=>p.type==='ENERGY').map(p=>Number(p.price)));
   const onlyEnergy=elements.length>0&&elements.every(e=>(e.priceComponents||[]).length>0&&
    (e.priceComponents||[]).every(p=>p.type==='ENERGY'&&Number.isFinite(Number(p.price)))&&validRestrictions(e.restrictions));
   const prices=[...new Set(rates)].sort((a,b)=>a-b);
   return{id:t.chargeTariffId,onlyEnergy,prices}
 });
 if(!ts.length){count('no_tariff');continue}
 const sig=tariffInfo.map(t=>t.id).sort().join('|');
 const idsSet=new Set(tariffInfo.map(t=>t.id));
 if(tariffInfo.some(t=>!wanted.has(t.id))){count('outside_verified_tariff_family');continue}
 if(!tariffInfo.every(t=>t.onlyEnergy&&t.prices.length===1)){count('fee_restriction_or_ambiguous_rate');continue}
 const acT=tariffInfo.filter(t=>t.prices[0]===0.49);
 const dcT=tariffInfo.filter(t=>t.prices[0]===0.62);
 if(acT.length!==1||!dcT.length||acT.length+dcT.length!==tariffInfo.length){count('missing_or_mixed_acdc_rates');continue}
 const evses=(loc.evses||[]).map(e=>{
  const t=evidence.get(norm(e.evseId));
  const kinds=t?[...t.types]:[],powers=t?[...t.powers]:[];
  return{id:e.evseId,status:e.status,physicalReference:e.physicalReference,
   kind:kinds.length===1?kinds[0]:'UNKNOWN_OR_MIXED',powersKw:powers};
 });
 if(!evses.length){count('no_evse');continue}
 const bad=evses.filter(e=>!['AC','DC'].includes(e.kind)||e.powersKw.length!==1);
 if(bad.length){count('missing_or_mixed_exact_evse_kind_or_power');exceptions.push({id:loc.id,name:loc.name,bad});continue}
 if(/garage|concession|concessionnaire|centre auto|automobile|porsche|mercedes|bmw|audi|citro[eë]n|peugeot|renault|volkswagen|ford|toyota|hyundai|kia|opel|nissan/i.test(loc.name||'')){count('dealer_or_nonpublic_access_uncertain');continue}
 const obs=evses.map(e=>({...e,price:e.kind==='AC'?0.49:0.62,
  selectedTariffIds:(e.kind==='AC'?acT:dcT).map(t=>t.id)}));
 // All tariff IDs on any single EVSE must have the exact same compiled price
 // and restrictions. Two 0.62 ENERGY-only IDs are economically equivalent.
 const record={locationId:loc.id,name:loc.name,city:loc.city,tariffIds:[...idsSet].sort(),evses:obs,
  hasAc:evses.some(e=>e.kind==='AC'),hasDc:evses.some(e=>e.kind==='DC'),signature:sig};
 eligible.push(record);
 count('strict_cohort_eligible');
}
const action=eligible.find(x=>x.locationId===proof.locationId);
const actionSource=all.find(x=>x.id===proof.locationId);
const report={schemaVersion:1,generatedAt:new Date().toISOString(),
 input:{locationsTotal:source.locations.length,powerdotLocations:all.length,proofLocationId:proof.locationId},
 tariffsPolicy:"Only the three exact recurring Powerdot pure-energy chargeTariffIds, with 0.49 AC and 0.62 DC, no other tariff components/restrictions, unique national exact EVSE kind + nominal power. Two DC IDs are equivalent only if both compiled offers are identical. No silent tariff selection for conflicting same-kind offers.",
 classification:breakdown,
 eligible:{stations:eligible.length,allKindsStations:eligible.filter(x=>x.hasAc&&x.hasDc).length,
 acOnlyStations:eligible.filter(x=>x.hasAc&&!x.hasDc).length,dcOnlyStations:eligible.filter(x=>x.hasDc&&!x.hasAc).length,
 totalEvse:eligible.reduce((n,x)=>n+x.evses.length,0),
 acEvse:eligible.reduce((n,x)=>n+x.evses.filter(y=>y.kind==='AC').length,0),
 dcEvse:eligible.reduce((n,x)=>n+x.evses.filter(y=>y.kind==='DC').length,0),
 byTariffCombination:Object.entries(eligible.reduce((m,x)=>(m[x.signature]=(m[x.signature]||0)+1,m),{})).sort((a,b)=>b[1]-a[1]).map(([ids,stations])=>({ids,stations})),
 exampleAction:action??null,
 sample:eligible.slice(0,6),
 fullLocationList:eligible.map(x=>({locationId:x.locationId,name:x.name,city:x.city,evseCount:x.evses.length,ac:x.evses.filter(y=>y.kind==='AC').length,dc:x.evses.filter(y=>y.kind==='DC').length,ids:x.tariffIds}))},
 exceptions:exceptions.slice(0,15),noAutomaticPublication:true};
await fs.mkdir('reports/france/electra',{recursive:true});
await fs.writeFile('reports/france/electra/powerdot-acdc-strict-cohort-audit-latest.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({classification:breakdown,eligible:report.eligible,action:action??actionSource?.name??'missing'},null,2).slice(0,13500));
