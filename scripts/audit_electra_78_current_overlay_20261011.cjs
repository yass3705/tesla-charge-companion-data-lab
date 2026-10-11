#!/usr/bin/env node
'use strict';
/* Historical 78 eMSP offers vs current published Electra France tiles; read-only. */
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const reportDir=path.join(root,'reports/tariff-scenarios');
const overlay=path.join(root,'data/platforms/electra/france');
const pilot=JSON.parse(fs.readFileSync(path.join(reportDir,'france-pricing-pilot-latest.json')));
const old=pilot.unmodeledExamples.filter(x=>x.provider==='Electra eMSP');
if(old.length!==78)throw Error('Expected 78 historical Electra rows, got '+old.length);
const wanted=new Set(old.map(x=>x.offerId));
const manifest=JSON.parse(fs.readFileSync(path.join(overlay,'manifest.json')));
const byId=new Map(),duplicateMatches=[];
let allOffers=0,readTiles=0;
for(const tile of manifest.tiles||[]){
 const obj=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(overlay,tile.file))));
 readTiles++;
 for(const offer of obj.emspOffers||[]){
  allOffers++;
  if(!wanted.has(offer.id))continue;
  if(byId.has(offer.id))duplicateMatches.push(offer.id);
  byId.set(offer.id,offer);
 }
}
const stats={historical:old.length,historicalUniqueIds:wanted.size,matched:0,
 missing:0,nowHasExplicitComponent:0,stillWithoutComponent:0,
 computed:0,incalculable:0,missingActiveRule:0,unsupportedComponent:0,byReason:{},
 byProvider:{},byComponent:{},examples:[],missingExamples:[]};
const engineFile=process.argv[2];
const engine=engineFile?require(path.resolve(engineFile)):null;
for(const h of old){
 const offer=byId.get(h.offerId);
 if(!offer){stats.missing++;if(stats.missingExamples.length<20)stats.missingExamples.push(h.offerId);continue;}
 stats.matched++;
 const active=(offer.pricing?.rules||[]).filter(r=>Number(r.afterMinutesRate)>0);
 if(!active.length){stats.missingActiveRule++;if(stats.examples.length<35)stats.examples.push({id:h.offerId,issue:'NO_ACTIVE_AFTERMINUTES'});continue;}
 const comp=[...new Set(active.map(r=>r.afterMinutesComponent||null))];
 for(const c of comp)stats.byComponent[c||'MISSING']=(stats.byComponent[c||'MISSING']||0)+1;
 const explicit=active.every(r=>['TIME','PARKING_TIME','CONNECTED_TIME'].includes(r.afterMinutesComponent));
 if(explicit)stats.nowHasExplicitComponent++;else stats.stillWithoutComponent++;
 let state=null,reason=null,price=null;
 if(engine){
  const session={energyKwh:20,durationMinutes:210,chargingMinutes:180,totalChargingMinutes:180,
   startAt:'2026-10-11T10:00:00+02:00',timeZone:'Europe/Paris',powerKw:22,vehicleSoc:50,targetSoc:80,
   includeCongestionFees:true,postChargeMinutes:30};
  const result=engine.evaluateOffer(offer,session);
  state=result.complete===true?'COMPUTED':'TARIF_INCALCULABLE';
  reason=result.reason||null;price=result.totalEur??null;
  if(result.complete===true)stats.computed++;else{
   stats.incalculable++;stats.byReason[reason||'UNKNOWN']=(stats.byReason[reason||'UNKNOWN']||0)+1;
  }
 }
 if(stats.examples.length<45)stats.examples.push({id:h.offerId,component:comp,rate:active.map(r=>r.afterMinutesRate),
  thresholds:active.map(r=>r.afterMinutesThreshold),state,reason,price});
}
const out={schemaVersion:1,at:new Date().toISOString(),sourceManifestAt:manifest.generatedAt,
 sourceManifestHash:crypto.createHash('sha256').update(fs.readFileSync(path.join(overlay,'manifest.json'))).digest('hex'),
 sourceFilesRead:readTiles,allPublishedOverlayOffers:allOffers,stats,
 decisions:{
  missing:'Do not infer unpub offer, status and identity must be checked separately.',
  explicit:'Compute only when afterMinutesComponent is unambiguously TIME or PARKING_TIME or CONNECTED_TIME.',
  unverified:'Tarif incalculable, not 0 or an inferred dimension',
  thisAudit:'Does not change source, publish prices, or infer that a published EVSE is accessible to the public.'}};
const target=path.join(reportDir,'electra-78-current-overlay-validation-2026-10-11.json');
fs.writeFileSync(target,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({RESULT:'PASS',sourceManifest:out.sourceManifestAt,readTiles,allOffers,
 ...Object.fromEntries(Object.entries(stats).filter(([k,v])=>typeof v==='number')),
 reasons:stats.byReason,components:stats.byComponent}));
if(duplicateMatches.length){console.error('DUPLICATE_MATCH_IDS',duplicateMatches.slice(0,15));process.exitCode=1;}
if(stats.matched+stats.missing!==old.length){console.error('coverage mismatch');process.exitCode=1;}
