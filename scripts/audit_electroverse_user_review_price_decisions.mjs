import fs from 'node:fs/promises';
const POLICY='data/platforms/electroverse/validated-mappings/price-disputes-review-2026-10-11.json';
const STATUS='reports/electroverse/status-filter-2026-10-10.json';
const EVIDENCE='reports/electroverse/full-reconciliation/priority-review-evidence.json';
const OUTPUT='reports/electroverse/price-disputes-23-validation-2026-10-11.json';
const norm=s=>String(s||'').replace(/[^A-Z0-9]/gi,'').toUpperCase();
const policy=JSON.parse(await fs.readFile(POLICY,'utf8'));
const filter=JSON.parse(await fs.readFile(STATUS,'utf8'));
const source=JSON.parse(await fs.readFile(EVIDENCE,'utf8'));
const error=(m)=>{throw Error('Electroverse user reviewed price policy regression: '+m)};
if(policy.samePowerDisputes.length!==15||policy.chargezyPowerVariants.length!==8)error('expected 15 same-power and 8 power-split identities');
const targets=filter.records.filter(r=>r.verdict==='TARIF_AMBIGU');
if(targets.length!==23)error('23 live-validated conflicts expected');
const byKey=new Map(targets.map(x=>[String(x.locationPk)+'|'+norm(x.evse),x]));
const outcome={schemaVersion:1,createdAt:new Date().toISOString(),policyPath:POLICY,
 sourceStatusReport:STATUS,sourcePricingEvidence:EVIDENCE,
 sourceStatusSnapshotAt:filter.generatedAt,
 evaluated:0,quarantineSamePower:0,chargezyPowerSplit:0,
 eligibleActiveVariants:0,validatedPowerOffers:0,safeToPublishNationalOverlay:false,
 tests:[],failures:[]};
const parseMoney=(entry,kind)=>{
 const label=entry.components.find(y=>y[0]===kind)?.[1]||'';
 const found=label.match(/€\s*(-?[0-9.]+)/);
 return found?Number(found[1]):0;
};
const detail=x=>source.reviewRows.filter(z=>z.stationId===x.stationId&&norm(z.evse)===norm(x.physicalReference));
const checkStatus=(x,sourcePks)=>{
 const observed=byKey.get(String(x.locationPk)+'|'+norm(x.physicalReference));
 if(!observed)error('reviewed identity missing from eligible snapshot: '+x.physicalReference);
 const eligible=new Set(observed.keptPk.map(String));
 for(const pk of sourcePks)if(!eligible.has(String(pk)))error('source PK not eligible in priority snapshot: '+x.physicalReference+' '+pk);
 return observed;
};
for(const x of policy.samePowerDisputes){
 const raw=detail(x).filter(v=>x.sourcePks.map(String).includes(String(v.sourcePk)));
 if(raw.length!==2)error('two pricing profiles required '+x.physicalReference);
 checkStatus(x,x.sourcePks);
 const pow=new Set(raw.flatMap(v=>v.fullPrice.map(z=>Number(z.kw))));
 if(pow.size!==1||![...pow].includes(x.commonPowerKw))error('same-power ambiguity power mismatch '+x.physicalReference);
 const prices=new Set(raw.map(v=>JSON.stringify(v.fullPrice.map(z=>({kw:z.kw,components:z.components,restrictions:z.restrictions})))));
 if(prices.size!==2)error('two different price signatures expected '+x.physicalReference);
 outcome.quarantineSamePower++;outcome.eligibleActiveVariants+=2;outcome.evaluated++;
 outcome.tests.push({evse:x.physicalReference,locationPk:x.locationPk,
  verdict:'TARIF_INCALCULABLE_IF_BOTH_SOURCE_PKS_ELIGIBLE',sourcePks:x.sourcePks,powerKw:x.commonPowerKw,
  sourcePricingConflict:true});
}
for(const x of policy.chargezyPowerVariants){
 const activePks=Object.values(x.sourcePkByPowerKw).map(String);
 checkStatus(x,activePks);
 const raw=detail(x).filter(v=>activePks.includes(String(v.sourcePk)));
 if(raw.length!==2)error('two verified source groups required '+x.physicalReference);
 const powerRows=[];
 for(const [label,sourcePk] of Object.entries(x.sourcePkByPowerKw)){
  const kw=Number(label),expectedRate=kw===25?0.59:kw===31?0.69:null;
  if(expectedRate==null)error('unvalidated power '+kw);
  const matching=raw.find(v=>String(v.sourcePk)===String(sourcePk));
  if(!matching)error('missing power-source match '+x.physicalReference+' '+kw);
  if(!matching.fullPrice.length||matching.fullPrice.some(p=>Number(p.kw)!==kw||
      Math.abs(parseMoney(p,'ConsumptionRate')-expectedRate)>0.00001||
      Math.abs(parseMoney(p,'ConnectionFee')-2)>0.00001))
    error('chargezy source pricing/power mismatch '+x.physicalReference+' kw='+kw);
  powerRows.push({kw,sourcePk,energyEuroPerKwh:expectedRate,connectionEuro:2,
    connectors:matching.fullPrice.length});
 }
 if(powerRows.length!==2||new Set(powerRows.map(v=>v.kw)).size!==2)error('power variants collapsed '+x.physicalReference);
 outcome.chargezyPowerSplit++;outcome.evaluated++;outcome.eligibleActiveVariants+=2;
 outcome.validatedPowerOffers+=2;
 outcome.tests.push({evse:x.physicalReference,locationPk:x.locationPk,verdict:'VALIDATED_DISTINCT_POWER_VARIANTS',
  powerRows:powerRows.sort((a,b)=>a.kw-b.kw)});
}
if(outcome.evaluated!==23||outcome.quarantineSamePower!==15||outcome.chargezyPowerSplit!==8||outcome.validatedPowerOffers!==16)
 error('aggregate accounting mismatch');
const builder=await fs.readFile('scripts/build_electroverse_france_evse_overlay.mjs','utf8');
const must=[
 'quarantineConflictingReviewedRows(filterElectroverseRow(sourceRow,true),true)',
 'quarantineConflictingReviewedRows(filterElectroverseRow(sourceRow))',
 'reviewedChargezyByRef.get(reviewedKey(row.electroverseLocationPk,pr))',
 'unique.length!==1 || validatedChargezyPower',
 '? \'|CONNECTOR_POWER|\'+String(powerKey)',
 'reviewedDisputes:{reviewedAt:'
];
for(const token of must)if(!builder.includes(token))error('builder missing implementation: '+token);
outcome.builderContractChecked=true;
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUTPUT,JSON.stringify(outcome,null,2)+'\n');
console.log(JSON.stringify({result:'PASS',reviewed:outcome.evaluated,
 quarantinedSamePower:outcome.quarantineSamePower,chargezyPowerSplit:outcome.chargezyPowerSplit,
 powerOfferVariants:outcome.validatedPowerOffers,nationalPublished:false}));
