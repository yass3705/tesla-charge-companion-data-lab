#!/usr/bin/env node
'use strict';
/** Evidence-only inventory for the 78 sampled Electra eMSP pricing offers whose
 * afterMinutesRate is not supported by a source-confirmed billing dimension.
 * Does NOT alter rates, decide source semantics or release prices.
 */
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),dir=path.join(root,'reports/tariff-scenarios');
const rows=JSON.parse(fs.readFileSync(path.join(dir,'france-real-offer-fixtures.json'),'utf8'));
const all=rows.filter(x=>(x.provider||'').includes('Electra eMSP')&&
 x.offer?.pricing?.rules?.some(r=>Number(r.afterMinutesRate)>0));
const entries=[];
for(const x of all){
 const offer=x.offer;
 const rules=(offer.pricing.rules||[]).filter(r=>Number(r.afterMinutesRate)>0);
 const parts=offer.id.split(':');
 for(const r of rules)entries.push({
  offerId:offer.id,provider:x.provider,
  tariffGroupId:parts[1]||null,evseRef:parts.slice(2).join(':')||null,
  afterMinutesRateEur:Number(r.afterMinutesRate),afterMinutesThresholdMinutes:Number(r.afterMinutesThreshold),
  afterMinutesComponent:r.afterMinutesComponent||null,afterMinutesCap:r.afterMinutesCap??null,
  afterMinutesCapStart:r.afterMinutesCapStart??null,afterMinutesCapEnd:r.afterMinutesCapEnd??null,
  source:x.origin||null,sourceMetadata:offer.metadata?.source||offer.source||null,
  cpoEvidence:offer.metadata?.operator||offer.metadata?.cpo||null,
  decision:'TARIF_INCALCULABLE_COMPONENT_UNVERIFIED'
 });
}
const groups={};
for(const v of entries){
 const key=[v.tariffGroupId,v.afterMinutesRateEur,v.afterMinutesThresholdMinutes,v.afterMinutesCap,v.afterMinutesCapStart,v.afterMinutesCapEnd].join('|');
 const g=groups[key]||{tariffGroupId:v.tariffGroupId,rateEurPerMin:v.afterMinutesRateEur,
  thresholdMinutes:v.afterMinutesThresholdMinutes,afterMinutesCap:v.afterMinutesCap,
  afterMinutesCapStart:v.afterMinutesCapStart,afterMinutesCapEnd:v.afterMinutesCapEnd,offers:0,exampleIds:[]};
 g.offers++;
 if(g.exampleIds.length<4)g.exampleIds.push(v.offerId);
 groups[key]=g;
}
const report={schemaVersion:1,generatedAt:new Date().toISOString(),
 scope:'78 Electra eMSP real offers sampled in 2026-10-10 audit, NOT CPO Electra direct',
 sampledOfferCount:all.length,activeRuleRows:entries.length,uniqueTariffProfiles:Object.keys(groups).length,
 profiles:Object.values(groups).sort((a,b)=>b.offers-a.offers),entries,
 policy:'No afterMinutesComponent can be inferred from station CPO Electra policy or another eMSP. Need charging / parking / connected time contract per tariff group. Until then TCC must display Tarif incalculable.',
 publication:false};
if(all.length!==78)throw Error('Expected 78 affected Electra eMSP offers; found '+all.length);
const fn=path.join(dir,'electra-78-afterminutes-evidence-matrix-2026-10-11.json');
fs.writeFileSync(fn,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({status:'PASS',offers:all.length,profiles:report.uniqueTariffProfiles,rows:entries.length}));
