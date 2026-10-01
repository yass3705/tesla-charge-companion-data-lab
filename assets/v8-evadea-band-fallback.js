// Tesla Charge Companion V8 RC4.8 — fallback e-Vadea par bande tarifaire validée.
// Utilisé uniquement lorsqu'une puissance du catalogue eMSP ne correspond pas exactement
// à la puissance IRVE publique, mais que la station, le contexte routier, le type AC/DC
// et la bande tarifaire sont tous résolus sans ambiguïté.
(function(){
  'use strict';
  const VERSION='rc48al-evadea-band-1';
  const text=v=>String(v==null?'':v).trim();
  const norm=v=>text(v).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();

  function distanceMeters(aLat,aLon,bLat,bLon){
    const r=6371000,toRad=x=>Number(x)*Math.PI/180;
    const p1=toRad(aLat),p2=toRad(bLat),dp=toRad(Number(bLat)-Number(aLat)),dl=toRad(Number(bLon)-Number(aLon));
    const h=Math.sin(dp/2)**2+Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2;
    return 2*r*Math.atan2(Math.sqrt(h),Math.sqrt(Math.max(0,1-h)));
  }
  function bandKey(context,power){
    const p=Number(power||0);
    if(context==='motorway')return p<100?'motorway-lt100':'motorway-gte100';
    if(context==='off_motorway')return p<30?'off-lt30':p<60?'off-30-60':'off-gte60';
    return '';
  }
  function tariffFor(map,context,power){
    const p=Number(power||0),grid=map?.tariffGrid||{},occ=grid?.occupancy||{};
    if(context==='motorway')return {
      pricePerKwhEur:Number(p<100?grid?.motorway?.lt100Kw:grid?.motorway?.gte100Kw),
      blockFeeEur:Number(occ?.motorwayBlockFeeEur),graceMinutes:Number(occ?.graceMinutes||5),startedBlockMinutes:Number(occ?.startedBlockMinutes||15)
    };
    if(context==='off_motorway')return {
      pricePerKwhEur:Number(p<30?grid?.offMotorway?.lt30Kw:p<60?grid?.offMotorway?.gte30Lt60Kw:grid?.offMotorway?.gte60Kw),
      blockFeeEur:Number(p<30?occ?.offMotorwayLt30KwBlockFeeEur:occ?.offMotorwayGte30KwBlockFeeEur),graceMinutes:Number(occ?.graceMinutes||5),startedBlockMinutes:Number(occ?.startedBlockMinutes||15)
    };
    return null;
  }
  function providerOf(c){
    if(c?.offerProvider)return text(c.offerProvider);
    const label=text(c?.label||c?.configurationLabel),i=label.indexOf('·');
    return (i>=0?label.slice(0,i):label).trim();
  }
  function physicalConfigs(st){
    const src=Array.isArray(st?.chargingConfigurations)&&st.chargingConfigurations.length?st.chargingConfigurations:[{kind:st?.kind,powerKw:st?.powerKw,stalls:st?.stalls}];
    const seen=new Set(),out=[];
    for(const c of src){
      if(norm(providerOf(c))==='e vadea direct')continue;
      const kind=text(c?.kind||st?.kind||'').toUpperCase(),power=Number(c?.powerKw??st?.powerKw??0);
      if(!['AC','DC'].includes(kind)||!(power>0))continue;
      const key=`${kind}|${power.toFixed(2)}`;if(seen.has(key))continue;
      seen.add(key);out.push({kind,powerKw:power,stalls:Number(c?.stalls||st?.stalls||0)});
    }
    return out;
  }
  function hasDirect(configs,cfg){
    return (configs||[]).some(c=>norm(providerOf(c))==='e vadea direct'&&text(c?.kind).toUpperCase()===cfg.kind&&Math.abs(Number(c?.powerKw||0)-cfg.powerKw)<.25);
  }
  function resolveBand(st,cfg,map,api){
    if(!api?.isEvadeaOperator?.(st)||!map?.evses)return null;
    const lat=Number(st?.latitude),lon=Number(st?.longitude);if(!Number.isFinite(lat)||!Number.isFinite(lon))return null;
    const maxMeters=Math.max(10,Number(map?.validatedInventory?.geoPowerFallbackMaxDistanceMeters||150));
    const nearby=[];
    for(const [evseId,rec] of Object.entries(map.evses)){
      const rlat=Number(rec?.latitude),rlon=Number(rec?.longitude);if(!Number.isFinite(rlat)||!Number.isFinite(rlon))continue;
      const meters=distanceMeters(lat,lon,rlat,rlon);if(meters<=maxMeters+1e-6)nearby.push({...rec,evseId,meters});
    }
    if(!nearby.length)return null;
    const stationIds=new Set(nearby.map(r=>text(r.stationId)).filter(Boolean));if(stationIds.size!==1)return null;
    const contexts=new Set(nearby.map(r=>text(r.context)).filter(Boolean));if(contexts.size!==1)return null;
    const context=[...contexts][0],wantedBand=bandKey(context,cfg.powerKw);if(!wantedBand)return null;
    const represented=nearby.filter(r=>{
      const hint=text(r?.kindHint).toUpperCase();
      return (!hint||hint===cfg.kind)&&bandKey(context,Number(r?.powerKw||0))===wantedBand;
    });
    if(!represented.length)return null;
    const tariff=tariffFor(map,context,cfg.powerKw);
    if(!tariff||!Number.isFinite(tariff.pricePerKwhEur)||!Number.isFinite(tariff.blockFeeEur))return null;
    return {
      context,stationId:[...stationIds][0],matchMode:'geo_tariff_band',
      matchDistanceMeters:Math.round(Math.min(...represented.map(r=>r.meters))),
      matchedEvseIds:represented.map(r=>r.evseId),referenceAddress:represented[0]?.address||'',...tariff
    };
  }
  function pricing(rec){return {type:'rules',rules:[{
    scope:'allDay',start:'00:00',end:'24:00',billing:'kwh',currency:'EUR',pricePerKwh:Number(rec.pricePerKwhEur),
    chargePerMinute:0,connectionFee:0,idlePerMinute:0,afterMinutesRate:0,afterMinutesThreshold:0,afterMinutesCap:0,afterMinutesCapStart:'00:00',afterMinutesCapEnd:'24:00',
    startedKwhCharged:true,postChargeGraceMinutes:Number(rec.graceMinutes||5),postChargeBlockMinutes:Number(rec.startedBlockMinutes||15),postChargeBlockFee:Number(rec.blockFeeEur||0)
  }]};}
  function addBandOffers(st,map,api){
    if(!st||String(st.countryCode||'FR').toUpperCase()!=='FR'||!api?.isEvadeaOperator?.(st))return st;
    const base=Array.isArray(st.chargingConfigurations)?st.chargingConfigurations.map(c=>({...c})):[],added=[];
    for(const cfg of physicalConfigs(st)){
      if(hasDirect([...base,...added],cfg))continue;
      const rec=resolveBand(st,cfg,map,api);if(!rec)continue;
      added.push({
        id:`tariff-overlay:evadea-direct-band:${cfg.kind}:${cfg.powerKw}`,label:`e-Vadea direct · ${cfg.kind} ${cfg.powerKw} kW`,
        kind:cfg.kind,powerKw:cfg.powerKw,stalls:cfg.stalls,pricing:pricing(rec),offerProvider:'e-Vadea direct',offerType:'operator_direct',
        overlayOfferId:'evadea-direct-evse',overlaySource:'data-lab/evadea_official_france.json',evadeaMatchMode:rec.matchMode,
        evadeaMatchDistanceMeters:rec.matchDistanceMeters,evadeaContext:rec.context,evadeaMatchedEvseIds:rec.matchedEvseIds,
        evadeaStationId:rec.stationId,evadeaReferenceAddress:rec.referenceAddress
      });
    }
    if(!added.length)return st;
    return {...st,chargingConfigurations:[...base,...added],_tariffOverlayOffers:[...(st._tariffOverlayOffers||[]),...added.map(x=>x.overlayOfferId)]};
  }
  function install(){
    const api=window.TCCV8OperatorOverlay;if(!api||api.__evadeaBandFallback)return false;
    const originalAdd=api.addOperatorOffers.bind(api),originalApply=api.applyToPrepared.bind(api);
    api.addOperatorOffers=function(st,overlay,map=window.TCC_EVADEA_TARIFF_MAP_V1){return addBandOffers(originalAdd(st,overlay,map),map,api);};
    api.applyToPrepared=async function(result){
      const out=await originalApply(result);const map=window.TCC_EVADEA_TARIFF_MAP_V1;
      if(out&&Array.isArray(out.stations)&&map?.evses)out.stations=out.stations.map(st=>addBandOffers(st,map,api));
      return out;
    };
    api.__evadeaBandFallback=true;api.evadeaBandFallbackVersion=VERSION;
    return true;
  }
  let tries=0;const timer=setInterval(()=>{tries++;if(install()||tries>160)clearInterval(timer);},50);
  window.TCCV8EvadeaBandFallback={version:VERSION,install,resolveBand};
})();
