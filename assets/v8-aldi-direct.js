// Tesla Charge Companion V8 — ALDI France CPO-direct, strict physical operator only.
(function(){
  'use strict';
  const REVISION='aldi-direct-v1b-20260826';
  const SOURCE='https://www.aldi.fr/services/borne-recharge.html';
  const CPO_SOURCE='https://afirev.fr/en/list-of-assigned-identifiers/';
  const text=v=>String(v==null?'':v).trim();
  const norm=v=>text(v).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();

  function operatorCorpus(st){return [st?.operator,st?._sourceOperator,st?.cpo,st?.network,st?.networkName,st?.partyId,st?.cpoId].map(text).filter(Boolean).join(' | ')}
  function identityCorpus(st){return [operatorCorpus(st),st?.id,st?.catalogStationId,st?.stationId,st?.evseId,st?.evseUid].map(text).filter(Boolean).join(' | ')}
  function hasFrAln(st){return /FR\s*\*?\s*ALN(?:\s*\*|\b)/i.test(identityCorpus(st))||norm(identityCorpus(st)).includes('fraln')}
  function isExplicitAldiOperator(st){
    const n=norm(operatorCorpus(st));
    return n==='aldi'||n==='aldi sarl'||n==='aldi nord'||n==='aldi nord charging'||n.includes(' aldi sarl ')||n.startsWith('aldi sarl ')||n.includes(' aldi nord ')||n.startsWith('aldi nord ');
  }
  function hasExplicitThirdPartyOperator(st){
    const n=` ${norm(operatorCorpus(st))} `;
    return ['powerdot','power dot','r3','dbt','e totem','etotem','driveco','allego','electra','freshmile','izivia','bump','qovoltis'].some(x=>n.includes(` ${norm(x)} `));
  }
  function isAldiPhysical(st){
    if(!st||String(st.countryCode||'FR').toUpperCase()!=='FR')return false;
    if(hasFrAln(st))return true;
    if(hasExplicitThirdPartyOperator(st))return false;
    return isExplicitAldiOperator(st);
  }

  function physicalGroups(st){
    const source=Array.isArray(st?.chargingConfigurations)&&st.chargingConfigurations.length?st.chargingConfigurations:[{kind:st?.kind,powerKw:st?.powerKw,stalls:st?.stalls}];
    const groups=new Map();
    for(const c of source){
      if(c?.aldiDirect===true)continue;
      const kind=text(c?.kind||st?.kind).toUpperCase(),power=Number(c?.powerKw??st?.powerKw??0);
      if(!['AC','DC'].includes(kind)||!(power>0))continue;
      const key=`${kind}|${power.toFixed(2)}`,stalls=Math.max(0,Number(c?.stalls||st?.stalls||0));
      const old=groups.get(key);if(!old||stalls>old.stalls)groups.set(key,{kind,powerKw:power,stalls});
    }
    return [...groups.values()];
  }
  function tariffFor(g){
    if(g.kind==='AC'&&g.powerKw>0&&g.powerKw<=22.5)return{id:'aldi-fr-ac-direct',price:.29};
    if(g.kind==='DC'&&g.powerKw>=45&&g.powerKw<=55)return{id:'aldi-fr-dc50-direct',price:.35};
    return null;
  }
  function pricing(price){return{type:'rules',rules:[{scope:'allDay',start:'00:00',end:'24:00',billing:'kwh',currency:'EUR',pricePerKwh:price,chargePerMinute:0,connectionFee:0,idlePerMinute:0,afterMinutesRate:0,afterMinutesThreshold:0,afterMinutesCap:0,afterMinutesCapStart:'00:00',afterMinutesCapEnd:'24:00'}],aldiExactDirect:true}}
  function providerOf(c){return norm(c?.offerProvider||text(c?.label).split('·')[0])}
  function mergeConfigurations(existing,direct){
    const kept=(existing||[]).filter(c=>!c?.aldiDirect&&providerOf(c)!=='aldi direct');
    return [...direct,...kept];
  }
  function directConfigurations(st){
    if(!isAldiPhysical(st))return[];
    const out=[];
    for(const g of physicalGroups(st)){
      const t=tariffFor(g);if(!t)continue;
      const suffix=`${g.kind.toLowerCase()}-${String(g.powerKw).replace('.','_')}`;
      out.push({id:`aldi-direct-${t.id}-${suffix}`,label:`ALDI Direct · ${g.kind} ${g.powerKw} kW`,kind:g.kind,powerKw:g.powerKw,stalls:g.stalls,pricing:pricing(t.price),offerProvider:'ALDI Direct',offerType:'operator_direct',aldiDirect:true,aldiVerified:true,aldiCpoPartyId:'FRALN',aldiTariffId:t.id,aldiSource:SOURCE,aldiCpoSource:CPO_SOURCE,aldiVerifiedAt:'2026-08-26'});
    }
    return out;
  }
  function mergeStation(st){
    if(!isAldiPhysical(st))return st;
    const direct=directConfigurations(st),groups=physicalGroups(st);
    const unresolved=groups.filter(g=>!tariffFor(g)).map(g=>`${g.kind}:${g.powerKw}`);
    if(!direct.length)return{...st,aldiStrictCpo:true,aldiPricingStatus:'unresolved_power',aldiUnresolvedConfigurations:unresolved};
    const configs=mergeConfigurations(st.chargingConfigurations,direct),first=direct[0];
    return{...st,chargingConfigurations:configs,pricing:st.pricing||first.pricing,operator:st.operator||'ALDI',aldiStrictCpo:true,aldiPricingStatus:unresolved.length?'partial':'verified',aldiDirectOfferCount:direct.length,aldiUnresolvedConfigurations:unresolved};
  }
  function overlayPrepared(prepared){
    if(!prepared||!Array.isArray(prepared.stations))return prepared;
    let verified=0,partial=0,unresolved=0,offers=0;
    prepared.stations=prepared.stations.map(st=>{
      if(!isAldiPhysical(st))return st;
      const merged=mergeStation(st);offers+=Number(merged.aldiDirectOfferCount||0);
      if(merged.aldiPricingStatus==='verified')verified++;else if(merged.aldiPricingStatus==='partial')partial++;else unresolved++;
      return merged;
    });
    prepared.aldiDirectLoaded=true;prepared.aldiMergeStats={verifiedStations:verified,partialStations:partial,unresolvedStations:unresolved,directOfferRows:offers};
    window.TCC_ALDI_MERGE_STATS={...prepared.aldiMergeStats};return prepared;
  }
  function installCandidateOverlay(){
    const current=window.candidateStations;if(typeof current!=='function')return false;if(current.__tccAldiDirectV1)return true;
    const wrapped=async function(filterMode='tesla',maxDistanceKm=0){
      const prepared=await current.call(this,filterMode,maxDistanceKm);if(filterMode!=='all')return prepared;return overlayPrepared(prepared);
    };
    wrapped.__tccAldiDirectV1=true;wrapped.__tccOriginal=current;window.candidateStations=wrapped;try{candidateStations=wrapped}catch(e){}return true;
  }
  function boot(){if(!installCandidateOverlay()){let tries=0;const timer=setInterval(()=>{tries++;if(installCandidateOverlay()||tries>=30)clearInterval(timer)},200)}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else queueMicrotask(boot);
  window.TCCAldiDirectV8={revision:REVISION,isAldiPhysical,hasFrAln,isExplicitAldiOperator,physicalGroups,tariffFor,directConfigurations,mergeStation,overlayPrepared,installCandidateOverlay};
  console.info('[TCC V8] ALDI Direct France : FRALN/ALDI physique uniquement, AC <=22 kW et DC 50 kW; DC 60/100 kW fail-closed.');
})();
