'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const [ref,input]=process.argv.slice(2),data=JSON.parse(fs.readFileSync(input,'utf8'));
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'tcc-g66-'));
try{
 for(const name of ['offer-engine.js','pricing-engine.js','session-engine.js','bridge.js'])fs.copyFileSync(path.join(ref,name),path.join(tmp,name));
 fs.writeFileSync(path.join(tmp,'package.json'),'{"type":"commonjs"}');
 const original=require(path.join(tmp,'session-engine.js')),bridge=require(path.join(tmp,'bridge.js'));
 const raw=fs.readFileSync(path.join(tmp,'session-engine.js'),'utf8');
 const anchor=':unknownPostCharge&&postChargeMinutes>0';
 assert.equal(raw.split(anchor).length,2);
 const patched=raw.replace(anchor,":offer?.metadata?.g66Diagnostic===true\n        ?(typeof options.g66Quote==='function'?options.g66Quote(station,offer,profile,currentSession):{complete:false,reason:'g66_quote_unavailable'})\n        "+anchor);
 fs.writeFileSync(path.join(tmp,'session-engine-g66.js'),patched);
 const candidate=require(path.join(tmp,'session-engine-g66.js'));
 const pairs=new Map(data.projection.map(r=>[r.national_id,r]));
 const quotes=new Map(data.quotes.map(q=>[q.signature+'|'+q.scenario,q]));
 assert.equal(pairs.size,24115);assert.equal(quotes.size,786);
 const allowed=new Set(['DIAGNOSTIC_ESTIMATE_AGREEMENT','SEGMENT_ROUNDING_EXPLAINED']);
 const sessionFor=f=>({startAt:f.startAt,timeZone:'Europe/Paris',energyKwh:Number(f.energy),durationMinutes:Number(f.duration),chargingMinutes:Number(f.charging),postChargeMinutes:Number(f.parking),consumptionKwhPer100Km:18,includeCongestionFees:true});
 const asSeconds=x=>typeof x==='number'&&Number.isFinite(x)&&Math.abs(x*60-Math.round(x*60))<1e-8?Math.round(x*60):null;
 function quoteFor(f){
  const s=sessionFor(f);
  return(station,o,profile,current)=>{
   const reject=reason=>({complete:false,reason,currency:'EUR'});
   const m=o.metadata,p=pairs.get(m.nationalId);
   if(station.countryCode!=='FR'||o.provider!=='Electroverse'||o.kind!=='roaming'||!p||station.id!==p.station_id||m.sourceId!==p.source_id||m.signature!==p.tariff_signature||profile.connectorId!=='g66-irve-'+p.national_id)return reject('g66_identity_scope_mismatch');
   if(!(Number(p.national_kw)>0))return reject('g66_invalid_national_power');
   if(current.timeZone!=='Europe/Paris'||current.startAt!==s.startAt||current.energyKwh!==s.energyKwh||asSeconds(current.durationMinutes)!==f.seconds||asSeconds(current.chargingMinutes)!==f.chargeSeconds||asSeconds(current.postChargeMinutes)!==f.parkSeconds||typeof current.includeCongestionFees!=='boolean')return reject('g66_session_mismatch');
   const q=quotes.get(p.tariff_signature+'|'+f.id);
   if(!q||!allowed.has(q.decision))return reject(q?.reason||q?.decision||'g66_quote_unavailable');
   const n=Number(q.estimate_eur);
   if(q.estimate_eur===''||!Number.isFinite(n)||n<0)return reject('g66_invalid_estimate');
   return{complete:true,currency:'EUR',totalEur:n,components:JSON.parse(q.segment_oracle&&q.decision==='SEGMENT_ROUNDING_EXPLAINED'?q.segment_oracle:q.oracle),diagnosticOnly:true};
  };
 }
 function stationFor(p){
  return{id:p.station_id,name:p.station_id,countryCode:'FR',timeZone:'Europe/Paris',physicalOperator:'IRVE fixture',evses:[{id:p.evse_id,evseId:p.evse_id,connectors:[{id:'g66-irve-'+p.national_id,plugName:p.national_plug,kind:p.national_mode,powerKw:Number(p.national_kw)}]}],offers:[{id:'g66-electroverse-'+p.national_id,provider:'Electroverse',kind:'roaming',countries:['FR'],currency:'EUR',evseIds:[p.evse_id],connectorIds:['g66-irve-'+p.national_id],connectorKinds:[p.national_mode],pricing:{type:'rules',rules:[]},metadata:{g66Diagnostic:true,nationalId:p.national_id,sourceId:p.source_id,signature:p.tariff_signature}}]};
 }
 function evaluate(station,s,quote){return candidate.evaluateStation(station,s,{g66Quote:quote});}
 const guards={},coverage=[];
 let checks=0;
 for(const f of data.fixtures){
  const s=sessionFor(f),quote=quoteFor(f);let eligible=0,reviewEligible=0,baselineEligible=0,unknown=0,zeroPower=0;const ranking=new Map();
  for(const p of data.projection){
   const st=stationFor(p),ev=evaluate(st,s,quote),q=quotes.get(p.tariff_signature+'|'+f.id),powerOK=Number(p.national_kw)>0,good=allowed.has(q.decision)&&powerOK;
   const lane=bridge.tariffLaneState(ev,st,'electroverse');
   if(!powerOK)zeroPower++;
   assert.equal(Boolean(ev.best),good,JSON.stringify({p,scenario:f.id,decision:q.decision,ev}));
   if(good){
    assert.equal(ev.eligibleOfferCount,1);assert.equal(lane.status,'priced');assert.equal(ev.best.total,Number(q.estimate_eur));
    assert.equal(ev.best.connectorId,'g66-irve-'+p.national_id);
    eligible++;if(p.g6_calculability==='NOT_YET_CERTIFIED')reviewEligible++;else baselineEligible++;
    assert.equal(ev.best.costPerRecoveredKm,s.energyKwh>0?Math.round((Number(q.estimate_eur)/(s.energyKwh/(18/100))+Number.EPSILON)*1e6)/1e6:null);
   }else{
    if(powerOK){assert.equal(ev.incomplete.length,1);assert.ok(ev.incomplete[0].result.reason);assert.ok(['unresolved','ambiguous'].includes(lane.status));}
    else {assert.ok(ev.eligibleOfferCount===0||ev.incomplete[0]?.result.reason==='g66_invalid_national_power');}
    unknown++;
   }
   checks++;
   if(!ranking.has(p.tariff_signature))ranking.set(p.tariff_signature,{station:{id:p.national_id,name:p.national_id},total:ev.best?.total??null,costPerKm:ev.best?.costPerRecoveredKm??null,distanceKm:1,evaluation:ev});
  }
  const rankRows=[...ranking.values()];
  for(const mode of ['price','costPerKm']){
   const ordered=bridge.rankRows(rankRows.slice(),mode,rankRows.length);assert.equal(ordered.length,262);
   let seenUnknown=false;
   for(const r of ordered){if(r.total===null)seenUnknown=true;else assert.equal(seenUnknown,false);}
   assert.equal(bridge.rankRows(rankRows.slice(),mode,20).length,20);
  }
  coverage.push({scenario:f.id,eligible,reviewEligible,baselineEligible,unknown,zeroPower});
 }
 const f=data.fixtures[0],s=sessionFor(f),quote=quoteFor(f),p=data.projection.find(x=>Number(x.national_kw)>0&&allowed.has(quotes.get(x.tariff_signature+'|'+f.id).decision)),st=stationFor(p);
 const noQuote=candidate.evaluateStation(st,s);guards.noQuoteFailsClosed=!noQuote.best&&noQuote.incomplete[0]?.result.reason==='g66_quote_unavailable';
 guards.changedEnergyFailsClosed=!evaluate(st,{...s,energyKwh:s.energyKwh+1},quote).best;
 guards.changedTimeFailsClosed=!evaluate(st,{...s,startAt:'2026-11-25T12:08:00Z'},quote).best;
 guards.missingParkingFailsClosed=!evaluate(st,{...s,postChargeMinutes:null},quote).best;
 guards.missingCongestionOptionFailsClosed=!evaluate(st,{...s,includeCongestionFees:undefined},quote).best;
 guards.routeEnergyFailsClosed=!evaluate({...st,route:{approachEnergyKwh:1}},s,quote).best;
 const foreign=structuredClone(st);foreign.id+='-wrong';guards.wrongStationFailsClosed=!evaluate(foreign,s,quote).best;
 const other=structuredClone(st);other.offers[0].metadata.sourceId='wrong';guards.wrongSourceFailsClosed=!evaluate(other,s,quote).best;
 const off=structuredClone(st);off.evses[0].connectors[0].status='out_of_service';guards.unusableConnectorExcluded=evaluate(off,s,quote).eligibleOfferCount===0;
 guards.powerFilter=bridge.variantMatchesFilters({powerLine:{kind:p.national_mode,powerKw:Number(p.national_kw)}},{connectorKinds:[p.national_mode],minPowerKw:Number(p.national_kw)})&&!bridge.variantMatchesFilters({powerLine:{kind:p.national_mode,powerKw:Number(p.national_kw)}},{minPowerKw:Number(p.national_kw)+1});
 function ordinary(provider,kind,cc,rate,fee=0){return{id:provider+'-fixture',provider,kind,countries:[cc],currency:'EUR',pricing:{type:'rules',rules:[{scope:'allDay',start:'00:00',end:'24:00',currency:'EUR',pricePerKwh:rate,chargePerMinute:0,idlePerMinute:0,connectionFee:0,...(fee?{congestionTimePerMinute:fee,congestionStartSoc:80}:{})}]}};}
 const multi=structuredClone(st);multi.offers.push(ordinary('Direct fixture','direct','FR',0.5),ordinary('Electra','roaming','FR',0.6));
 const ev=evaluate(multi,s,quote);
 guards.threeChannels=['direct','electra','electroverse'].every(k=>bridge.tariffLaneState(ev,multi,k).status==='priced');
 guards.bestMinimum=ev.best.total===Math.min(...[ev.best,...ev.alternatives].map(x=>x.total));
 const only=structuredClone(multi);only.offers=only.offers.filter(o=>!o.metadata?.g66Diagnostic);
 guards.otherChannelsIdentical=JSON.stringify(original.evaluateStation(only,s))===JSON.stringify(evaluate(only,s,quote));
 const feeStation=structuredClone(only);feeStation.offers=[ordinary('Direct congestion fixture','direct','FR',0.5,0.1)];
 const feeSession={...s,startSoc:85,arrivalSoc:85,targetSoc:95};
 const fee=candidate.evaluateStation(feeStation,feeSession,{g66Quote:quote}),oldFee=original.evaluateStation(feeStation,feeSession);
 guards.congestionNativeUnchanged=JSON.stringify(fee)===JSON.stringify(oldFee)&&fee.best?.congestion?.available===true&&fee.best.congestion.totalWithoutCongestion<=fee.best.total;
 const countries=['IT','CH','DE','ES','NL','GB','MA','BE'];
 guards.otherCountriesUnchanged=countries.every(cc=>{const x=structuredClone(only);x.countryCode=cc;x.offers=[ordinary('Electroverse','roaming',cc,0.5),ordinary('Tesla','direct',cc,0.4)];return JSON.stringify(original.evaluateStation(x,s))===JSON.stringify(evaluate(x,s,quote));});
 guards.zeroEnergyUndefined=candidate.recoveredKm({...s,energyKwh:0})===null;
 assert.ok(Object.values(guards).every(Boolean),JSON.stringify(guards));
 process.stdout.write(JSON.stringify({identityPairs:pairs.size,runtimeOfferChecks:checks,coverage,guards,countriesSynthetic:countries,rankingSampleSignatures:262,productionCommit:data.productionCommit}));
}finally{fs.rmSync(tmp,{recursive:true,force:true});}
