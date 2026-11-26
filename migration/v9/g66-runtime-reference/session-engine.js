(function(root,factory){
  if(typeof module==='object'&&module.exports){
    module.exports=factory(require('./offer-engine.js'),require('./pricing-engine.js'));
  }else{
    root.TCCV9SessionEngine=factory(root.TCCV9OfferEngine,root.TCCV9PricingEngine);
  }
})(typeof globalThis!=='undefined'?globalThis:this,function(OfferEngine,PricingEngine){
  'use strict';

  if(!OfferEngine)throw new Error('TCC V9 offer engine is required');
  if(!PricingEngine)throw new Error('TCC V9 pricing engine is required');

  const text=v=>String(v==null?'':v).trim();
  const num=v=>{if(v===null||v===undefined||v==='')return null;const n=Number(v);return Number.isFinite(n)?n:null;};
  const money=v=>Math.round((Number(v)+Number.EPSILON)*1000000)/1000000;
  const addMinutes=(value,minutes)=>{const d=value instanceof Date?new Date(value.getTime()):new Date(value);if(Number.isNaN(d.getTime()))return null;return new Date(d.getTime()+Number(minutes||0)*60000);};

  function connectorKind(connector={}){
    const raw=text(connector.kind||connector.currentType||connector.powerType||connector.plugName).toUpperCase();
    if(raw.includes('DC')||raw.includes('CCS')||raw.includes('CHADEMO'))return'DC';
    if(raw.includes('AC')||raw.includes('TYPE2')||raw.includes('TYPE 2'))return'AC';
    const power=num(connector.powerKw);return power!=null&&power>22?'DC':'AC';
  }

  function connectorUsable(connector={}){
    const state=text(connector?.status?.state??connector?.status).toLowerCase();
    return !['out_of_service','unavailable','offline','faulted','inoperative'].includes(state);
  }
  const evseIdentity=v=>text(v).toUpperCase().replace(/[^A-Z0-9]/g,'');
  function evseIdentities(evse={}){
    return [evse.evseId,evse.pdcId,evse.id,...(Array.isArray(evse.aliases)?evse.aliases:[]),...(Array.isArray(evse.pdcIds)?evse.pdcIds:[])].map(evseIdentity).filter(Boolean);
  }
  function stationChargingProfile(station){
    let selected=null;
    for(const evse of station?.evses||[])for(const connector of evse?.connectors||[]){
      if(!connectorUsable(connector))continue;
      const power=num(connector?.powerKw);if(power==null||power<=0)continue;
      if(!selected||power>selected.powerKw)selected={powerKw:power,kind:connectorKind(connector),connectorId:text(connector?.id)||null,plugName:text(connector?.plugName||connector?.type)||null,evseIds:evseIdentities(evse)};
    }
    return selected||{powerKw:null,kind:null,connectorId:null,plugName:null,evseIds:[]};
  }
  function stationChargingKind(station){return stationChargingProfile(station).kind;}

  function offerMatchesChargingKind(offer,chargingKind,chargingPowerKw=null,chargingPlugName=null,chargingConnectorId=null,chargingEvseIds=[]){
    const scopedEvses=Array.isArray(offer?.evseIds)?offer.evseIds.map(evseIdentity).filter(Boolean):[];
    const candidateEvses=(Array.isArray(chargingEvseIds)?chargingEvseIds:[chargingEvseIds]).map(evseIdentity).filter(Boolean);
    if(scopedEvses.length&&!scopedEvses.some(id=>candidateEvses.includes(id)))return false;
    const allowed=Array.isArray(offer?.connectorKinds)?offer.connectorKinds.map(v=>text(v).toUpperCase()).filter(Boolean):[];
    if(chargingKind&&allowed.length&&!allowed.includes(chargingKind))return false;
    const min=num(offer?.minPowerKw),max=num(offer?.maxPowerKw),power=num(chargingPowerKw);
    if((min!=null||max!=null)&&power==null)return false;
    if(power!=null&&min!=null&&power<min-1e-9)return false;
    if(power!=null&&max!=null&&power>max+1e-9)return false;
    const ids=Array.isArray(offer?.connectorIds)?offer.connectorIds.map(text).filter(Boolean):[];
    if(ids.length&&(!chargingConnectorId||!ids.includes(text(chargingConnectorId))))return false;
    const plugs=Array.isArray(offer?.plugNames)?offer.plugNames.map(v=>text(v).toUpperCase()).filter(Boolean):[];
    if(plugs.length&&(!chargingPlugName||!plugs.includes(text(chargingPlugName).toUpperCase())))return false;
    return true;
  }

  function fxRate(currency,targetCurrency,fxRates={}){
    const from=text(currency||targetCurrency||'EUR').toUpperCase(),to=text(targetCurrency||from).toUpperCase();
    if(from===to)return 1;
    const direct=num(fxRates[`${from}_${to}`]??fxRates[`${from}/${to}`]);if(direct!=null&&direct>0)return direct;
    const inverse=num(fxRates[`${to}_${from}`]??fxRates[`${to}/${from}`]);if(inverse!=null&&inverse>0)return 1/inverse;
    const fromEur=num(fxRates[from]),toEur=num(fxRates[to]);
    if(fromEur!=null&&fromEur>0&&toEur!=null&&toEur>0)return toEur/fromEur;
    return null;
  }

  function recoveredKm(session={}){
    const explicit=num(session.recoveredKm);if(explicit!=null&&explicit>0)return explicit;
    const energy=num(session.energyKwh),consumption=num(session.consumptionKwhPer100Km);
    if(energy==null||energy<=0||consumption==null||consumption<=0)return null;
    return energy/(consumption/100);
  }

  function stationSession(station,session={},options={}){
    const id=text(station?.id||station?.canonicalId||station?.stationId);
    const approach=num(options.approachEnergyKwhByStationId?.[id]??session.approachEnergyKwhByStationId?.[id]??station?.route?.approachEnergyKwh)??0;
    const requested=session.energyKwh==null||session.energyKwh===''?null:num(session.energyKwh);
    const include=session.includeRouteEnergyInCharge!==false;
    return{...session,requestedEnergyKwh:requested,approachEnergyKwh:approach,
      energyKwh:requested==null?null:money(Math.max(0,requested+(include?approach:0)))};
  }

  function validDateKey(value){
    const key=text(value);if(!/^\d{4}-\d{2}-\d{2}$/.test(key))return null;
    const [year,month,day]=key.split('-').map(Number),date=new Date(Date.UTC(year,month-1,day));
    return date.getUTCFullYear()===year&&date.getUTCMonth()+1===month&&date.getUTCDate()===day?key:null;
  }

  function evaluateOfferValidity(offer,session={}){
    const rawFrom=text(offer?.validFrom),rawThrough=text(offer?.validThrough);
    if(!rawFrom&&!rawThrough)return{complete:true};
    const validFrom=rawFrom?validDateKey(rawFrom):null,validThrough=rawThrough?validDateKey(rawThrough):null;
    if((rawFrom&&!validFrom)||(rawThrough&&!validThrough)||(validFrom&&validThrough&&validFrom>validThrough)){
      return{complete:false,reason:'invalid_offer_validity_window',offerId:text(offer?.id||offer?.offerId),validFrom:rawFrom||null,validThrough:rawThrough||null};
    }
    if(!session.startAt)return{complete:false,reason:'offer_validity_requires_start_time',offerId:text(offer?.id||offer?.offerId),validFrom,validThrough};
    const timeZone=PricingEngine.offerTimeZone(offer,session),start=PricingEngine.localDateParts(session.startAt,timeZone);
    if(!start)return{complete:false,reason:'offer_validity_local_date_unresolved',offerId:text(offer?.id||offer?.offerId),timeZone,validFrom,validThrough};
    if((validFrom&&start.key<validFrom)||(validThrough&&start.key>validThrough)){
      return{complete:false,reason:'offer_outside_validity_window',offerId:text(offer?.id||offer?.offerId),timeZone,sessionLocalDate:start.key,validFrom,validThrough};
    }
    const basis=text(offer?.validityBasis||offer?.metadata?.validityBasis)||'session_start_local_date';
    if(basis==='whole_session_local_date'){
      const duration=Math.max(0,num(session.durationMinutes)??0),endAt=addMinutes(session.startAt,duration),end=endAt&&PricingEngine.localDateParts(endAt,timeZone);
      if(!end)return{complete:false,reason:'offer_validity_local_date_unresolved',offerId:text(offer?.id||offer?.offerId),timeZone,validFrom,validThrough};
      if((validFrom&&end.key<validFrom)||(validThrough&&end.key>validThrough)){
        return{complete:false,reason:'offer_session_crosses_validity_window',offerId:text(offer?.id||offer?.offerId),timeZone,sessionLocalDate:start.key,sessionEndLocalDate:end.key,validFrom,validThrough};
      }
    }else if(basis!=='session_start_local_date'){
      return{complete:false,reason:'unsupported_offer_validity_basis',offerId:text(offer?.id||offer?.offerId),validityBasis:basis,validFrom,validThrough};
    }
    return{complete:true,timeZone,sessionLocalDate:start.key,validFrom,validThrough,validityBasis:basis};
  }

  function evaluateSessionStartLockedOffer(offer,session={}){
    const pricing=offer?.pricing||{},timeZone=PricingEngine.offerTimeZone(offer,session);
    if(pricing.type!=='rules'||pricing.priceSelectionBasis!=='session_start_local_time')return null;
    const currencyStatus=PricingEngine.offerCurrencyStatus(offer);
    if(!currencyStatus.complete)return{...currencyStatus,offerId:text(offer?.id||offer?.offerId),timeZone};
    if((pricing.rules||[]).some(rule=>rule.billing==='powerMinute'||(num(rule.afterMinutesRate)??0)>0))return PricingEngine.evaluateOffer(offer,session);
    if(!timeZone)return{complete:false,reason:'missing_tariff_time_zone',offerId:text(offer?.id||offer?.offerId)};
    if(!PricingEngine.localDateParts(session.startAt,timeZone))return{complete:false,reason:'invalid_tariff_time_zone',offerId:text(offer?.id||offer?.offerId),timeZone};
    const rule=PricingEngine.matchingRule(pricing,session.startAt,timeZone);
    if(!rule)return{complete:false,reason:'no_matching_time_rule',offerId:text(offer?.id||offer?.offerId),timeZone};
    const base=PricingEngine.evaluateRule(rule,session);
    if(base.complete===false)return{...base,offerId:text(offer?.id||offer?.offerId),timeZone};
    const finalized=PricingEngine.applyMinimumTotal(pricing,base.totalEur,base.components);
    return{
      complete:true,totalEur:finalized.totalEur,components:finalized.components,
      offerId:text(offer?.id||offer?.offerId),currency:currencyStatus.currency,matchedRule:rule,
      segmented:false,timeZone,priceSelectionBasis:'session_start_local_time'
    };
  }

  function timelineEnergy(pricing,session,timeZone){
    const rows=Array.isArray(session.chargeTimeline)?session.chargeTimeline:[];
    if(!rows.length||!session.startAt)return null;
    let total=0;const segments=[];
    for(const step of rows){
      const offset=Math.max(0,num(step.offsetMinutes)??0),duration=Math.max(0,num(step.durationMinutes)??0),energy=Math.max(0,num(step.energyKwh)??0);
      if(duration<=1e-9||energy<=0)continue;
      let used=0;
      while(used<duration-1e-9){
        const at=addMinutes(session.startAt,offset+used);if(!at)return{complete:false,reason:'invalid_charge_timeline_start'};
        const rule=PricingEngine.matchingRule(pricing,at,timeZone);if(!rule)return{complete:false,reason:'no_matching_time_rule',segmentStartAt:at.toISOString()};
        if(!PricingEngine.segmentableRule(rule))return{complete:false,reason:'tariff_window_crossing_unsupported_components',segmentStartAt:at.toISOString(),matchedRule:rule};
        let boundary=PricingEngine.minutesUntilRuleBoundary(rule,at,timeZone);if(boundary==null)return{complete:false,reason:'unresolved_tariff_boundary'};
        if(!Number.isFinite(boundary))boundary=duration-used;
        const slice=Math.min(duration-used,Math.max(boundary,1e-6)),sliceEnergy=energy*(slice/duration),rate=num(rule.pricePerKwh),cost=rate==null?0:sliceEnergy*rate;
        total+=cost;
        segments.push({startAt:at.toISOString(),durationMinutes:money(slice),energyKwh:money(sliceEnergy),pricePerKwh:rate,costEur:money(cost),startSoc:num(step.startSoc),endSoc:num(step.endSoc),powerKw:num(step.powerKw),rule});
        used+=slice;
        if(segments.length>4096)return{complete:false,reason:'charge_timeline_segmentation_guard'};
      }
    }
    return{complete:true,totalEur:money(total),segments};
  }

  function evaluateTimelineOffer(offer,session={}){
    const pricing=offer?.pricing||{},timeZone=PricingEngine.offerTimeZone(offer,session);
    const currencyStatus=PricingEngine.offerCurrencyStatus(offer);
    if(!currencyStatus.complete)return{...currencyStatus,offerId:text(offer?.id||offer?.offerId),timeZone};
    if(pricing.type!=='rules'||pricing.priceSelectionBasis==='session_start_local_time'||!Array.isArray(session.chargeTimeline)||!session.chargeTimeline.length||!session.startAt)return null;
    if((pricing.rules||[]).some(rule=>rule.billing==='powerMinute'))return PricingEngine.evaluateOffer(offer,session);
    // A sole all-day rule without calendar restrictions cannot change during
    // the charge. The ordinary evaluator still checks every component and
    // threshold on the full session, including billing steps.
    if(pricing.rules?.length===1){
      const only=pricing.rules[0];
      if(only?.scope==='allDay'&&only.daysOfWeek==null&&only.days==null&&
         only.holidayOnly!==true&&only.excludeHolidays!==true&&
         only.validFromDate==null&&only.validThroughDate==null)return null;
    }
    const rule=PricingEngine.matchingRule(pricing,session.startAt,timeZone);if(!rule)return null;
    const duration=Math.max(0,num(session.durationMinutes)??0),boundary=PricingEngine.minutesUntilRuleBoundary(rule,session.startAt,timeZone);
    if(boundary==null||!Number.isFinite(boundary)||duration<=boundary+1e-9)return null;
    const threshold=num(pricing.longConnectionFee?.thresholdMinutes);if(threshold!=null&&duration>threshold)return null;
    const timeBase=PricingEngine.evaluateSegmentedRules(pricing,{...session,energyKwh:0},timeZone);if(timeBase.complete===false)return{...timeBase,offerId:text(offer?.id||offer?.offerId),timeZone};
    const energyBase=timelineEnergy(pricing,session,timeZone);if(!energyBase||energyBase.complete===false)return energyBase?{...energyBase,offerId:text(offer?.id||offer?.offerId),timeZone}:null;
    const conditional=PricingEngine.evaluateConditionalSessionFees(pricing.conditionalSessionFees,session);if(conditional.complete===false)return{complete:false,reason:conditional.reason,offerId:text(offer?.id||offer?.offerId),timeZone};
    const post=PricingEngine.evaluatePostChargeFee(pricing.postChargeFee,session,timeZone);if(post.complete===false)return{complete:false,reason:post.reason,offerId:text(offer?.id||offer?.offerId),timeZone};
    const total=timeBase.totalEur+energyBase.totalEur+conditional.totalEur+post.totalEur;
    const components={...timeBase.components,energyTimeline:{segments:energyBase.segments,costEur:energyBase.totalEur},...(conditional.component?{conditionalSessionFees:conditional.component}:{}),...(post.component?{postCharge:post.component}:{})};
    const finalized=PricingEngine.applyMinimumTotal(pricing,total,components);
    return{complete:true,totalEur:finalized.totalEur,components:finalized.components,offerId:text(offer?.id||offer?.offerId),currency:currencyStatus.currency,matchedRule:rule,segmented:true,energyTimelineApplied:true,timeZone};
  }

  function congestionRules(pricing={}){
    const groups=Array.isArray(pricing.componentGroups)?pricing.componentGroups:[],all=[
      ...(Array.isArray(pricing.rules)?pricing.rules:[]),
      ...groups.flatMap(group=>group.rules||[])
    ];
    return all.filter(rule=>num(rule?.congestionTimePerMinute)!=null&&num(rule.congestionTimePerMinute)>0);
  }

  function evaluateStation(station,session={},options={}){
    const selectedSubscriptions=options.selectedSubscriptions||session.selectedSubscriptions||[];
    const chargingProfile=stationChargingProfile(station),chargingKind=chargingProfile.kind,chargingPowerKw=chargingProfile.powerKw,chargingPlugName=chargingProfile.plugName,chargingConnectorId=chargingProfile.connectorId;
    const connectorProfiles=(station?.evses||[]).flatMap(evse=>(evse.connectors||[]).filter(connectorUsable).map(connector=>({kind:connectorKind(connector),powerKw:num(connector.powerKw),plugName:text(connector.plugName||connector.type)||null,connectorId:text(connector.id)||null,evseIds:evseIdentities(evse)})));
    const offerPairs=OfferEngine.eligibleOffers(station,selectedSubscriptions,{countryCode:station?.countryCode}).map(offer=>{
      const exact=Array.isArray(offer?.evseIds)&&offer.evseIds.length>0||offer?.metadata?.pcprExactConnector===true;
      const profile=exact?connectorProfiles.find(p=>offerMatchesChargingKind(offer,p.kind,p.powerKw,p.plugName,p.connectorId,p.evseIds))
        :offerMatchesChargingKind(offer,chargingKind,chargingPowerKw,chargingPlugName,chargingConnectorId,chargingProfile.evseIds)?chargingProfile:null;
      return{offer,profile,exact};
    }).filter(pair=>pair.profile);
    const targetCurrency=text(options.targetCurrency||session.targetCurrency||'EUR').toUpperCase();
    const fxRates=options.fxRates||session.fxRates||{};
    const effectiveSession=stationSession(station,session,options),km=recoveredKm(session),evaluations=[];
    effectiveSession.stationTimeZone=station?.timeZone||station?.metadata?.timeZone||effectiveSession.stationTimeZone||null;
    if(num(effectiveSession.powerKw)==null&&chargingPowerKw!=null)effectiveSession.powerKw=chargingPowerKw;

    for(const {offer,profile,exact} of offerPairs){
      const connectorSession=exact?options.pcprConnectorSessions?.[profile.connectorId]:null;
      const currentSession={...(connectorSession||effectiveSession),chargingKind:profile.kind};
      if(exact&&profile.powerKw!=null)currentSession.powerKw=Math.min(num(currentSession.powerKw)??profile.powerKw,profile.powerKw);
      const postChargeMinutes=Math.max(0,num(currentSession.postChargeMinutes)??0);
      const unknownPostCharge=offer?.pricing?.postChargeFeeUnknown===true||offer?.metadata?.postChargeFeeUnknown===true;
      const validity=evaluateOfferValidity(offer,currentSession);
      const locked=validity.complete?evaluateSessionStartLockedOffer(offer,currentSession):null;
      const timeline=validity.complete&&!locked?evaluateTimelineOffer(offer,currentSession):null;
      const feeRules=congestionRules(offer?.pricing);
      const result=validity.complete===false
        ?validity
        :unknownPostCharge&&postChargeMinutes>0
        ?{complete:false,reason:'post_charge_fee_unknown_for_station',offerId:text(offer.id||offer.offerId),postChargeMinutes}
        :feeRules.length
        ?PricingEngine.evaluateOffer(offer,{...currentSession,includeCongestionFees:true})
        :(locked||timeline||PricingEngine.evaluateOffer(offer,currentSession));
      const withoutCongestion=feeRules.length&&validity.complete!==false
        ?PricingEngine.evaluateOffer(offer,{...currentSession,includeCongestionFees:false}):null;
      const currency=text(result.currency||offer.currency||'EUR').toUpperCase();
      const rate=result.complete?fxRate(currency,targetCurrency,fxRates):null;
      const pricingWarning=text(offer?.metadata?.incompletePricingReason);
      const comparable=result.complete===true&&!pricingWarning&&rate!=null&&num(result.totalEur)!=null;
      const normalizedTotal=comparable?money(result.totalEur*rate):null;
      const totalWithoutCongestion=withoutCongestion?.complete&&comparable?money(withoutCongestion.totalEur*rate):null;
      const congestionMinutes=feeRules.length?PricingEngine.congestionBillableMinutes(currentSession,num(feeRules[0]?.congestionStartSoc)??80):null;
      evaluations.push({
        offerId:text(offer.id||offer.offerId),provider:text(offer.provider),kind:text(offer.kind),subscriptionId:text(offer.subscriptionId),selectionId:text(offer.selectionId)||null,
        priority:num(offer.priority)??0,currency,result,comparable,targetCurrency,
        connectorId:exact?profile.connectorId:null,evseId:exact?profile.evseIds[0]||null:null,
        connectorPowerKw:exact?profile.powerKw:null,connectorKind:exact?profile.kind:null,
        incompletePricingReason:pricingWarning||null,
        total:normalizedTotal,costPerRecoveredKm:normalizedTotal!=null&&km?money(normalizedTotal/km):null,
        congestion:feeRules.length?{
          available:true,thresholdSoc:num(feeRules[0]?.congestionStartSoc)??80,
          thresholdSource:text(feeRules[0]?.congestionThresholdSource)||'default_soc80',
          minutes:congestionMinutes?.complete?congestionMinutes.minutes:null,
          totalWithoutCongestion,
          feeAmount:normalizedTotal!=null&&totalWithoutCongestion!=null?money(normalizedTotal-totalWithoutCongestion):null,
          sourceCurrencyTotalWithout:withoutCongestion?.complete?withoutCongestion.totalEur:null
        }:null
      });
    }

    const comparable=evaluations.filter(x=>x.comparable).sort((a,b)=>{
      if(a.total!==b.total)return a.total-b.total;
      if(a.priority!==b.priority)return b.priority-a.priority;
      return `${a.provider}|${a.offerId}`.localeCompare(`${b.provider}|${b.offerId}`);
    });
    const best=comparable[0]||null;
    return{
      stationId:text(station?.id||station?.canonicalId||station?.stationId),chargingKind,chargingPowerKw,chargingPlugName,chargingConnectorId,
      eligibleOfferCount:offerPairs.length,comparableOfferCount:comparable.length,targetCurrency,recoveredKm:km,
      requestedEnergyKwh:effectiveSession.requestedEnergyKwh,approachEnergyKwh:effectiveSession.approachEnergyKwh,billedEnergyKwh:effectiveSession.energyKwh,
      best,
      alternatives:comparable.slice(1),
      incomplete:evaluations.filter(x=>!x.comparable)
    };
  }

  function evaluateArea(stations,session={},options={}){
    const rows=(stations||[]).map(station=>({station,evaluation:evaluateStation(station,session,options)}));
    const sortBy=options.sortBy||'total';
    rows.sort((a,b)=>{
      const av=sortBy==='costPerRecoveredKm'?a.evaluation.best?.costPerRecoveredKm:a.evaluation.best?.total;
      const bv=sortBy==='costPerRecoveredKm'?b.evaluation.best?.costPerRecoveredKm:b.evaluation.best?.total;
      if(av==null&&bv==null)return 0;if(av==null)return 1;if(bv==null)return-1;if(av!==bv)return av-bv;
      return a.evaluation.stationId.localeCompare(b.evaluation.stationId);
    });
    return rows;
  }

  return{evaluateStation,evaluateArea,recoveredKm,fxRate,stationSession,evaluateOfferValidity,evaluateSessionStartLockedOffer,evaluateTimelineOffer,timelineEnergy,stationChargingProfile,stationChargingKind,offerMatchesChargingKind,connectorKind,connectorUsable};
});
