// Tesla Charge Companion V8 RC4.8 — overlay tarifs opérateur directs.
(function(){
  'use strict';
  const OVERLAY_URL='data/tariff_overlay_v1.json';
  const TOTALENERGIES_URL='data/totalenergies_tariff_overlay_v1.json';
  const EVADEA_MAP_URL='data/evadea_evse_tariffs_v1.json';
  const REVISION='rc48ak';
  let overlayPromise=null,totalEnergiesPromise=null,evadeaPromise=null,evadeaAddressIndexCache=null;
  const text=v=>String(v==null?'':v).trim();
  const norm=v=>text(v).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();

  async function loadTotalEnergiesOverlay(){
    if(!totalEnergiesPromise)totalEnergiesPromise=fetch(`${TOTALENERGIES_URL}?v=20260825a`,{cache:'no-store'}).then(r=>{
      if(!r.ok)throw new Error(`extension TotalEnergies indisponible (${r.status})`);
      return r.json();
    }).then(data=>{
      if(!data||data.operator!=='TotalEnergies'||String(data.country||'FR').toUpperCase()!=='FR')throw new Error('extension TotalEnergies invalide');
      window.TCC_TOTALENERGIES_TARIFF_OVERLAY_V1=data;
      return data;
    }).catch(err=>{
      console.warn('[TCC V8] Extension TotalEnergies non chargée:',err);
      return null;
    });
    return totalEnergiesPromise;
  }

  function mergeOperatorExtension(base,extension){
    if(!extension)return base||{};
    const merged={...(base||{})};
    const baseOffers=Array.isArray(merged.operatorOffers)?merged.operatorOffers:[];
    const baseSubs=Array.isArray(merged.subscriptions)?merged.subscriptions:[];
    const extOffers=Array.isArray(extension.operatorOffers)?extension.operatorOffers:[];
    const extSubs=Array.isArray(extension.subscriptions)?extension.subscriptions:[];
    const extOfferIds=new Set(extOffers.map(x=>text(x?.id)).filter(Boolean));
    const extSubIds=new Set(extSubs.map(x=>text(x?.id)).filter(Boolean));
    merged.operatorOffers=[...baseOffers.filter(x=>!extOfferIds.has(text(x?.id))),...extOffers];
    merged.subscriptions=[...baseSubs.filter(x=>!extSubIds.has(text(x?.id))),...extSubs];
    const resolved=new Set((extension.resolvedDeferredOperators||[]).map(norm).filter(Boolean));
    if(resolved.size&&Array.isArray(merged.deferredValidated)){
      merged.deferredValidated=merged.deferredValidated.filter(x=>!resolved.has(norm(x?.operator)));
    }
    return merged;
  }

  async function loadOverlay(){
    if(!overlayPromise)overlayPromise=Promise.all([
      fetch(`${OVERLAY_URL}?v=20260825a`,{cache:'no-store'}).then(r=>{
        if(!r.ok)throw new Error(`overlay tarifs indisponible (${r.status})`);
        return r.json();
      }),
      loadTotalEnergiesOverlay()
    ]).then(([data,totalEnergies])=>{
      const merged=mergeOperatorExtension(data,totalEnergies);
      window.TCC_TARIFF_OVERLAY_V1=merged;
      return merged;
    }).catch(err=>{
      console.warn('[TCC V8] Overlay tarifs opérateur non chargé:',err);
      return {operatorOffers:[],subscriptions:[],mappedOperatorOffers:[]};
    });
    return overlayPromise;
  }

  async function loadEvadeaMap(){
    if(!evadeaPromise)evadeaPromise=fetch(`${EVADEA_MAP_URL}?v=20260821b`,{cache:'no-store'}).then(r=>{
      if(!r.ok)throw new Error(`carte e-Vadea indisponible (${r.status})`);
      return r.json();
    }).then(data=>{
      if(!data||data.operator!=='e-Vadea'||!data.evses||typeof data.evses!=='object')throw new Error('carte e-Vadea invalide');
      window.TCC_EVADEA_TARIFF_MAP_V1=data;
      evadeaAddressIndexCache=null;
      return data;
    }).catch(err=>{
      console.warn('[TCC V8] Carte tarifaire e-Vadea non chargée:',err);
      return {operator:'e-Vadea',evses:{}};
    });
    return evadeaPromise;
  }

  function operatorCandidates(st){
    return [st?.operator,st?._sourceOperator,st?.cpo,st?.network,st?.name].map(norm).filter(Boolean);
  }
  function directOperatorCandidates(st){
    return [st?.operator,st?._sourceOperator,st?.cpo].map(norm).filter(Boolean);
  }
  function isSigeifOperator(st){
    return operatorCandidates(st).some(v=>v==='sigeif'||v.includes('sigeif')||v.includes('syndicat intercommunal pour le gaz et l electricite en idf'));
  }
  function isPlenitudeOperator(st){
    return operatorCandidates(st).some(v=>v==='be charge'||v.includes('plenitude')||v.includes('plentitude'));
  }
  function isEvadeaOperator(st){
    return operatorCandidates(st).some(v=>v==='e vadea'||v==='evadea'||v.includes('e vadea'));
  }
  function operatorMatches(st,offer){
    const values=offer?.directOperatorOnly?directOperatorCandidates(st):operatorCandidates(st),id=String(offer?.id||'');
    if(id.startsWith('sigeif-')&&isSigeifOperator(st))return true;
    if(id.startsWith('plenitude-')&&isPlenitudeOperator(st))return true;
    return (offer?.operatorAliases||[]).some(alias=>values.includes(norm(alias)));
  }
  function powerMatches(kind,power,offer){
    if(offer?.kind&&text(kind).toUpperCase()!==text(offer.kind).toUpperCase())return false;
    const p=Number(power||0),min=Number(offer?.minPowerKw),max=Number(offer?.maxPowerKw);
    if(Number.isFinite(min)&&p<min-1e-9)return false;
    if(Number.isFinite(max)&&p>max+1e-9)return false;
    return true;
  }
  function providerOfConfig(c){
    const label=text(c?.label||c?.configurationLabel);
    const i=label.indexOf('·');
    return (i>=0?label.slice(0,i):label).trim();
  }
  function providerLabel(offer){return String(offer?.id||'').startsWith('sigeif-')?'SIGEIF / IZIVIA direct':offer?.provider;}

  function physicalConfigs(st){
    const configs=Array.isArray(st?.chargingConfigurations)&&st.chargingConfigurations.length?st.chargingConfigurations:[{id:'main',label:`${st?.kind||'AC'} ${Number(st?.powerKw||0)} kW`,kind:st?.kind||'AC',powerKw:Number(st?.powerKw||0),stalls:Number(st?.stalls||0),pricing:st?.pricing}];
    const seen=new Set(),out=[];
    for(const c of configs){
      const kind=text(c?.kind||st?.kind||'AC').toUpperCase(),power=Number(c?.powerKw??st?.powerKw??0);
      if(!(power>0))continue;
      const key=`${kind}|${power.toFixed(2)}`;
      if(seen.has(key))continue;
      seen.add(key);out.push({kind,powerKw:power,stalls:Number(c?.stalls||st?.stalls||0)});
    }
    return out;
  }
  function hasProvider(configs,provider,kind,power){
    const p=norm(provider);
    return (configs||[]).some(c=>norm(providerOfConfig(c))===p&&text(c?.kind).toUpperCase()===kind&&Math.abs(Number(c?.powerKw||0)-power)<.25);
  }

  function canonicalEvadeaId(value){
    const compact=String(value==null?'':value).toUpperCase().replace(/[^A-Z0-9]/g,'');
    return /^FREVAE[A-Z0-9]+$/.test(compact)?compact:'';
  }
  function collectEvadeaIds(st){
    const ids=new Set(),seen=new Set();
    function scan(value,depth=0,key=''){
      if(value==null||depth>4)return;
      if(typeof value==='string'||typeof value==='number'){
        const raw=String(value).toUpperCase();
        const exact=canonicalEvadeaId(raw);if(exact)ids.add(exact);
        for(const m of raw.match(/FREVAE[A-Z0-9]+/g)||[])ids.add(m);
        return;
      }
      if(typeof value!=='object'||seen.has(value))return;
      seen.add(value);
      if(Array.isArray(value)){
        value.slice(0,250).forEach(v=>scan(v,depth+1,key));return;
      }
      for(const [k,v] of Object.entries(value)){
        const nk=norm(k);
        if(depth<=1||/(?:evse|pdc|station|source|external|identifier|^id$|ids)/.test(nk))scan(v,depth+1,k);
      }
    }
    scan(st,0,'station');
    return [...ids];
  }

  function evadeaAddressIndex(map){
    if(evadeaAddressIndexCache?.map===map)return evadeaAddressIndexCache.index;
    const index=new Map();
    for(const [evseId,rec] of Object.entries(map?.evses||{})){
      const address=norm(rec?.address);if(!address)continue;
      if(!index.has(address))index.set(address,[]);
      index.get(address).push({...rec,evseId});
    }
    evadeaAddressIndexCache={map,index};
    return index;
  }
  function geoDistanceKm(aLat,aLon,bLat,bLon){
    const r=6371,toRad=x=>Number(x)*Math.PI/180;
    const p1=toRad(aLat),p2=toRad(bLat),dp=toRad(Number(bLat)-Number(aLat)),dl=toRad(Number(bLon)-Number(aLon));
    const h=Math.sin(dp/2)**2+Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2;
    return 2*r*Math.atan2(Math.sqrt(h),Math.sqrt(Math.max(0,1-h)));
  }
  function configCompatible(rec,cfg){
    if(Math.abs(Number(rec?.powerKw||0)-Number(cfg?.powerKw||0))>=.25)return false;
    const hint=text(rec?.kindHint).toUpperCase();
    return !hint||hint===text(cfg?.kind).toUpperCase();
  }
  function consistentEvadea(records,matchMode,matchedEvseIds=[],matchDistanceMeters=null){
    if(!records.length)return null;
    const signatures=new Set(records.map(r=>[
      r.context,Number(r.pricePerKwhEur).toFixed(6),Number(r?.occupancy?.blockFeeEur).toFixed(6),Number(r?.occupancy?.graceMinutes),Number(r?.occupancy?.startedBlockMinutes)
    ].join('|')));
    if(signatures.size!==1)return null;
    return {...records[0],matchMode,matchedEvseIds,matchDistanceMeters};
  }
  function resolveEvadea(st,cfg,map){
    const evses=map?.evses||{};
    const ids=collectEvadeaIds(st);
    const exact=ids.map(id=>evses[id]?{...evses[id],evseId:id}:null).filter(Boolean).filter(r=>configCompatible(r,cfg));
    const exactResolved=consistentEvadea(exact,'evse',ids.filter(id=>!!evses[id]));
    if(exactResolved)return exactResolved;

    if(!isEvadeaOperator(st))return null;
    const address=norm(st?.address||st?._sourceAddress||'');
    if(address.length>=8){
      const fallback=(evadeaAddressIndex(map).get(address)||[]).filter(r=>configCompatible(r,cfg));
      const addressResolved=consistentEvadea(fallback,'address_power',[]);
      if(addressResolved)return addressResolved;
    }

    const lat=Number(st?.latitude),lon=Number(st?.longitude);
    if(!Number.isFinite(lat)||!Number.isFinite(lon))return null;
    const maxMeters=Math.max(10,Number(map?.validatedInventory?.geoPowerFallbackMaxDistanceMeters||150));
    const geo=[];
    let nearest=Infinity;
    for(const [evseId,rec] of Object.entries(evses)){
      if(!configCompatible(rec,cfg))continue;
      const rlat=Number(rec?.latitude),rlon=Number(rec?.longitude);
      if(!Number.isFinite(rlat)||!Number.isFinite(rlon))continue;
      const meters=geoDistanceKm(lat,lon,rlat,rlon)*1000;
      if(meters<=maxMeters+1e-6){geo.push({...rec,evseId});nearest=Math.min(nearest,meters);}
    }
    if(!geo.length)return null;
    const stationIds=new Set(geo.map(r=>text(r.stationId)).filter(Boolean));
    if(stationIds.size!==1)return null;
    return consistentEvadea(geo,'geo_power',[],Number.isFinite(nearest)?Math.round(nearest):null);
  }
  function evadeaPricing(rec){
    return {type:'rules',rules:[{
      scope:'allDay',start:'00:00',end:'24:00',billing:'kwh',currency:'EUR',
      pricePerKwh:Number(rec.pricePerKwhEur),chargePerMinute:0,connectionFee:0,idlePerMinute:0,
      afterMinutesRate:0,afterMinutesThreshold:0,afterMinutesCap:0,afterMinutesCapStart:'00:00',afterMinutesCapEnd:'24:00',
      startedKwhCharged:true,
      postChargeGraceMinutes:Number(rec?.occupancy?.graceMinutes||5),
      postChargeBlockMinutes:Number(rec?.occupancy?.startedBlockMinutes||15),
      postChargeBlockFee:Number(rec?.occupancy?.blockFeeEur||0)
    }]};
  }
  function addEvadeaOffers(st,map,base,physical,added){
    if(!map?.evses||!Object.keys(map.evses).length)return;
    for(const cfg of physical){
      const rec=resolveEvadea(st,cfg,map);if(!rec)continue;
      const provider='e-Vadea direct';
      if(hasProvider([...base,...added],provider,cfg.kind,cfg.powerKw))continue;
      added.push({
        id:`tariff-overlay:evadea-direct-evse:${cfg.kind}:${cfg.powerKw}`,
        label:`${provider} · ${cfg.kind} ${cfg.powerKw} kW`,
        kind:cfg.kind,powerKw:cfg.powerKw,stalls:cfg.stalls,
        pricing:evadeaPricing(rec),offerProvider:provider,offerType:'operator_direct',
        overlayOfferId:'evadea-direct-evse',overlaySource:'data-lab/evadea_official_france.json',
        evadeaMatchMode:rec.matchMode,evadeaMatchDistanceMeters:rec.matchDistanceMeters,
        evadeaContext:rec.context,evadeaMatchedEvseIds:rec.matchedEvseIds||[],
        evadeaStationId:rec.stationId||'',evadeaReferenceAddress:rec.address||''
      });
    }
  }

  function addOperatorOffers(st,overlay,evadeaMap=window.TCC_EVADEA_TARIFF_MAP_V1){
    if(!st||String(st.countryCode||'FR').toUpperCase()!=='FR')return st;
    const base=Array.isArray(st.chargingConfigurations)?st.chargingConfigurations.map(c=>({...c})):[];
    const physical=physicalConfigs(st),added=[];
    addEvadeaOffers(st,evadeaMap,base,physical,added);
    for(const offer of overlay?.operatorOffers||[]){
      if(!operatorMatches(st,offer))continue;
      const provider=providerLabel(offer);
      for(const cfg of physical){
        if(!powerMatches(cfg.kind,cfg.powerKw,offer))continue;
        if(hasProvider([...base,...added],provider,cfg.kind,cfg.powerKw))continue;
        added.push({
          id:`tariff-overlay:${offer.id}:${cfg.kind}:${cfg.powerKw}`,
          label:`${provider} · ${cfg.kind} ${cfg.powerKw} kW`,
          kind:cfg.kind,
          powerKw:cfg.powerKw,
          stalls:cfg.stalls,
          pricing:JSON.parse(JSON.stringify(offer.pricing||{type:'rules',rules:[]})),
          offerProvider:provider,
          offerType:offer.offerType||'operator_direct',
          overlayOfferId:offer.id,
          overlaySource:offer.source||''
        });
      }
    }
    if(!added.length)return st;
    return {...st,chargingConfigurations:[...base,...added],_tariffOverlayOffers:[...(st._tariffOverlayOffers||[]),...added.map(x=>x.overlayOfferId)]};
  }

  async function applyToPrepared(result){
    if(!result||!Array.isArray(result.stations))return result;
    const [overlay,evadeaMap]=await Promise.all([loadOverlay(),loadEvadeaMap()]);
    result.stations=result.stations.map(st=>addOperatorOffers(st,overlay,evadeaMap));
    result.tariffOverlayApplied=true;
    result.tariffOverlayAppliedAt=Date.now();
    result.evadeaTariffMapApplied=!!Object.keys(evadeaMap?.evses||{}).length;
    return result;
  }

  // Extension du moteur de règles :
  // - frais après FIN de charge avec franchise (Plenitude),
  // - frais e-Vadea par bloc de 15 min commencé après 5 min sans énergie,
  // - kWh commencé facturé lorsque la grille le demande.
  function installPostChargePricing(){
    const current=window.priceWithRules;
    if(typeof current!=='function')return false;
    if(current.__tccPostChargeGraceV2)return true;
    const base=(current.__tccPostChargeGrace&&typeof current.__tccOriginal==='function')?current.__tccOriginal:current;
    const wrapped=function(pp,startMin,chargeMinutes,billedEnergy,unplugTime,startTime,powerSegments=[]){
      const out=base.apply(this,arguments);
      const rules=Array.isArray(pp?.rules)?pp.rules:[];
      if(!out||out.error||!rules.length)return out;

      const started=rules.filter(r=>r?.startedKwhCharged&&String(r?.billing||'').toLowerCase()==='kwh');
      if(started.length){
        const signatures=[...new Set(started.map(r=>`${Number(r?.pricePerKwh||0).toFixed(8)}|${r?.currency||'EUR'}`))];
        if(signatures.length===1){
          const energy=Math.max(0,Number(billedEnergy||0));
          const rounded=Math.ceil(Math.max(0,energy-1e-9));
          if(rounded>energy+1e-9){
            const r=started[0],raw=(rounded-energy)*Math.max(0,Number(r.pricePerKwh||0));
            const converted=typeof window.fxToEur==='function'?window.fxToEur(raw,r.currency||'EUR'):(typeof fxToEur==='function'?fxToEur(raw,r.currency||'EUR'):raw);
            const delta=Number(converted||0);
            out.total=Number(out.total||0)+delta;
            out.chargeCost=Number(out.chargeCost||0)+delta;
            out.startedKwhRoundingCost=Number(out.startedKwhRoundingCost||0)+delta;
            out.billedEnergyRoundedKwh=rounded;
          }
        }
      }

      const hasPost=rules.some(r=>Number(r?.postChargeRate||0)>0||Number(r?.postChargeBlockFee||0)>0);
      if(!hasPost)return out;
      const occupied=Number(out.occupiedMinutes),charge=Math.max(0,Number(chargeMinutes||0));
      if(!(occupied>charge))return out;
      const graceValues=rules.map(r=>Number(r?.postChargeGraceMinutes)).filter(Number.isFinite);
      const grace=graceValues.length?Math.max(0,Math.max(...graceValues)):0;
      const exposureStart=charge+grace,exposureEnd=occupied;
      if(!(exposureEnd>exposureStart))return out;

      let extra=0,blockCount=0;
      const localAtExposure=((Number(startMin||0)+exposureStart)%1440+1440)%1440;
      const exposureRule=typeof window.ruleForMinute==='function'?window.ruleForMinute(rules,localAtExposure):(typeof ruleForMinute==='function'?ruleForMinute(rules,localAtExposure):null);
      const blockFee=Math.max(0,Number(exposureRule?.postChargeBlockFee||0));
      const blockMinutes=Math.max(0,Number(exposureRule?.postChargeBlockMinutes||0));
      if(blockFee>0&&blockMinutes>0){
        const exposure=Math.max(0,exposureEnd-exposureStart);
        blockCount=Math.ceil(Math.max(0,exposure-1e-9)/blockMinutes);
        const raw=blockCount*blockFee,currency=exposureRule?.currency||'EUR';
        extra=typeof window.fxToEur==='function'?window.fxToEur(raw,currency):(typeof fxToEur==='function'?fxToEur(raw,currency):raw);
      }else{
        for(let i=Math.floor(exposureStart);i<Math.ceil(exposureEnd);i++){
          const a=Math.max(exposureStart,i),b=Math.min(exposureEnd,i+1),fraction=Math.max(0,b-a);
          if(!(fraction>0))continue;
          const localMinute=((Number(startMin||0)+a)%1440+1440)%1440;
          const rule=typeof window.ruleForMinute==='function'?window.ruleForMinute(rules,localMinute):(typeof ruleForMinute==='function'?ruleForMinute(rules,localMinute):null);
          if(!rule)continue;
          const rate=Math.max(0,Number(rule.postChargeRate||0));
          if(!(rate>0))continue;
          const currency=rule.currency||'EUR',raw=rate*fraction;
          const converted=typeof window.fxToEur==='function'?window.fxToEur(raw,currency):(typeof fxToEur==='function'?fxToEur(raw,currency):raw);
          extra+=Number(converted||0);
        }
      }
      if(extra>0){
        out.total=Number(out.total||0)+Number(extra||0);
        out.idleCost=Number(out.idleCost||0)+Number(extra||0);
        out.postChargeCost=Number(out.postChargeCost||0)+Number(extra||0);
        if(blockCount>0)out.postChargeBlocks=Number(out.postChargeBlocks||0)+blockCount;
      }
      return out;
    };
    wrapped.__tccPostChargeGrace=true;
    wrapped.__tccPostChargeGraceV2=true;
    wrapped.__tccOriginal=base;
    window.priceWithRules=wrapped;
    try{priceWithRules=wrapped}catch(e){}
    console.info('[TCC V8] Frais post-charge + blocs e-Vadea + kWh commencé actifs.');
    return true;
  }

  function pruneEvadeaReferenceRows(){
    document.querySelectorAll('.v8-reference-row[data-reference-offer-id="evadea-grid"]').forEach(row=>{
      const box=row.closest('.v8-offer-box');if(!box)return;
      const exact=[...box.querySelectorAll('.v8-offer-row:not(.v8-reference-row)')].some(r=>{
        const provider=r.dataset?.tccProvider||r.querySelector('.v8-offer-provider')?.textContent||'';
        return norm(provider).includes('e vadea direct');
      });
      if(exact)row.remove();
    });
  }
  function installEvadeaReferenceGuard(){
    const root=document.getElementById('results');
    if(!root)return false;
    if(root.__tccEvadeaReferenceGuard){pruneEvadeaReferenceRows();return true;}
    let timer=null;const obs=new MutationObserver(()=>{clearTimeout(timer);timer=setTimeout(pruneEvadeaReferenceRows,120)});
    obs.observe(root,{childList:true,subtree:true});root.__tccEvadeaReferenceGuard=obs;
    setTimeout(pruneEvadeaReferenceRows,200);return true;
  }

  function install(){
    installPostChargePricing();installEvadeaReferenceGuard();
    const current=window.candidateStations;
    if(typeof current!=='function')return false;
    if(current.__tccOperatorOverlay)return true;
    const wrapped=async function(...args){
      const result=await current.apply(this,args);
      return applyToPrepared(result);
    };
    wrapped.__tccOperatorOverlay=true;wrapped.__tccOriginal=current;
    window.candidateStations=wrapped;
    try{candidateStations=wrapped}catch(e){}
    console.info('[TCC V8] Overlay opérateur direct V1 + TotalEnergies + e-Vadea EVSE/geo actif.');
    return true;
  }

  function markRevision(){
    const banner=document.getElementById('tccPreviewBanner');
    if(banner&&/RC4\.8/.test(text(banner.textContent))){banner.textContent=`V8 Preview · RC4.8 · ${REVISION} · multi-tarifs · auto-mise à jour désactivée`;}
  }

  loadOverlay();loadEvadeaMap();
  let tries=0;const timer=setInterval(()=>{tries++;const a=install(),b=installPostChargePricing(),c=installEvadeaReferenceGuard();if((a&&b&&c)||tries>160)clearInterval(timer);},100);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(markRevision,0),{once:true});else setTimeout(markRevision,0);
  window.TCCV8OperatorOverlay={loadOverlay,loadTotalEnergiesOverlay,loadEvadeaMap,mergeOperatorExtension,addOperatorOffers,applyToPrepared,isSigeifOperator,isPlenitudeOperator,isEvadeaOperator,resolveEvadea,installPostChargePricing,pruneEvadeaReferenceRows,revision:REVISION};
})();
