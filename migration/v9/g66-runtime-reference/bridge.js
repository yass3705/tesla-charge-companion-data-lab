(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root){
    root.TCCV9ProductionShell=api;
    if(root.document){
      const start=()=>{
        if(root.__TCC_V9_SHELL__?.pending||root.__TCC_V9_SHELL__?.ready)return;
        api.install(root).catch(err=>{
          const marker=root.__TCC_V9_SHELL__||{};
          marker.pending=false;marker.ready=false;marker.error=String(err?.message||err);
          root.__TCC_V9_SHELL__=marker;
          console.error('[TCC V9 shell] install failed',err);
        });
      };
      if(root.document.readyState==='loading')root.document.addEventListener('DOMContentLoaded',start,{once:true});
      else root.setTimeout(start,0);
    }
  }
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const text=v=>String(v==null?'':v).trim();
  const num=v=>{if(v==null||String(v).trim()==='')return null;const n=Number(v);return Number.isFinite(n)?n:null;};
  const pricedItem=item=>Boolean(item&&item.comparable!==false&&item.result?.complete===true&&num(item.total)!=null);
  const pricedBest=evaluation=>pricedItem(evaluation?.best)?evaluation.best:null;
  const floorPower=v=>{const n=num(v);return n==null?null:Math.round(n*100)/100;};
  const unverifiedFranceDcPower=(station,kind,power)=>text(station?.countryCode).toUpperCase()==='FR'&&text(kind).toUpperCase()==='DC'&&num(power)>1000;
  function guardUnverifiedPowerOffers(station,kind,power,offers){
    if(!unverifiedFranceDcPower(station,kind,power))return offers;
    return(offers||[]).map(offer=>({...offer,metadata:{...offer.metadata,incompletePricingReason:'irve_dc_nominal_power_unverified'}}));
  }
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function stationDisplayName(station){
    const name=text(station?.name),address=text(station?.address),operator=text(station?.physicalOperator?.name);
    const technical=/^[A-Z0-9_-]{8,}$/.test(name)&&/[A-Z]/.test(name)&&/\d/.test(name);
    if(!technical||!address||!operator)return name||'Borne';
    const street=address.split(',')[0].trim();
    return street&&street.toLowerCase()!==operator.toLowerCase()?operator+' · '+street:name;
  }
  const V7_DC_POINTS=[[0,175],[10,175],[20,170],[30,160],[40,145],[50,125],[60,105],[70,85],[80,60],[85,42],[90,28],[95,16],[98,10],[100,6]];
  const SUBSCRIPTION_KEY='tccV9SelectedSubscriptionsV1';
  const congestionSelections=new Map(); // toggled independently per EVSE and offer
  // France prices and Electra-only discounts: https://www.go-electra.com/fr/electra-plus/
  const ELECTRA_PLUS_PLANS=[
    {id:'electra-plus-essential',label:'Electra+ Essentiel',provider:'Electra',monthlyFeeEur:1.99,discountPerKwhEur:0.10},
    {id:'electra-plus-smart',label:'Electra+ Smart',provider:'Electra',monthlyFeeEur:4.99,discountPerKwhEur:0.20}
  ];

  function selectedSubscriptions(w){
    try{const raw=JSON.parse(w.localStorage.getItem(SUBSCRIPTION_KEY)||'[]');return Array.isArray(raw)?[...new Set(raw.map(text).filter(Boolean))]:[];}catch(_){return[];}
  }
  function selectedSubscriptionsForConfig(w,cfg){
    const selected=selectedSubscriptions(w);
    return cfg?.preproductionCandidateBase?selected.filter(id=>!ELECTRA_PLUS_PLANS.some(plan=>plan.id===id)):selected;
  }
  function saveSelectedSubscriptions(w,ids){const clean=[...new Set((ids||[]).map(text).filter(Boolean))];try{w.localStorage.setItem(SUBSCRIPTION_KEY,JSON.stringify(clean));}catch(_){}return clean;}
  function subscriptionLabel(row){const provider=text(row?.provider),label=text(row?.label),id=text(row?.id);if(label&&label!==id)return label;if(provider&&provider!==id)return provider;return id;}
  function subscriptionOptionsForArea(area,countryCode,catalogue=[]){
    const options=new Map(),country=text(countryCode).toUpperCase();
    const stations=area?.stations||[],allOperators=area?.availableOperators||[];
    const stationIds=new Set(stations.flatMap(st=>[text(st.id),...(st.aliases||[]),...(st.evses||[]).flatMap(evse=>[text(evse.id),...(evse.aliases||[]),...(evse.pdcIds||[])])]).filter(Boolean));
    const catalogueInRadius=(catalogue||[]).filter(offer=>{
      if(!stations.length&&!allOperators.length)return false;
      const scoped=[...(offer.stationIds||[]),...(offer.evseIds||[])].map(text).filter(Boolean);
      if(scoped.length)return scoped.some(id=>stationIds.has(id));
      const operators=[...(offer.operatorIds||[]),...(offer.operatorAliases||[]),...(offer.networkIds||[]),...(offer.networkAliases||[])].map(value=>text(value).toLowerCase()).filter(Boolean);
      if(operators.length)return stations.some(st=>[text(st.physicalOperator?.id),text(st.physicalOperator?.name),text(st.networkBrand)].some(value=>operators.includes(value.toLowerCase())))||allOperators.some(op=>[text(op.id),text(op.name)].some(value=>operators.includes(value.toLowerCase())));
      return offer?.metadata?.countryWideVerified===true;
    });
    const offers=[...catalogueInRadius,...(area?.subscriptionOfferPool||[]),...stations.flatMap(station=>station?.offers||[])];
    for(const offer of offers){
      const id=text(offer?.subscriptionId);if(!id)continue;
      const countries=(offer?.countries||[]).map(value=>text(value).toUpperCase());
      if(countries.length&&!countries.includes('*')&&!countries.includes(country))continue;
      const metadata=offer?.metadata||{},label=text(metadata.subscriptionName||metadata.subscriptionLabel||offer?.subscriptionName||offer?.provider||id);
      const promotionEnd=text(offer?.monthlyFeePromotionEnd||metadata.promotionEnd),feeCurrent=!promotionEnd||promotionEnd>=new Date().toISOString().slice(0,10);
      const monthlyFeeEur=feeCurrent?num(offer?.monthlyFeeEur??metadata.monthlyFeeEur):null,annualFeeEur=num(offer?.annualFeeEur??metadata.annualFeeEur);
      if(!options.has(id))options.set(id,{id,label,provider:text(offer?.provider)||label,countries:[country],monthlyFeeEur,annualFeeEur,feeNote:feeCurrent?'':'Mensualité à vérifier après promotion',coverageNote:text(metadata.coverageNote||offer?.coverageNote),source:text(metadata.source||offer?.source),validationDate:text(metadata.validationDate||metadata.validatedAt)});
    }
    const localElectra=stations.some(st=>/electra/i.test(text(st.physicalOperator?.id)+' '+text(st.physicalOperator?.name)))||allOperators.some(op=>/electra/i.test(text(op.id)+' '+text(op.name)));
    if(!area?.preproductionCandidate&&country==='FR'&&localElectra)for(const plan of ELECTRA_PLUS_PLANS){
      if(!options.has(plan.id))options.set(plan.id,{...plan,countries:['FR'],coverageNote:'Bornes Electra avec tarif direct unique vérifié · −'+plan.discountPerKwhEur.toFixed(2)+' €/kWh',source:'Electra+',validationDate:'2026-10-13'});
    }
    return [...options.values()].sort((a,b)=>subscriptionLabel(a).localeCompare(subscriptionLabel(b),'fr'));
  }
  async function loadSubscriptionCatalogue(w,cfg){
    if(cfg.preproductionCandidateBase)return[];
    const base=String(cfg.runtimeBase||'.').replace(/\/$/,'');
    const files=['france-direct-offers.json','electra-direct-france.json'];
    const results=await Promise.all(files.map(async file=>{
      try{const response=await w.fetch(`${base}/data/v9/${file}`,{cache:'no-cache'});if(!response.ok)return[];
        const payload=await response.json();return Array.isArray(payload.subscriptionOffers)?payload.subscriptionOffers:[];
      }catch(_){return[];}
    }));
    return results.flat();
  }
  function renderSubscriptionSelector(w,options,countryCode,stations=[]){
    const compare=w.document.getElementById('compare'),card=compare?.querySelector('.card');if(!card)return;
    let box=w.document.getElementById('v9SubscriptionSelector');
    if(!box){box=w.document.createElement('div');box.id='v9SubscriptionSelector';box.className='box v9-filter-group';box.style.marginTop='10px';const primary=card.querySelector('button.primary');if(primary)card.insertBefore(box,primary);else card.appendChild(box);}
    const selected=new Set(selectedSubscriptions(w)),rows=(options||[]).slice();
    const emspProviders=[...new Set((stations||[]).flatMap(st=>st?.offers||[])
      .filter(offer=>/^(emsp|roaming)$/i.test(text(offer?.kind))||/electra|electroverse/i.test(text(offer?.provider)))
      .map(offer=>text(offer?.provider)).filter(name=>/electra|electroverse/i.test(name)))];
    const emspMessage=emspProviders.length?' Les tarifs '+emspProviders.join(', ')+' affichés dans les résultats sont des prix eMSP, distincts d’un abonnement.':'';
    const choices=rows.map(row=>'<label style="display:flex;align-items:flex-start;gap:8px;margin:0;padding:5px 2px"><input type="checkbox" value="'+esc(row.id)+'"'+(selected.has(text(row.id))?' checked':'')+' style="width:auto;margin:2px 0 0"><span><b>'+esc(subscriptionLabel(row))+'</b>'+(row.monthlyFeeEur!=null?' · '+esc(formatCurrencyAmount(row.monthlyFeeEur,'EUR'))+'/mois':row.annualFeeEur!=null?' · '+esc(formatCurrencyAmount(row.annualFeeEur,'EUR'))+'/an':row.feeNote?' · '+esc(row.feeNote):'')+'<span class="small" style="display:block">'+esc(row.coverageNote||row.provider)+'</span>'+(row.source||row.validationDate?'<span class="small" style="display:block">'+esc([row.source,row.validationDate].filter(Boolean).join(' · '))+'</span>':'')+'</span></label>').join('');
    box.innerHTML='<b>Abonnements recharge</b> <span class="small">('+rows.length+' offre(s) vérifiée(s) en '+esc(countryCode)+')</span>'+
      '<div class="small" style="margin-top:6px">Choisis les abonnements que tu possèdes. Le tarif intervient seulement sur les bornes auxquelles il s’applique; les frais mensuels sont indiqués séparément.</div>'+
      (rows.length?'<details class="v9-subscription-list" style="margin-top:8px"><summary>Choisir mes abonnements ('+selected.size+' actif(s))</summary><div id="v9SubscriptionChoices" role="group" aria-label="Abonnements recharge, sélection multiple" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:3px;max-height:180px;overflow:auto;margin-top:8px">'+choices+'</div>'+
        '<div class="row" style="margin-top:8px"><button type="button" class="secondary v9-sub-none" style="width:auto">Aucun abonnement</button></div></details>':
        '<div class="small" style="margin-top:8px">Aucun tarif d’abonnement vérifié pour les bornes de cette zone.'+esc(emspMessage)+'</div>');
    const selectedIds=()=>[...box.querySelectorAll('#v9SubscriptionChoices input:checked')].map(input=>text(input.value));
    box.querySelector('#v9SubscriptionChoices')?.addEventListener('change',event=>{
      const changed=event.target,plans=ELECTRA_PLUS_PLANS.map(plan=>plan.id);
      if(changed?.checked&&plans.includes(text(changed.value)))for(const input of box.querySelectorAll('#v9SubscriptionChoices input'))if(input!==changed&&plans.includes(text(input.value)))input.checked=false;
      saveSelectedSubscriptions(w,selectedIds());if(box._v9SubscriptionTimer)w.clearTimeout(box._v9SubscriptionTimer);box._v9SubscriptionTimer=w.setTimeout(()=>{box._v9SubscriptionTimer=null;w.compare();},150);
    });
    box.querySelector('.v9-sub-none')?.addEventListener('click',()=>{saveSelectedSubscriptions(w,[]);w.compare();});
  }

  function rankingWeights(mode){if(mode==='price')return{price:.7,distance:.3};if(mode==='distance')return{price:.3,distance:.7};return{price:.5,distance:.5};}
  function rankRows(rows,mode='balanced',limit=20){
    const rankable=x=>Number.isFinite(x.total)&&(!x.evaluation||pricedBest(x.evaluation));
    const time=x=>x.rankingChoices?.length?
      Math.min(...x.rankingChoices.map(choice=>num(choice.score?.totalTimeMinutes)??Infinity)):
      (num(x.score?.totalTimeMinutes)??Infinity);
    const cost=x=>x.rankingChoices?.length?
      Math.min(...x.rankingChoices.map(choice=>num(choice.costPerKm)??Infinity)):
      (num(x.costPerKm)??Infinity);
    const available=(rows||[]).filter(x=>rankable(x)&&Number.isFinite(x.distanceKm));
    const unknown=(rows||[]).filter(x=>!rankable(x)&&Number.isFinite(x.distanceKm)).sort((a,b)=>a.distanceKm-b.distanceKm);
    const nameTie=(a,b)=>text(a.station?.name).localeCompare(text(b.station?.name),'fr');
    if(mode==='price'){
      available.sort((a,b)=>a.total-b.total||a.distanceKm-b.distanceKm||nameTie(a,b));
      return available.concat(unknown).slice(0,limit);
    }
    if(mode==='distance'){
      available.sort((a,b)=>Number(Boolean(a.distanceEstimated))-Number(Boolean(b.distanceEstimated))||a.distanceKm-b.distanceKm||a.total-b.total||nameTie(a,b));
      return available.concat(unknown).slice(0,limit);
    }
    if(mode==='totalTime'){
      available.sort((a,b)=>time(a)-time(b)||a.total-b.total||a.distanceKm-b.distanceKm||nameTie(a,b));
      return available.concat(unknown).slice(0,limit);
    }
    if(mode==='costPerKm'){
      const withCost=available.filter(x=>Number.isFinite(cost(x))),withoutCost=available.filter(x=>!Number.isFinite(cost(x)));
      withCost.sort((a,b)=>cost(a)-cost(b)||a.total-b.total||a.distanceKm-b.distanceKm||text(a.station?.name).localeCompare(text(b.station?.name),'fr'));
      return withCost.concat(withoutCost,unknown).slice(0,limit);
    }
    if(!available.length)return unknown.slice(0,limit);
    const costs=available.map(x=>x.total),distances=available.map(x=>x.distanceKm),minC=Math.min(...costs),maxC=Math.max(...costs),minD=Math.min(...distances),maxD=Math.max(...distances),w=rankingWeights(mode);
    for(const row of available){const cn=maxC===minC?0:(row.total-minC)/(maxC-minC),dn=maxD===minD?0:(row.distanceKm-minD)/(maxD-minD);row.shellScore=w.price*cn+w.distance*dn;}
    available.sort((a,b)=>a.shellScore-b.shellScore||a.total-b.total||a.distanceKm-b.distanceKm||text(a.station?.name).localeCompare(text(b.station?.name),'fr'));
    return available.concat(unknown).slice(0,limit);
  }
  function combineDateTime(date,time,startValue=null){
    if(!date||!time)return null;
    const midnight=text(time)==='24:00',normalized=midnight?'00:00':text(time);
    let d=new Date(date+'T'+normalized+':00');
    if(!Number.isFinite(d.getTime()))return null;
    if(midnight)d=new Date(d.getTime()+24*60*60*1000);
    if(startValue){const start=new Date(startValue);if(Number.isFinite(start.getTime())&&d<=start)d=new Date(d.getTime()+24*60*60*1000);}
    return d.toISOString();
  }
  function dcCurve(condition='normal',profile='realistic'){
    const cf=condition==='warm'?1:(condition==='cold'?.68:.86),pf=profile==='optimistic'?1.08:(profile==='conservative'?.88:1);
    return V7_DC_POINTS.map(([soc,powerKw])=>({soc,powerKw:Math.max(3,powerKw*cf*pf)}));
  }
  function readInputs(w){
    const get=id=>w.document.getElementById(id),date=get('simDate')?.value||'',time=get('simTime')?.value||'',unplug=get('simUnplugTime')?.value||'',startAt=combineDateTime(date,time),disconnectAt=unplug?combineDateTime(date,unplug,startAt):null;
    const rawRadius=text(get('simMaxDistance')?.value),radius=rawRadius===''?0:Math.max(0,num(rawRadius)||0);
    const operatorSelect=get('simOperatorFilter'),selectedOperatorIds=operatorSelect?.multiple?[...operatorSelect.selectedOptions].map(option=>text(option.value)).filter(Boolean):(text(operatorSelect?.value)?[text(operatorSelect.value)]:[]),operatorMode=operatorSelect?.dataset?.v9Mode||(selectedOperatorIds.length?'selected':'all'),operatorIds=operatorMode==='all'?[]:operatorMode==='tesla'?['tesla']:selectedOperatorIds;
    const powerSelect=get('simPowerType'),acCheckbox=get('simPowerAc'),dcCheckbox=get('simPowerDc'),connectorKinds=acCheckbox&&dcCheckbox?[...(acCheckbox.checked?['AC']:[]),...(dcCheckbox.checked?['DC']:[])]:powerSelect?.multiple?[...powerSelect.selectedOptions].map(option=>text(option.value)).filter(v=>v==='AC'||v==='DC'):(text(powerSelect?.value)&&text(powerSelect?.value)!=='all'?[text(powerSelect.value)]:[]);
    const minPowerInput=num(get('simMinPowerKw')?.value),maxPowerInput=num(get('simMaxPowerKw')?.value);
    const minPowerKw=minPowerInput!=null?Math.max(1,minPowerInput):null,maxPowerKw=maxPowerInput!=null?Math.max(1,maxPowerInput):null;
    return{startSoc:num(get('simNow')?.value),targetSoc:num(get('simTarget')?.value),date,time,startAt,disconnectAt,condition:get('simCondition')?.value||'normal',profile:get('simProfile')?.value||'realistic',batteryCapacityKwh:num(get('v9BatteryCapacity')?.value),consumptionKwhPer100Km:num(get('v9Consumption')?.value),vehicleMaxAcKw:num(get('v9MaxAc')?.value),vehicleMaxDcKw:num(get('v9MaxDc')?.value),operatorMode,operatorIds,connectorKinds,minPowerKw,maxPowerKw,rankingMode:get('simRanking')?.value||'balanced',radiusKm:radius,originText:text(get('simOrigin')?.value)};
  }
  function currencyForCountry(countryCode){return{CH:'CHF',GB:'GBP',MA:'MAD'}[text(countryCode).toUpperCase()]||'EUR';}
  function buildSession(input,countryCode){const bounded=(value,min,max,fallback)=>typeof value==='number'&&Number.isFinite(value)&&value>=min&&value<=max?value:fallback;return{startSoc:input.startSoc,targetSoc:input.targetSoc,startAt:input.startAt,disconnectAt:input.disconnectAt,targetCurrency:currencyForCountry(countryCode),batteryCapacityKwh:bounded(input.batteryCapacityKwh,10,250,75),consumptionKwhPer100Km:bounded(input.consumptionKwhPer100Km,5,60,15),vehicleMaxAcKw:bounded(input.vehicleMaxAcKw,1,43,11),vehicleMaxDcKw:bounded(input.vehicleMaxDcKw,1,500,250),chargeEfficiency:.92,chargeCurve:dcCurve(input.condition,input.profile)};}
  function diagnosticStore(w,event){try{const key='tccV9ProductionShellDiagnosticsV1',rows=JSON.parse(w.localStorage.getItem(key)||'[]');rows.unshift({...event,at:new Date().toISOString()});w.localStorage.setItem(key,JSON.stringify(rows.slice(0,20)));}catch(_){}}
  async function countryCodeForOrigin(w,origin){
    const cacheKey=`tcc-v9-country:${Number(origin.lat).toFixed(3)},${Number(origin.lon).toFixed(3)}`;
    try{const cached=w.sessionStorage.getItem(cacheKey);if(cached)return cached;}catch(_){ }
    const url=`https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&lat=${encodeURIComponent(origin.lat)}&lon=${encodeURIComponent(origin.lon)}`;
    const response=await w.fetch(url,{headers:{Accept:'application/json'}});if(!response.ok)throw new Error(`country lookup ${response.status}`);const data=await response.json();const code=text(data?.address?.country_code).toUpperCase();if(!/^[A-Z]{2}$/.test(code))throw new Error('country unavailable');
    try{w.sessionStorage.setItem(cacheKey,code);}catch(_){ }return code;
  }
  function adapters(w){return{teslaJson:w.TCCV9Adapters?.teslaJson,nationalCompact:w.TCCV9Adapters?.nationalCompact,directOffers:w.TCCV9Adapters?.directOffers,legacyDirectTariffs:w.TCCV9Adapters?.legacyDirectTariffs,legacyDirectStations:w.TCCV9Adapters?.legacyDirectStations,franceEmspCompact:w.TCCV9Adapters?.franceEmspCompact,franceCrosswalk:w.TCCV9Adapters?.franceCrosswalk,franceIrveStatus:w.TCCV9Adapters?.franceIrveStatus,moroccoPublic:w.TCCV9Adapters?.moroccoPublic,moroccoKilowattTariff:w.TCCV9Adapters?.moroccoKilowattTariff};}
  function verifiedExchangeRates(payload){
    if(!payload||text(payload.base).toUpperCase()!=='EUR'||!/^\d{4}-\d{2}-\d{2}$/.test(text(payload.date))||
       !Number.isFinite(Date.parse(payload.checkedAt))||!text(payload.source)||num(payload.rates?.EUR)!==1)return{EUR:1};
    const rates={EUR:1};
    for(const [currency,value] of Object.entries(payload.rates||{})){
      const rate=num(value);if(/^[A-Z]{3}$/.test(currency)&&rate!=null&&rate>0)rates[currency]=rate;
    }
    return rates;
  }
  function pinnedTeslaInventory(w,base,source,expectedSha){
    if(!/^[a-f0-9]{64}$/.test(String(expectedSha||''))||source?.id!=='tesla-global'||
       source.adapter!=='tesla-json'||source.path!=='data/tesla_stations.json'||
       !w.TCCV9Adapters?.teslaJson?.normalizePayload||!w.TCCV9Adapters?.teslaJson?.provedConfigurationOffers||!w.TCCV9PreparedCandidate?.sha256Hex)
      throw new Error('pinned Tesla inventory unavailable');
    let promise=null;
    return async function(){
      if(!promise)promise=w.fetch(`${base}/${source.path}`,{cache:'no-cache'}).then(async response=>{
        if(!response.ok)throw new Error(`Tesla inventory ${response.status}`);
        const bytes=new Uint8Array(await response.arrayBuffer());
        if(await w.TCCV9PreparedCandidate.sha256Hex(bytes,w.crypto)!==expectedSha)
          throw new Error('Tesla inventory SHA mismatch');
        const payload=JSON.parse(new TextDecoder().decode(bytes));
        const rawStations=Array.isArray(payload)?payload:payload?.stations||[];
        const stations=w.TCCV9Adapters.teslaJson.normalizePayload(payload);
        const rawById=new Map(rawStations.map(raw=>[String(raw.id),raw]));
        if(rawById.size!==rawStations.length)throw new Error('Tesla inventory duplicate source IDs');
        // Preserve exact source configuration scope. The common engine still rejects
        // incomplete or unsupported billed components. Tesla is never projected
        // onto a national catalogue: source configurations define its scope.
        return stations.map(station=>{
          const offers=w.TCCV9Adapters.teslaJson.provedConfigurationOffers(rawById.get(station.sourceStationId),station);
          const provedIds=new Set(offers.map(offer=>offer.id));
          return {...station,offers,
            unparsedOffers:(station.offers||[]).filter(offer=>!provedIds.has(offer.id)).map(offer=>({
              id:offer.id,channel:'Direct',scope:{evseId:offer.evseIds?.[0],connectorId:null},
              rawOffer:offer,calculationStatus:'not_evaluated'})),
            status:{state:'unknown',updatedAt:station.status?.updatedAt||null,sourceId:'tesla-global'}};
        });
      }).catch(error=>{promise=null;throw error;});
      return promise;
    };
  }
  async function createEngine(w,cfg){
    if(!w.TCCV9RuntimeEngine||!w.TCCV9BrowserLoaders||!w.TCCV9BrowserRouting)throw new Error('V9 runtime dependency missing');
    const base=String(cfg.runtimeBase||'.').replace(/\/$/,''),[historicalRegistry,vehicleProfiles]=await Promise.all([
      w.fetch(`${base}/data/v9/source-registry.json`,{cache:'no-cache'}).then(r=>{if(!r.ok)throw new Error(`registry ${r.status}`);return r.json();}),
      w.fetch(`${base}/data/v9/vehicle-profiles.json`,{cache:'no-cache'}).then(r=>{if(!r.ok)throw new Error(`vehicle profiles ${r.status}`);return r.json();})
    ]);
    const exchangeUrl=new URL('../data/exchange_rates.json',w.location.href).toString();
    const exchange=await w.fetch(exchangeUrl,{cache:'no-cache'}).then(async r=>{
      if(!r.ok){if(cfg.fxArtifactSha256)throw new Error('Pinned FX unavailable');return null;}
      const bytes=new Uint8Array(await r.arrayBuffer());
      if(cfg.fxArtifactSha256&&await w.TCCV9PreparedCandidate.sha256Hex(bytes,w.crypto)!==cfg.fxArtifactSha256)throw new Error('Pinned FX SHA mismatch');
      return JSON.parse(new TextDecoder().decode(bytes));
    }).catch(error=>{if(cfg.fxArtifactSha256)throw error;return null;});
    let registry=historicalRegistry,
      loaders=cfg.preproductionCandidateBase?{}:
        w.TCCV9BrowserLoaders.createRegistryLoaders({registry,basePath:base,adapters:adapters(w)}),
      preparedCandidate=null;
    if(cfg.preproductionCandidateBase){
      // NEVER blend unevaluated candidate tariffs into the historical priced catalog.
      if(cfg.mode!=='candidate'||cfg.preproductionIsolated!==true||!/^[a-f0-9]{64}$/.test(String(cfg.nationalPolicySha256||''))||!w.TCCV9PreparedCandidate?.loadPrepared||!w.TCCV9CanonicalAdapter?.toFragments)
        throw new Error('isolated preproduction candidate not configured safely');
      const preview=await w.TCCV9PreparedCandidate.loadPrepared({
        baseUrl:cfg.preproductionCandidateBase,fetchImpl:w.fetch.bind(w),adapter:w.TCCV9CanonicalAdapter,
        cryptoImpl:w.crypto,origin:w.location.href,expectedIndexSha256:cfg.preparedIndexSha256,expectedNationalPolicySha256:cfg.nationalPolicySha256
      });
      if(preview.candidate.bundleId!==cfg.preparedBundleId)throw new Error('prepared bundle identity mismatch');
      registry=preview.registry;loaders=preview.loaders;preparedCandidate=preview.candidate;
      const tesla=historicalRegistry.sources?.find(source=>source.id==='tesla-global');
      const teslaLoader=pinnedTeslaInventory(w,base,tesla,cfg.teslaArtifactSha256);
      if(registry.sources.some(source=>source.id==='tesla-global'))throw new Error('Tesla source collision');
      registry={...registry,autonomousTesla:true,sources:[...registry.sources,tesla]};
      loaders={...loaders,'tesla-global':teslaLoader};
    }
    const routeProvider=w.TCCV9BrowserRouting.osrmProvider();
    const engine=w.TCCV9RuntimeEngine.createEngine({registry,loaders,routeProvider,vehicleProfiles});
    engine.__tccFxRates=verifiedExchangeRates(exchange);
    engine.__tccPreparedCandidate=preparedCandidate;
    return engine;
  }
  function straightLineDistanceKm(origin,station){
    const lat1=num(origin?.lat??origin?.latitude),lon1=num(origin?.lon??origin?.longitude),lat2=num(station?.latitude),lon2=num(station?.longitude);
    if([lat1,lon1,lat2,lon2].some(value=>value==null))return null;
    const rad=Math.PI/180,dLat=(lat2-lat1)*rad,dLon=(lon2-lon1)*rad,a=Math.sin(dLat/2)**2+Math.cos(lat1*rad)*Math.cos(lat2*rad)*Math.sin(dLon/2)**2;
    return 12742*Math.atan2(Math.sqrt(a),Math.sqrt(Math.max(0,1-a)));
  }
  function rowsFromArea(area,origin=area?.query?.origin){return(area.rankedStations||area.stations||[]).map(st=>{const evaluation=area.sessionEvaluations?.[st.id],best=pricedBest(evaluation),score=area.stationScores?.[st.id],route=area.routes?.byStationId?.[st.id],routedDistance=num(score?.distanceKm??route?.distanceKm);return{station:st,evaluation,score,route,total:num(best?.total),costPerKm:num(best?.costPerRecoveredKm),recoveredKm:num(evaluation?.recoveredKm??best?.result?.recoveredKm),distanceKm:routedDistance??straightLineDistanceKm(origin,st),distanceEstimated:routedDistance==null};});}
  function maxPower(st){let max=0;for(const evse of st?.evses||[])for(const c of evse?.connectors||[])max=Math.max(max,num(c?.powerKw)||0);return max;}
  function connectorKind(c={}){const raw=text(c.kind||c.currentType||c.powerType||c.plugName||c.plugType).toUpperCase();if(raw.includes('DC')||raw.includes('CCS')||raw.includes('CHADEMO'))return'DC';if(raw.includes('AC')||raw.includes('TYPE2')||raw.includes('TYPE 2'))return'AC';const power=num(c.powerKw);return power!=null&&power>22?'DC':'AC';}
  function powerLines(row){
    if(row?.powerLine)return[row.powerLine];
    const map=new Map(),station=row?.station||{};
    for(const [evseIndex,evse] of (station.evses||[]).entries())for(const connector of evse.connectors||[]){
      const power=floorPower(connector.powerKw??connector.power??evse.powerKw);if(power==null||power<=0)continue;
      const kind=connectorKind(connector),key=kind+':'+power,current=map.get(key)||{kind,powerKw:power,evseIds:new Set()};
      current.evseIds.add(text(evse.id||evse.evseId||evse.idTag)||'evse-'+evseIndex);map.set(key,current);
    }
    return [...map.values()].map(line=>({kind:line.kind,powerKw:line.powerKw,count:line.evseIds.size})).sort((a,b)=>a.kind.localeCompare(b.kind)||b.powerKw-a.powerKw);
  }
  function formatMinutes(value){const n=num(value);if(n==null)return'—';const total=Math.max(0,Math.round(n)),h=Math.floor(total/60),m=total%60;return h?h+' h '+String(m).padStart(2,'0')+' min':m+' min';}
  function formatRate(value,currency,unit){const n=num(value);if(n==null)return null;return Number(n).toLocaleString('fr-FR',{minimumFractionDigits:2,maximumFractionDigits:3})+' '+text(currency||'EUR').toUpperCase()+'/'+unit;}
  function tariffRateLabels(offer){
    const pricing=offer?.pricing||{},rules=[...(Array.isArray(pricing.rules)?pricing.rules:[]),...(pricing.componentGroups||[]).flatMap(group=>group.rules||[])],labels=[],seen=new Set();
    if(pricing.type==='electroverse_restrictions'){
      const rates=pricing.fallbackRates||{},currency=pricing.currency||offer?.currency||'EUR';
      const add=(value,unit)=>{const label=formatRate(value,currency,unit);if(label&&!labels.includes(label))labels.push(label);};
      add(rates.energy,'kWh');add(rates.chargingMinute,'min de charge');add(rates.parkingMinute,'min de stationnement');
      if(num(rates.flat)>0)labels.push(formatCurrencyAmount(rates.flat,currency)+' frais fixes');
      for(const rule of rules){const r=rule?.rates||{};add(r.energy,'kWh');add(r.chargingMinute,'min de charge');add(r.parkingMinute,'min de stationnement');}
      return labels;
    }
    const fields=['pricePerKwh','pricePerMinute','chargePerMinute','chargingTimePerMinuteEur','connectedTimePerMinuteEur','idlePerMinute','connectionFee','sessionFeeEur','connectedTimeComponentEur','connectedTimeBlockEur'];
    const positive=rule=>fields.some(key=>(num(rule?.[key])??0)>0)||(Array.isArray(rule?.ocpiDurationBands)&&rule.ocpiDurationBands.some(b=>(num(b?.[3])??0)>0));
    const zeroPlaceholder=rule=>{
      const values=fields.map(key=>num(rule?.[key])).filter(value=>value!=null);
      return values.length>0&&values.every(value=>value===0)&&!positive(rule)&&
        !(Array.isArray(rule?.ocpiDurationBands)&&rule.ocpiDurationBands.some(b=>(num(b?.[3])??0)>0));
    };
    const hasPricedWindow=rules.some(rule=>rule?.scope!=='allDay'&&positive(rule));
    const add=(value,unit,currency,qualifier='')=>{
      if((num(value)??0)<=0)return;
      const label=formatRate(value,currency,unit);if(!label)return;
      const full=label+qualifier;if(!seen.has(full)){seen.add(full);labels.push(full);}
    };
    for(const rule of rules){
      if(hasPricedWindow&&rule?.scope==='allDay'&&zeroPlaceholder(rule))continue;
      const currency=rule?.currency||pricing.currency||offer?.currency;
      if(Array.isArray(rule?.powerBands)&&rule.powerBands.length){
        for(const band of rule.powerBands){
          const lower=num(band?.minKw),upper=num(band?.maxKw),rate=formatRate(band?.ratePerMinute,currency,'min');
          if(!rate)continue;
          const range=lower==null?'':upper==null||upper>=1000?' (≥ '+lower+' kW délivrés)':' ('+lower+'–'+upper+' kW délivrés)';
          const label=rate+range;if(!seen.has(label)){seen.add(label);labels.push(label);}
        }
        const fee=num(rule.connectionFee);
        if(fee>0){const label=formatCurrencyAmount(fee,currency)+' frais de connexion';if(!seen.has(label)){seen.add(label);labels.push(label);}}
        continue;
      }
      const window=rule?.scope==='allDay'?'':' ('+text(rule?.start||'')+'–'+text(rule?.end||'')+')';
      add(rule?.pricePerKwh,'kWh',currency,window);
      add(rule?.pricePerMinute,'min',currency,' connecté'+window);
      add(rule?.chargePerMinute??rule?.chargingTimePerMinuteEur,'min',currency,' charge'+window);
      add(rule?.connectedTimePerMinuteEur,'min',currency,' connecté'+window);
      add(rule?.idlePerMinute,'min',currency,' après charge'+window);
      add(rule?.congestionTimePerMinute,'min congestion',currency,' dès '+(num(rule?.congestionStartSoc)??80)+' %'+window);
      const afterPhase={CONNECTED_TIME:'connexion',TIME:'charge',PARKING_TIME:'stationnement'}[rule?.afterMinutesComponent];
      if((num(rule?.afterMinutesRate)??0)>0&&afterPhase&&num(rule?.afterMinutesThreshold)!=null){
        add(rule.afterMinutesRate,'min',currency,' de '+afterPhase+' après '+rule.afterMinutesThreshold+' min de session'+window);
        if((num(rule.afterMinutesCap)??0)>0&&['whole_session','night_window_local_per_night'].includes(rule.afterMinutesCapMode)){
          const label='Plafond des frais après seuil '+formatCurrencyAmount(rule.afterMinutesCap,currency)+(rule.afterMinutesCapMode==='whole_session'?' par session':' par nuit ('+text(rule.afterMinutesCapStart)+'–'+text(rule.afterMinutesCapEnd)+')');
          if(!seen.has(label)){seen.add(label);labels.push(label);}
        }
      }
      for(const [field,description] of [['connectionFee','frais de connexion'],['sessionFeeEur','frais de session'],['connectedTimeComponentEur','temps connecté']]){
        const value=num(rule?.[field]);if(value==null||value===0)continue;
        const label=formatCurrencyAmount(value,currency)+' '+description+window;
        if(!seen.has(label)){seen.add(label);labels.push(label);}
      }
      if(num(rule?.connectedTimeBlockMinutes)>0&&num(rule?.connectedTimeBlockEur)!=null){
        const label=formatCurrencyAmount(rule.connectedTimeBlockEur,currency)+' / '+rule.connectedTimeBlockMinutes+' min connectées'+window;
        if(!seen.has(label)){seen.add(label);labels.push(label);}
      }
      if(num(rule?.minimumSessionEur)>0){const label='Minimum '+formatCurrencyAmount(rule.minimumSessionEur,currency)+window;if(!seen.has(label)){seen.add(label);labels.push(label);}}
      if(Array.isArray(rule?.ocpiDurationBands))for(const band of rule.ocpiDurationBands){
        const rate=formatRate(band?.[3],currency,'min');if(!rate)continue;
        const label=rate+' ('+text(band?.[0])+'–'+text(band?.[1])+' min)';if(!seen.has(label)){seen.add(label);labels.push(label);}
      }
    }
    add(pricing.pricePerKwh,'kWh',pricing.currency||offer?.currency);
    add(pricing.pricePerMinute,'min',pricing.currency||offer?.currency,' connecté');
    add(pricing.chargePerMinute??pricing.chargingTimePerMinuteEur,'min',pricing.currency||offer?.currency,' charge');
    const longFee=pricing.longConnectionFee;
    if(num(longFee?.eurPerHourAfterThreshold)>0){
      const label=formatRate(longFee.eurPerHourAfterThreshold,pricing.currency||offer?.currency,'h')+' après '+longFee.thresholdMinutes+' min';
      if(!seen.has(label)){seen.add(label);labels.push(label);}
    }
    if(!labels.length&&rules.some(rule=>num(rule?.pricePerKwh)===0))labels.push(formatRate(0,pricing.currency||offer?.currency,'kWh'));
    return labels;
  }
  function appliedTariffRateLabels(item,offer){
    const result=item?.result||{},components=result.components||{};
    if(components.powerMinute)return tariffRateLabels(offer);
    const charged=(value,key)=>{
      if(!value||typeof value!=='object')return false;
      if((num(value[key])??num(value[key]?.totalEur)??0)>0)return true;
      return Object.values(value).some(child=>Array.isArray(child)?child.some(part=>charged(part,key)):charged(child,key));
    };
    const groups=(components.componentGroups||[]).filter(group=>group?.matched);
    const segments=[
      ...(components.segmentedPricing?.segments||[]),
      ...(components.energyTimeline?.segments||[]),
      ...groups.flatMap(group=>group?.components?.segmentedPricing?.segments||[])
    ];
    const entries=segments.filter(segment=>segment?.rule).map(segment=>({rule:segment.rule,components:segment.components||{}}));
    if(!entries.length)entries.push(...groups.filter(group=>group?.rule).map(group=>({rule:group.rule,components:group.components||{}})));
    if(!entries.length&&result.matchedRule)entries.push({rule:result.matchedRule,components});
    if(!entries.length)return[];
    const used=entries.map(({rule,components:part})=>({
      ...rule,
      idlePerMinute:charged(part,'parkingTime')?rule.idlePerMinute:null,
      congestionTimePerMinute:charged(part,'congestionTime')?rule.congestionTimePerMinute:null
    }));
    const labels=tariffRateLabels({currency:item?.currency||offer?.currency,pricing:{rules:used}});
    for(const window of components.postCharge?.appliedRateWindows||[]){
      if((num(window?.billedMinutes)??0)<=0||(num(window?.costEur)??0)<=0)continue;
      const rate=formatRate(window.eurPerMinute,item?.currency||offer?.currency,'min après charge');
      if(rate)labels.push(rate+' ('+text(window.start)+'–'+text(window.end)+')');
    }
    return[...new Set(labels)];
  }
  function baseTariffsForPower(row,line){
    const station=row?.station||{},out=[],seen=new Set(),connectors=[];
    for(const evse of station.evses||[])for(const connector of evse.connectors||[]){
      const power=num(connector.powerKw??connector.power??evse.powerKw);
      if(power!=null&&floorPower(power)===line.powerKw&&connectorKind(connector)===line.kind)connectors.push(connector);
    }
    const connectorIds=new Set(connectors.map(c=>text(c.id||c.connectorId)).filter(Boolean));
    const plugNames=new Set(connectors.map(c=>text(c.plugName||c.type).toUpperCase()).filter(Boolean));
    for(const offer of station.offers||[]){
      const kinds=Array.isArray(offer?.connectorKinds)?offer.connectorKinds.map(v=>text(v).toUpperCase()).filter(Boolean):[];
      if(kinds.length&&!kinds.includes(text(line.kind).toUpperCase()))continue;
      const min=num(offer?.minPowerKw),max=num(offer?.maxPowerKw);
      if(min!=null&&line.powerKw<floorPower(min))continue;
      if(max!=null&&line.powerKw>floorPower(max))continue;
      const ids=(offer?.connectorIds||[]).map(text).filter(Boolean);
      if(ids.length&&![...connectorIds].some(id=>ids.includes(id)))continue;
      const plugs=(offer?.plugNames||[]).map(v=>text(v).toUpperCase()).filter(Boolean);
      if(plugs.length&&![...plugNames].some(name=>plugs.includes(name)))continue;
      const provider=text(offer?.provider||offer?.network||offer?.operator||'tarif');
      for(const rate of tariffRateLabels(offer)){
        const label=rate+' · '+provider;
        if(!seen.has(label)){seen.add(label);out.push(label);}
      }
    }
    return out;
  }
  function evaluatedBaseTariffs(row){
    const station=row?.station||{},item=row?.evaluation?.best,labels=[];
    if(!item||!['cpo_direct','direct','subscription'].includes(text(item.kind).toLowerCase()))return labels;
    const offer=(station.offers||[]).find(candidate=>text(candidate?.id||candidate?.offerId)===text(item.offerId));
    const result=item.result||{},segments=[
      ...(result?.components?.segmentedPricing?.segments||[]),
      ...(result?.components?.energyTimeline?.segments||[])
    ];
    const rules=segments.map(segment=>segment?.rule).filter(Boolean);
    if(!rules.length&&result.matchedRule)rules.push(result.matchedRule);
    const effectiveOffer=offer||{currency:item.currency,pricing:{rules}};
    const rates=rules.length?tariffRateLabels({currency:item.currency||effectiveOffer.currency,pricing:{rules}}):tariffRateLabels(effectiveOffer);
    for(const rate of rates){const label=rate+' · '+text(item.provider||'tarif');if(!labels.includes(label))labels.push(label);}
    return labels;
  }
  function renderPowerLines(row){
    const lines=powerLines(row);if(!lines.length)return'<div class="small">Puissance non renseignée</div>';
    const applied=row?.evaluation?.best||null;
    const appliedRules=[];
    const matched=applied?.result?.matchedRule;
    if(matched)appliedRules.push(matched);
    for(const segment of [
      ...(applied?.result?.components?.segmentedPricing?.segments||[]),
      ...(applied?.result?.components?.energyTimeline?.segments||[]),
      ...(applied?.result?.components?.compactMinute?.segments||[])
    ]){if(segment?.rule)appliedRules.push(segment.rule);}
    const appliedLabels=appliedRules.length?tariffRateLabels({currency:applied.currency||'EUR',pricing:{rules:appliedRules}}):[];
    const appliedOffer=(row?.station?.offers||[]).find(offer=>text(offer?.id||offer?.offerId)===text(applied?.offerId));
    const hasTimeWindows=(appliedOffer?.pricing?.rules||[]).some(rule=>rule?.scope!=='allDay');
    const electroversePricing=appliedOffer?.pricing?.type==='electroverse_restrictions'?appliedOffer.pricing:null;
    const electroverseLabels=[];
    if(electroversePricing){
      const components=['energy','chargingMinute','parkingMinute','flat'];
      const used=applied?.result?.components?.segments||[];
      for(const segment of used){
        let indices;try{indices=JSON.parse(segment.ruleSignature);}catch(_){continue;}
        for(const component of components){
          const index=indices?.[component],rule=index==null?null:electroversePricing.rules?.[index],value=num(rule?.rates?.[component]??electroversePricing.fallbackRates?.[component]);
          if(value==null||value===0)continue;
          const label=component==='flat'?formatCurrencyAmount(value,appliedOffer.currency||'EUR')+' frais fixes':formatRate(value,appliedOffer.currency||'EUR',{energy:'kWh',chargingMinute:'min de charge',parkingMinute:'min de stationnement'}[component]);
          if(label&&!electroverseLabels.includes(label))electroverseLabels.push(label);
        }
      }
    }
    return'<div class="v9-power-lines" style="margin-top:8px">'+lines.map(line=>{
      const fallback=applied&&!hasTimeWindows&&appliedOffer?tariffRateLabels(appliedOffer):[];
      const longFee=appliedOffer?.pricing?.longConnectionFee;
      const longFeeLabels=longFee?tariffRateLabels({currency:appliedOffer.currency,pricing:{longConnectionFee:longFee}}):[];
      const tariffs=[...new Set([...(electroverseLabels.length?electroverseLabels:appliedLabels.length?appliedLabels:fallback),...longFeeLabels])];
      const provider=text(applied?.provider||'');
      const baseLine=tariffs.length
        ?'<div class="small" style="color:#c7d0d9">Base utilisée: '+tariffs.map(esc).join(' · ')+(provider?' · '+esc(provider):'')+(hasTimeWindows&&appliedOffer?.pricing?.timeZone==='UTC'?' · horaires UTC':'')+'</div>'
        :row?.evaluation?.best
          ?'<div class="small" style="color:#c7d0d9">Tarif unitaire appliqué non détaillé · prix final ci-dessous</div>'
          :'<div class="small" style="color:#c7d0d9">Tarif de base non disponible</div>';
      return '<div class="small" style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start"><span>'+esc(line.kind)+' · <b>'+(unverifiedFranceDcPower(row?.station,line.kind,line.powerKw)?'Puissance à vérifier':line.powerKw+' kW')+'</b>'+baseLine+'</span><span>'+line.count+' PDC</span></div>';
    }).join('')+'</div>';
  }
  function renderMapSummary(w,area,rows){
    const engine=w.TCCV9MapPriceEngine;if(!engine)return;
    const host=w.document.getElementById('v9MapSummary')||w.document.createElement('section');host.id='v9MapSummary';host.className='box';host.style.cssText='margin:10px 0;background:#11151a;border:1px solid #28323d';
    const bestByStation=new Map();for(const row of [...(area?.mapRankingRows||[]),...(rows||[])]){const id=text(row?.station?.id||row?.station?.canonicalId||row?.station?.stationId);if(!id)continue;const current=bestByStation.get(id),cost=num(pricedBest(row?.evaluation)?.total),previous=num(pricedBest(current?.evaluation)?.total);if(!current||current.summaryOnly&&!row.summaryOnly||(cost!=null&&(previous==null||cost<previous)))bestByStation.set(id,row);}
    const currentPoints=[...bestByStation.values()],points=(area?.mapStations?.length?area.mapStations.map(st=>{const row=bestByStation.get(text(st.id));return row?{...row,mapPage:st.page}:{station:st,mapPage:st.page};}):currentPoints).filter(row=>Number.isFinite(Number(row?.station?.latitude))&&Number.isFinite(Number(row?.station?.longitude))),zoneRows=engine.summarizeZones(currentPoints,{precision:1}),visible=zoneRows.slice(0,12);
    host.innerHTML='<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap"><b>Résultats V9</b><div role="group" aria-label="Mode d’affichage"><button type="button" class="secondary v9-view-list" style="width:auto;padding:6px 10px">☷ Liste</button><button type="button" class="secondary v9-view-map" style="width:auto;padding:6px 10px">⌖ Carte</button></div></div><div class="small" style="margin-top:6px">'+esc(area?.preproductionCandidate?'Carte OpenStreetMap · prix des offres calculables ; offres brutes sans prix simulé · les stations proches sont regroupées.':'Carte OpenStreetMap · étiquette = prix total simulé de la session, au meilleur tarif disponible · les stations proches sont regroupées.')+'</div><div id="v9MapZones" style="display:none;margin-top:8px"><div class="v9-real-map" role="img" aria-label="Carte des stations V9 sur fond OpenStreetMap" style="position:relative;width:100%;height:380px;overflow:hidden;border:1px solid #34404c;border-radius:8px;background:#e5e3df;touch-action:none"><div class="v9-map-tiles" style="position:absolute;inset:0"></div><div class="v9-map-markers" style="position:absolute;inset:0;pointer-events:none"></div><div style="position:absolute;right:10px;top:10px;display:grid;gap:4px"><button type="button" class="v9-map-zoom-in" aria-label="Zoomer" style="width:34px;padding:5px;background:white;color:#111">+</button><button type="button" class="v9-map-zoom-out" aria-label="Dézoomer" style="width:34px;padding:5px;background:white;color:#111">−</button></div><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener" style="position:absolute;bottom:2px;right:4px;background:#ffffffdd;color:#222;font-size:10px">© OpenStreetMap</a></div><div class="small" style="margin-top:5px">Déplacez la carte ou zoomez ; sélectionnez un prix pour voir les tarifs.</div><div id="v9MapSelected" class="box" style="display:none;margin-top:8px"></div></div><div id="v9MapZoneSummary" style="display:none;margin-top:8px">'+(visible.length?'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px">'+visible.map(z=>'<div style="padding:8px;border-radius:8px;background:#1a222b"><b>'+engine.formatPricePerKm(z.bestPricePerKm)+'</b><div class="small">'+esc(z.bestStation?stationDisplayName(z.bestStation):'Zone')+' · '+z.pricedStationCount+'/'+z.stationCount+' tarifée(s)</div></div>').join('')+'</div>':'<div class="small">Aucun prix/km vérifiable dans cette zone.</div>')+'</div>';
    const results=w.document.getElementById('results');if(results&&host.parentNode!==results.parentNode)results.parentNode.insertBefore(host,results);
    const listButton=host.querySelector('.v9-view-list'),mapButton=host.querySelector('.v9-view-map'),zones=host.querySelector('#v9MapZones'),summary=host.querySelector('#v9MapZoneSummary'),selected=host.querySelector('#v9MapSelected'),canvas=host.querySelector('.v9-real-map'),tiles=host.querySelector('.v9-map-tiles'),markers=host.querySelector('.v9-map-markers');
    if(canvas){canvas.style.backgroundColor='#e5e3df';canvas.style.backgroundImage='linear-gradient(#c8d0d4 1px, transparent 1px),linear-gradient(90deg,#c8d0d4 1px, transparent 1px)';canvas.style.backgroundSize='64px 64px';}
    const tileWarning=w.document.createElement('div');tileWarning.className='v9-map-tile-warning';tileWarning.setAttribute('role','status');tileWarning.textContent='Fond cartographique indisponible · les repères restent utilisables';tileWarning.style.cssText='display:none;position:absolute;left:8px;bottom:8px;z-index:2;padding:4px 7px;border-radius:4px;background:#fff;color:#222;font-size:11px';canvas?.appendChild(tileWarning);
    tiles?.addEventListener('error',event=>{if(event.target?.tagName==='IMG')tileWarning.style.display='block';},true);
    const project=(lat,lon,z)=>{const scale=256*2**z,clamped=Math.max(-85.0511,Math.min(85.0511,lat)),rad=clamped*Math.PI/180;return{x:(lon+180)/360*scale,y:(1-Math.log(Math.tan(rad)+1/Math.cos(rad))/Math.PI)/2*scale};};
    const unproject=(x,y,z)=>{const scale=256*2**z,n=Math.PI-2*Math.PI*y/scale;return{lat:180/Math.PI*Math.atan(Math.sinh(n)),lon:x/scale*360-180};};
    const mapViewKey=JSON.stringify({origin:area?.query?.origin,radiusKm:area?.query?.radiusKm,filters:area?.query?.filters}),savedView=host._v9MapView?.key===mapViewKey?host._v9MapView:null;
    const lats=points.map(row=>Number(row.station.latitude)),lons=points.map(row=>Number(row.station.longitude));
    let center=points.length?{lat:(Math.min(...lats)+Math.max(...lats))/2,lon:(Math.min(...lons)+Math.max(...lons))/2}:{lat:Number(area?.query?.origin?.lat)||46.6,lon:Number(area?.query?.origin?.lon)||2.2},zoom=12,drag=null;
    let viewInitialized=!!savedView;if(savedView){center=savedView.center;zoom=savedView.zoom;}
    const fit=()=>{if(!points.length)return;const width=Math.max(320,canvas?.clientWidth||640),height=Math.max(260,canvas?.clientHeight||380);for(let z=16;z>=3;z--){const p=points.map(row=>project(Number(row.station.latitude),Number(row.station.longitude),z));if(Math.max(...p.map(v=>v.x))-Math.min(...p.map(v=>v.x))<width-70&&Math.max(...p.map(v=>v.y))-Math.min(...p.map(v=>v.y))<height-70){zoom=z;break;}}};
    const draw=()=>{if(!canvas||!tiles||!markers||!canvas.clientWidth)return;host._v9MapView={key:mapViewKey,center:{...center},zoom};const width=canvas.clientWidth,height=canvas.clientHeight,mid=project(center.lat,center.lon,zoom),left=mid.x-width/2,top=mid.y-height/2,world=2**zoom;let tileHtml='';for(let tx=Math.floor(left/256);tx<=Math.floor((left+width)/256);tx++)for(let ty=Math.floor(top/256);ty<=Math.floor((top+height)/256);ty++){if(ty<0||ty>=world)continue;const wrapped=((tx%world)+world)%world;tileHtml+='<img src="https://tile.openstreetmap.org/'+zoom+'/'+wrapped+'/'+ty+'.png" alt="" draggable="false" loading="lazy" style="position:absolute;left:'+(tx*256-left).toFixed(1)+'px;top:'+(ty*256-top).toFixed(1)+'px;width:256px;height:256px;max-width:none">';}tiles.innerHTML=tileHtml;
      const clusters=[],grid=new Map(),cell=zoom>=14?54:zoom>=10?70:90;
      points.forEach((row,index)=>{const p=project(Number(row.station.latitude),Number(row.station.longitude),zoom),x=p.x-left,y=p.y-top;
        if(x< -cell||y< -cell||x>width+cell||y>height+cell)return;
        const key=Math.floor(x/cell)+','+Math.floor(y/cell);let group=grid.get(key);
        if(!group){group={x,y,indices:[],best:null,hasRaw:false};grid.set(key,group);clusters.push(group);}
        group.indices.push(index);const priced=pricedBest(row.evaluation);if(priced&&(!group.best||priced.total<group.best.total))group.best=priced;
        if(!group.hasRaw)group.hasRaw=row.station?.hasRawOffer===true||(row.station?.unparsedOffers||[]).some(o=>o.calculationStatus==='not_evaluated');
      });
      markers.innerHTML=clusters.map((group,clusterIndex)=>{const first=points[group.indices[0]],count=group.indices.length,label=count===1?stationDisplayName(first.station):count+' stations proches',best=group.best,amount=best?formatCurrencyAmount(best.total,best.targetCurrency||currencyForCountry(first.station?.countryCode)):group.hasRaw?'Incalculable':'Sans prix';return'<button type="button" class="v9-map-marker" data-cluster="'+clusterIndex+'" title="'+esc(label)+'" aria-label="Sélectionner '+esc(label)+' · '+esc(best?'session dès '+amount:group.hasRaw?'tarif incalculable':'prix non disponible')+'" style="position:absolute;left:'+group.x.toFixed(1)+'px;top:'+group.y.toFixed(1)+'px;min-width:58px;width:auto;height:30px;transform:translate(-50%,-50%);border:2px solid white;border-radius:16px;box-shadow:0 2px 8px #111a;background:'+(best?'#f4a64a':'#737b82')+';pointer-events:auto;cursor:pointer;padding:2px 8px;color:#111;font-size:12px;font-weight:800;white-space:nowrap">'+esc(amount)+(count>1?' <span style="font-size:10px">· '+count+'</span>':'')+'</button>';}).join('');
      canvas._v9Clusters=clusters;
    };
    const setMode=mode=>{const map=mode==='map';if(zones)zones.style.display=map?'block':'none';if(summary)summary.style.display=map?'block':'none';if(results)results.style.display=map?'none':'';listButton?.classList.toggle('primary',!map);mapButton?.classList.toggle('primary',map);host.dataset.v9View=mode;if(map){if(!viewInitialized){fit();viewInitialized=true;}draw();}};
    const selectPoint=index=>{
      const row=points[index];if(!row||!selected)return;if((row.summaryOnly||!row.evaluation)&&Number.isInteger(row.mapPage)){if(row.mapPage!==(Number(area?.query?.stationOffset)||0)/(Number(area?.query?.stationLimit)||160)){area.navigateToPage?.(row.mapPage);return;}selected.style.display='block';selected.innerHTML='<b>'+esc(stationDisplayName(row.station))+'</b><div class="small">'+(row.station.hasRawOffer?'Tarif incalculable':'Prix non disponible')+' pour cette station.</div>';return;}
      const st=row.station,price=num(row.costPerKm);
      selected.style.display='block';
      const selectedPower=row.bestChoice?.row?.powerLine||row.powerLine;
      selected.innerHTML='<b>'+esc(stationDisplayName(st))+'</b><div class="small">'+esc(st.physicalOperator?.name||'Opérateur inconnu')+(selectedPower?' · '+esc(selectedPower.kind||'')+' '+esc(selectedPower.powerKw||'')+' kW':'')+'</div>'+renderTariffs(row.evaluation,row.bestChoice?.station||st,area?.displayFxRates,area?.selectedSubscriptions||[])+'<div class="small" style="margin-top:6px">'+(price==null?'Prix/km non disponible':esc(price.toLocaleString('fr-FR',{minimumFractionDigits:3,maximumFractionDigits:3})+' '+text(row.evaluation?.best?.targetCurrency||'EUR')+'/km'))+'</div><button type="button" class="secondary v9-map-open-row" style="width:auto;margin-top:8px">Voir la fiche dans la liste</button>';
      selected.querySelector('.v9-map-open-row')?.addEventListener('click',()=>{setMode('list');const card=[...(results?.querySelectorAll('.v9-result-card')||[])].find(item=>text(item.dataset.v9StationId)===text(st.id));card?.scrollIntoView?.({behavior:'smooth',block:'center'});});
      for(const marker of markers.querySelectorAll('.v9-map-marker'))marker.style.outline=canvas._v9Clusters?.[Number(marker.dataset.cluster)]?.indices.includes(index)?'3px solid #fff':'none';
    };
    markers?.addEventListener('click',event=>{const marker=event.target.closest('.v9-map-marker');if(!marker)return;event.stopPropagation();
      const indices=canvas._v9Clusters?.[Number(marker.dataset.cluster)]?.indices||[];
      if(indices.length===1){selectPoint(indices[0]);return;}
      selected.style.display='block';const choices=indices.slice().sort((a,b)=>{const pa=pricedBest(points[a].evaluation)?.total,pb=pricedBest(points[b].evaluation)?.total;return(pa==null?Infinity:pa)-(pb==null?Infinity:pb);}).slice(0,20);
      selected.innerHTML='<b>'+indices.length+' stations proches</b><div class="small">Zoomez pour séparer les stations ; les meilleures offres calculables sont présentées en premier.</div><div style="display:grid;gap:4px;margin-top:8px">'+choices.map(index=>'<button type="button" class="secondary v9-map-choice" data-index="'+index+'" style="width:100%;text-align:left">'+esc(stationDisplayName(points[index].station))+'</button>').join('')+'</div>'+(indices.length>20?'<button type="button" class="secondary v9-map-zoom-cluster">Zoomer sur ce groupe</button>':'');
      selected.querySelectorAll('.v9-map-choice').forEach(button=>button.addEventListener('click',()=>selectPoint(Number(button.dataset.index))));
      selected.querySelector('.v9-map-zoom-cluster')?.addEventListener('click',()=>{zoom=Math.min(18,zoom+2);draw();});
    });
    listButton?.addEventListener('click',()=>setMode('list'));mapButton?.addEventListener('click',()=>setMode('map'));
    host.querySelector('.v9-map-zoom-in')?.addEventListener('click',()=>{zoom=Math.min(18,zoom+1);draw();});host.querySelector('.v9-map-zoom-out')?.addEventListener('click',()=>{zoom=Math.max(2,zoom-1);draw();});
    canvas?.addEventListener('pointerdown',event=>{if(event.target.closest('button,a'))return;drag={x:event.clientX,y:event.clientY,center:project(center.lat,center.lon,zoom)};canvas.setPointerCapture?.(event.pointerId);});canvas?.addEventListener('pointermove',event=>{if(!drag)return;center=unproject(drag.center.x-(event.clientX-drag.x),drag.center.y-(event.clientY-drag.y),zoom);draw();});canvas?.addEventListener('pointerup',()=>{drag=null;});canvas?.addEventListener('pointercancel',()=>{drag=null;});
    canvas?.addEventListener('wheel',event=>{event.preventDefault();zoom=Math.max(2,Math.min(18,zoom+(event.deltaY<0?1:-1)));draw();},{passive:false});
    if(w.ResizeObserver&&canvas){new w.ResizeObserver(()=>{if(host.dataset.v9View==='map')draw();}).observe(canvas);}
    setMode('list');
  }
  function formatCurrencyAmount(value,currency){
    const amount=num(value);if(amount==null)return null;
    const code=text(currency||'EUR').toUpperCase();
    const formatted=amount.toLocaleString('fr-FR',{minimumFractionDigits:2,maximumFractionDigits:2});
    return code==='EUR'?formatted+' €':formatted+' '+code;
  }
  function offerPriceCategory(item){
    const provider=text(item?.provider).toLowerCase(),offerId=text(item?.offerId).toLowerCase(),kind=text(item?.kind).toLowerCase();
    if(text(item?.subscriptionId))return'subscription:'+text(item.subscriptionId);
    // Direct CPO tariffs stay in the Direct lane even when the operator name is Electra.
    if(kind!=='emsp'&&kind!=='roaming')return'direct';
    if(provider.includes('electroverse')||offerId.includes('electroverse'))return'electroverse';
    if(provider.includes('electra')||offerId.includes('electra'))return'electra';
    return null;
  }

  function displayAmount(item,fxRates={}){
    const local=text(item?.targetCurrency||'EUR').toUpperCase(),amount=num(item?.total);
    if(amount==null)return'Prix non disponible';
    const primary=formatCurrencyAmount(amount,local);
    if(local==='EUR')return primary;
    const rate=num(fxRates?.[local]),sourceCurrency=text(item?.currency).toUpperCase();
    const euro=rate>0?amount/rate:sourceCurrency==='EUR'?num(item?.result?.totalEur):null;
    return primary+(euro==null?' (conversion en € non disponible)':' (≈ '+formatCurrencyAmount(euro,'EUR')+')');
  }
  // A lane is evaluated independently. Distinct tariffs for a single EVSE/power
  // are not ranked against each other: their evidence is marked ambiguous.
  function evaluationLanes(evaluation){
    const lanes=new Map();
    for(const item of [evaluation?.best,...(evaluation?.alternatives||[]),...(evaluation?.incomplete||[])]){
      if(!item)continue;
      const category=offerPriceCategory(item);
      if(!lanes.has(category))lanes.set(category,[]);
      lanes.get(category).push(item);
    }
    return lanes;
  }
  function tariffLaneState(evaluation,station,category,laneOffers){
    const offers=laneOffers??evaluationLanes(evaluation).get(category)??[];
    if(!offers.length){
      if(!station?.unparsedOffers?.length)return{status:'missing',item:null,offers:[],diagnostics:[]};
      const evseIds=new Set((station?.evses||[]).map(evse=>text(evse.id)).filter(Boolean));
      const connectorIds=new Set((station?.evses||[]).flatMap(evse=>(evse.connectors||[]).map(c=>text(c.id))).filter(Boolean));
      const pending=(station?.unparsedOffers||[]).filter(raw=>{
        const lane=text(raw.channel).toLowerCase();
        const scope=raw.scope||{};
        return lane===category&&evseIds.has(text(scope.evseId))&&
          (!scope.connectorId||connectorIds.has(text(scope.connectorId)))&&raw.calculationStatus==='not_evaluated';
      }).map(raw=>({offerId:raw.id,provider:raw.channel,reason:'raw_candidate_not_evaluated'}));
      return pending.length?{status:'unresolved',item:null,offers:pending,
        diagnostics:pending.map(offer=>({offerId:offer.offerId,reason:offer.reason}))}
        :{status:'missing',item:null,offers:[],diagnostics:[]};
    }
    const sourceOffers=station?.offers||[];
    let localEvseIds;
    const diagnostics=offers.map(item=>({offerId:text(item.offerId),reason:text(item.result?.reason||item.incompletePricingReason||'')}));
    if(offers.some(item=>/ambig/i.test(text(item.result?.reason))||sourceOffers.some(offer=>{
      if(text(offer?.id||offer?.offerId)!==text(item.offerId)||offer?.metadata?.tariffAmbiguous!==true)return false;
      const conflicted=offer.metadata.ambiguousPdcIds;
      if(!Array.isArray(conflicted))return true;
      localEvseIds??=new Set((station?.evses||[]).flatMap(evse=>[text(evse.id),text(evse.evseId),...(evse.aliases||[]).map(text),...(evse.pdcIds||[]).map(text)]).filter(Boolean));
      return conflicted.some(id=>localEvseIds.has(text(id)));
    })))return{status:'ambiguous',item:null,offers,diagnostics};
    if(offers.length===1){
      const item=offers[0];
      return pricedItem(item)?{status:'priced',item,offers,diagnostics}:{status:'unresolved',item:null,offers,diagnostics};
    }
    const descriptions=new Set();
    for(const item of offers){
      const source=sourceOffers.find(offer=>text(offer?.id||offer?.offerId)===text(item.offerId));
      const unresolved=item.comparable===false||item.result?.complete===false||num(item.total)==null;
      const signature=JSON.stringify({
        currency:text(item.currency),total:unresolved?null:Math.round(Number(item.total)*1e6)/1e6,
        pricing:source?.pricing||item.result?.matchedRule||null,
        reason:unresolved?text(item.result?.reason||item.incompletePricingReason||'unresolved'):null
      });
      descriptions.add(signature);
    }
    if(descriptions.size>1)return{status:'ambiguous',item:null,offers,diagnostics};
    const priced=offers.find(pricedItem);
    if(priced)return{status:'priced',item:priced,offers,diagnostics};
    return{status:'unresolved',item:null,offers,diagnostics};
  }

  function congestionLaneKey(station,evaluation,category){
    const evseIds=(station?.evses||[]).flatMap(evse=>[text(evse.id),...(evse.connectors||[]).map(c=>text(c.id))]).filter(Boolean).sort();
    return JSON.stringify([text(station?.id||station?.canonicalId||station?.stationId),evseIds,text(evaluation?.chargingConnectorId),text(category)]);
  }
  function congestionAdjustedTotal(item,key){
    if(!item)return null;
    if(item.congestion?.available&&congestionSelections.get(key)===false)return num(item.congestion.totalWithoutCongestion);
    return num(item.total);
  }
  function bindCongestionToggles(w){
    if(w.__TCC_V9_CONGESTION_TOGGLE_BOUND__)return;
    w.__TCC_V9_CONGESTION_TOGGLE_BOUND__=true;
    w.document.addEventListener('click',event=>{
      const button=event.target?.closest?.('.v9-congestion-toggle');if(!button)return;
      const key=button.dataset.v9CongestionKey;
      if(!key)return;
      const currentlyIncluded=congestionSelections.get(key)!==false,newIncluded=!currentlyIncluded;
      congestionSelections.set(key,newIncluded);
      for(const row of w.document.querySelectorAll('.v9-tariff-row')){
        if(row.dataset.v9CongestionKey!==key)continue;
        row.dataset.v9EffectiveTotal=newIncluded?row.dataset.v9IncludedTotal:row.dataset.v9ExcludedTotal;
        const amount=row.querySelector('.v9-lane-amount');
        if(amount)amount.textContent=newIncluded?row.dataset.v9IncludedAmount:row.dataset.v9ExcludedAmount;
        const toggle=row.querySelector('.v9-congestion-toggle');
        if(toggle){toggle.setAttribute('aria-pressed',String(newIncluded));toggle.textContent=newIncluded?'Congestion incluse':'Congestion exclue';}
      }
      for(const host of w.document.querySelectorAll('.v9-tariffs')){
        const priced=[...host.querySelectorAll('.v9-tariff-row[data-v9-effective-total]')]
          .filter(el=>num(el.dataset.v9EffectiveTotal)!=null)
          .sort((a,b)=>num(a.dataset.v9EffectiveTotal)-num(b.dataset.v9EffectiveTotal));
        const best=priced[0]||null;
        for(const row of host.querySelectorAll('.v9-tariff-row')){
          const selected=row===best;
          row.classList.toggle('v9-best-tariff',selected);
          row.style.borderColor=selected?'#fff':'#343a42';
          row.style.boxShadow=selected?'0 0 0 2px #fff':'none';
          row.style.fontWeight=selected?'800':'normal';
          const heading=row.querySelector('.v9-lane-heading');
          if(heading)heading.textContent=row.dataset.v9LaneLabel+(selected?' · MEILLEUR TARIF':'');
        }
      }
    });
  }
  function feeBreakdown(components={},omitCongestion=false,depth=0){
    const rows=[];
    const add=(key,label,value)=>{
      const amount=num(value);
      if(amount!=null&&amount!==0)rows.push({key,label,amount});
    };
    const cost=value=>typeof value==='object'&&value!==null?
      (value.costEur??value.costGbp??value.totalEur):value;
    for(const [key,label] of [
      ['energy','Énergie'],['powerMinute','Charge selon la puissance délivrée'],['chargingTime','Temps de charge'],
      ['connectionFee','Frais fixes'],['sessionFee','Frais de session'],
      ['connectedTimePerMinute','Temps connecté'],['connectedTimeBlocks','Temps connecté par bloc'],
      ['connectedTimeAfterFree','Temps connecté après franchise'],
      ['connectedTimeInitialTier','Temps connecté par palier'],
      ['connectedTimeComponent','Forfait de connexion'],['parkingTime','Stationnement'],
      ['idleSupplement','Supplément après charge'],['postCharge','Frais après charge'],
      ['conditionalSessionFees','Frais conditionnels'],['afterMinutes','Frais après seuil']])add(key,label,cost(components[key]));
    if(!omitCongestion)add('congestionTime','Congestion',cost(components.congestionTime));
    add('minimumSession','Complément au minimum de session',components.minimumSession?.topUpEur);
    add('minimumTotal','Complément au minimum de facturation',components.minimumTotal?.topUpEur);
    if(components.energy==null)add('energyTimeline','Énergie',components.energyTimeline?.costEur);
    const supplements=new Set(['minimumSession','minimumTotal','postCharge','conditionalSessionFees','energyTimeline']);
    const hasRuleCharge=()=>rows.some(row=>!supplements.has(row.key));
    if(!hasRuleCharge()&&Array.isArray(components.componentGroups))
      components.componentGroups.forEach((group,index)=>{
        const nested=depth<3&&group?.components?feeBreakdown(group.components,omitCongestion,depth+1):[];
        const subtotal=nested.reduce((sum,row)=>sum+row.amount,0),groupTotal=num(group?.costEur);
        if(nested.length&&groupTotal!=null&&Math.abs(subtotal-groupTotal)<0.02)
          rows.push(...nested.map(row=>({...row,key:'componentGroup'+index+'.'+row.key,
            label:row.label+' (composante '+(index+1)+')'})));
        else add('componentGroup'+index,'Composante tarifaire '+(index+1),groupTotal);
      });
    if(!hasRuleCharge()&&depth<3&&Array.isArray(components.segmentedPricing?.segments)){
      const nested=components.segmentedPricing.segments.flatMap(segment=>
        segment?.components?feeBreakdown(segment.components,omitCongestion,depth+1):[]);
      const subtotal=nested.reduce((sum,row)=>sum+row.amount,0),expected=num(components.segmentedPricing.totalEur);
      if(nested.length&&expected!=null&&Math.abs(subtotal-expected)<0.02){
        const grouped=new Map();
        for(const row of nested){const key=row.key+'|'+row.label,prior=grouped.get(key);
          grouped.set(key,{...row,amount:(prior?.amount||0)+row.amount});}
        rows.push(...grouped.values());
      }
    }
    if(!hasRuleCharge())add('segmentedPricing','Tarif horaire',components.segmentedPricing?.totalEur);
    return rows;
  }
  function renderTariffs(evaluation,station,fxRates={},selectedSubscriptionIds=[]){
    const evaluated=[evaluation?.best,...(evaluation?.alternatives||[]),...(evaluation?.incomplete||[])].filter(Boolean);
    const subs=[...new Set((selectedSubscriptionIds||[]).map(text).filter(Boolean))];
    const subscriptionNames=new Map(evaluated.filter(item=>text(item.subscriptionId)).map(item=>[text(item.subscriptionId),text(item.provider)||text(item.subscriptionId)]));
    const categories=[
      {id:'direct',label:'Direct',color:'#f4a64a'},
      ...subs.map(id=>({id:'subscription:'+id,label:subscriptionNames.get(id)||id,color:'#f5d6a1',subscription:true})),
      {id:'electra',label:'Electra',color:'#74d7ec'},
      {id:'electroverse',label:'Electroverse',color:'#c9b3f4'}
    ];
    const states=new Map(categories.map(category=>[category.id,tariffLaneState(evaluation,station,category.id)]));
    const bestId=categories.filter(category=>states.get(category.id)?.status==='priced')
      .sort((a,b)=>congestionAdjustedTotal(states.get(a.id).item,congestionLaneKey(station,evaluation,a.id))-congestionAdjustedTotal(states.get(b.id).item,congestionLaneKey(station,evaluation,b.id)))[0]?.id||null;
    return'<div class="v9-tariffs" role="list" aria-label="Tarifs indépendants par borne et puissance" style="display:grid;gap:6px;margin-top:8px">'+categories.map(category=>{
      const state=states.get(category.id),item=state.item,best=category.id===bestId,key=congestionLaneKey(station,evaluation,category.id);
      const hasCongestion=state.status==='priced'&&item?.congestion?.available&&num(item?.congestion?.totalWithoutCongestion)!=null;
      const including=congestionSelections.get(key)!==false;
      const total=hasCongestion&&!including?item.congestion.totalWithoutCongestion:item?.total;
      const displayItem=hasCongestion&&!including?{...item,total,result:{...item.result,totalEur:item.congestion.sourceCurrencyTotalWithout}}:item;
      const calculated=value=>'Prix calculé · '+displayAmount(value,fxRates);
      const localEvses=new Set((station?.evses||[]).map(e=>text(e.id))),localConnectors=new Set((station?.evses||[]).flatMap(e=>(e.connectors||[]).map(c=>text(c.id))));
      const rawPending=state.status==='priced'?(station?.unparsedOffers||[]).filter(raw=>raw.calculationStatus==='not_evaluated'&&text(raw.channel).toLowerCase()===category.id&&localEvses.has(text(raw.scope?.evseId))&&(!raw.scope?.connectorId||localConnectors.has(text(raw.scope.connectorId)))):[];
      const amount=state.status==='priced'?calculated(displayItem)
        :state.status==='missing'?'Prix non disponible':'Tarif incalculable';
      const stateExplanation=state.status==='missing'?'Aucune offre exploitable trouvée pour cette voie tarifaire et ce PDC.':state.status!=='priced'?'Offre identifiée, mais les conditions ne permettent pas un calcul fiable.':'';
      const congestionAttr=hasCongestion?' data-v9-congestion-key="'+esc(key)+'" data-v9-included-total="'+esc(item.total)+'" data-v9-excluded-total="'+esc(item.congestion.totalWithoutCongestion)+'" data-v9-included-amount="'+esc(calculated(item))+'" data-v9-excluded-amount="'+esc(calculated({...item,total:item.congestion.totalWithoutCongestion,result:{...item.result,totalEur:item.congestion.sourceCurrencyTotalWithout}}))+'"':'';
      const totalAttr=state.status==='priced'&&num(total)!=null?' data-v9-effective-total="'+esc(total)+'"':'';
      const names=[...new Set(state.offers.map(offer=>text(offer.provider)).filter(Boolean))];
      const detail=item&&station?.offers?.find(offer=>text(offer?.id||offer?.offerId)===text(item.offerId));
      const rateLabels=detail?appliedTariffRateLabels(item,detail):[];
      const label=names.join(', ')+(state.status==='priced'&&rateLabels.length?' · '+rateLabels.join(' · '):'');
      const fullLabels=detail?tariffRateLabels(detail):[];
      const source=text(detail?.metadata?.source||detail?.source||detail?.sourceId);
      const sourceDate=text(detail?.metadata?.fetchedAt||detail?.metadata?.validatedAt||detail?.metadata?.collectedAt||detail?.generatedAt);
      const billed=item?.result?.components||{};
      const feeRows=state.status==='priced'&&item?.result?.complete===true?
        feeBreakdown(billed,hasCongestion&&!including)
          .map(row=>'<div>'+esc(row.label)+' : '+esc(formatCurrencyAmount(row.amount,item.currency||detail?.currency||'EUR'))+'</div>').join(''):'';
      const preauthorisation=billed.guestPreAuthorisation;
      const preauthorisationAmount=preauthorisation?.includedInTotal===false?
        num(preauthorisation.amountGbp??preauthorisation.amountEur):null;
      const preauthorisationRow=state.status==='priced'&&preauthorisationAmount!=null?
        '<div>Préautorisation non facturée : '+esc(formatCurrencyAmount(preauthorisationAmount,
          preauthorisation.amountGbp!=null?'GBP':'EUR'))+'</div>':'';
      const history=detail?'<details class="v9-tariff-detail" style="grid-column:1/-1;font-size:12px"><summary>Détail du tarif · '+esc(category.label)+'</summary>'+
        (fullLabels.length?'<div>Grilles et conditions : '+esc(fullLabels.join(' · '))+'</div>':'')+
        feeRows+preauthorisationRow+
        (billed.powerMinute?.estimatedFromChargeCurve?'<div>Estimation selon la courbe de charge du véhicule ; la puissance réellement délivrée peut varier.</div>':'')+
        (source?'<div>Source : '+esc(source)+'</div>':'')+(sourceDate?'<div>Date : '+esc(sourceDate)+'</div>':'')+
        '<div>Offre : '+esc(detail.id||item?.offerId||'')+'</div></details>':'';
      return'<div class="v9-tariff-row'+(best?' v9-best-tariff':'')+'" role="listitem" data-v9-lane-label="'+esc(category.label)+'" data-v9-tariff-state="'+esc(state.status)+'"'+totalAttr+congestionAttr+' style="display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:3px 10px;padding:8px 10px;border:1px solid '+(best?'#fff':'#343a42')+';border-radius:8px;background:'+category.color+';color:#15171b;min-width:0;'+(best?'font-weight:800;box-shadow:0 0 0 2px #fff':'')+'">'+
        '<strong class="v9-lane-heading" style="font-size:14px;line-height:1.3">'+esc(category.label)+(best?' · MEILLEUR TARIF':'')+'</strong>'+
        '<span style="font-size:15px;line-height:1.3;text-align:right"><span class="v9-lane-amount">'+esc(amount)+'</span></span>'+
        (hasCongestion?'<button type="button" class="v9-congestion-toggle" data-v9-congestion-key="'+esc(key)+'" aria-pressed="'+String(including)+'" title="Basculer les frais de congestion pour cette offre seulement" style="grid-column:1/-1;justify-self:end;background:#fff;color:#15171b;border:1px solid #555;border-radius:6px;padding:4px 8px;min-height:32px;font-size:12px;width:auto;cursor:pointer">'+(including?'Congestion incluse':'Congestion exclue')+'</button>':'')+
        (hasCongestion?'<span style="grid-column:1/-1;font-size:11px;line-height:1.3">À partir de '+esc(item.congestion.thresholdSoc)+' % de batterie'+(item.congestion.thresholdSource==='default_soc80'?' (hypothèse V9)':' (source)')+' · '+esc(num(item.congestion.minutes)?.toFixed(1)||'—')+' min au-delà du seuil</span>':'')+
        (label?'<span style="grid-column:1/-1;font-size:12px;line-height:1.3;opacity:.8;overflow-wrap:anywhere">'+esc(label)+(category.subscription?' · abonnement':'')+'</span>':'')+
        (stateExplanation?'<span class="v9-tariff-explanation" style="grid-column:1/-1;font-size:12px;line-height:1.4">'+esc(stateExplanation)+'</span>':'')+
        (rawPending.length?'<span class="v9-raw-offers-notice" style="grid-column:1/-1;font-size:12px;line-height:1.4">Tarif incalculable · '+rawPending.length+' autre(s) offre(s) brute(s) conservée(s) pour ce PDC, sans montant simulé.</span>':'')+
        history+
      '</div>';
    }).join('')+'</div>';
  }
  function isTeslaStation(station){
    const operator=text(station?.physicalOperator?.name||station?.operator?.name||station?.operatorName).toLowerCase();
    const provenance=(station?.provenance||station?.sources||[]).map(item=>text(item?.sourceId||item?.id||item)).filter(Boolean);
    return operator.includes('tesla')||provenance.some(id=>/tesla|suc-tracker/i.test(id));
  }
  function stationBaseSource(station){
    const operator=text(station?.physicalOperator?.name||station?.operator?.name||station?.operatorName).toLowerCase();
    const provenance=(station?.provenance||station?.sources||[]).map(item=>text(item?.sourceId||item?.id||item)).filter(Boolean);
    if(isTeslaStation(station))return text(station?.countryCode).toUpperCase()==='MA'?'TESLA · export Mac':'TESLA · SuC Tracker';
    const labels={'france-national':'IRVE','spain-reve':'REVE','italy-pun':'PUN','switzerland-national':'Base nationale CH','germany-production-snapshot':'Base nationale DE','uk-production-open-feeds':'Open data UK','netherlands-dotnl-national':'DOT-NL','belgium-nap-national':'NAP Belgique','morocco-evgo-native':'EVgo MA','morocco-fastvolt-public':'FastVolt MA','morocco-kilowatt-public':'Kilowatt MA','morocco-totalenergies-hosts':'TotalEnergies MA'};
    const canonicalLabels={'FR:ionity_direct':'IONITY Direct · FR','GB:ionity_direct':'IONITY Direct · UK','IT:ionity_direct':'IONITY Direct · IT','DE:ionity_direct':'IONITY Direct · DE','FR:belib_stations':'Belib · FR','IT:atlante_direct':'Atlante Direct · IT','CH:swiss_integration':'Base intégrée CH'};
    const found=provenance.map(id=>labels[id]||canonicalLabels[id]||canonicalLabels[id.replace(/^prepared:/,'')]).filter(Boolean);
    if(found.length)return[...new Set(found)].join(' · ');
    const canonical=provenance.map(id=>id.replace(/^prepared:/,'')).filter(id=>/^[A-Z]{2}:[a-z0-9_]+$/.test(id));
    if(canonical.length)return[...new Set(canonical)].join(' · ');
    const byCountry={FR:'IRVE',ES:'REVE',IT:'PUN',CH:'Base nationale CH',DE:'Base nationale DE',GB:'Open data UK',MA:'Base CPO Maroc',NL:'DOT-NL',BE:'NAP Belgique'};
    return byCountry[text(station?.countryCode).toUpperCase()]||'Source nationale';
  }
  function renderCostPerKm(row){
    const evaluation=row?.evaluation,best=pricedBest(evaluation),cost=num(best?.costPerRecoveredKm),km=num(evaluation?.recoveredKm??row?.recoveredKm);
    if(cost==null)return'<div class="small warn">Coût au km récupéré : non calculable</div>';
    return'<div class="small">Coût au km récupéré : <b>'+cost.toLocaleString('fr-FR',{minimumFractionDigits:3,maximumFractionDigits:3})+' '+esc(best?.targetCurrency||'EUR')+'/km</b>'+(km!=null?' · '+km.toFixed(1)+' km récupérés':'')+'</div>';
  }

  function offerAppliesToEvseGroup(offer,evseTokens,connectorIds){
    const evseIds=(offer?.evseIds||[]).map(text).filter(Boolean),offerConnectorIds=(offer?.connectorIds||[]).map(text).filter(Boolean);
    if(evseIds.length&&![...evseTokens||[]].some(id=>evseIds.includes(text(id))))return false;
    if(offerConnectorIds.length&&![...connectorIds||[]].some(id=>offerConnectorIds.includes(text(id))))return false;
    return true;
  }
  function electraPlusOffers(station,selected=[]){
    if(text(station?.countryCode).toUpperCase()!=='FR'||
       ![text(station?.physicalOperator?.id),text(station?.physicalOperator?.name)].some(value=>value.toLowerCase()==='electra'))return[];
    const bases=(station.offers||[]).filter(offer=>text(offer.id).startsWith('electra-direct-exact:')&&
      text(offer.kind)==='direct'&&text(offer.currency).toUpperCase()==='EUR'&&
      offer.metadata?.verified===true&&!offer.metadata?.tariffAmbiguous&&!offer.metadata?.incompletePricingReason);
    if(bases.length!==1)return[]; // A station-level choice between tariffs has no EVSE attribution.
    const base=bases[0],groups=base.pricing?.componentGroups;
    if(!Array.isArray(groups)||!groups.length)return[];
    return ELECTRA_PLUS_PLANS.filter(plan=>selected.includes(plan.id)).flatMap(plan=>{
      const pricing=JSON.parse(JSON.stringify(base.pricing));let energyRules=0;
      for(const group of pricing.componentGroups){
        if(!Array.isArray(group.rules)||!group.rules.length)return[];
        for(const rule of group.rules){
          const price=num(rule.pricePerKwh);
          if(price==null)continue; // Other OCPI elements (for example congestion) keep their original rate.
          if(price<plan.discountPerKwhEur)return[];
          rule.pricePerKwh=Math.round((price-plan.discountPerKwhEur)*1e6)/1e6;
          energyRules++;
        }
      }
      if(!energyRules)return[];
      return[{...base,id:base.id+':'+plan.id,kind:'subscription',subscriptionId:plan.id,
        pricing,metadata:{...base.metadata,source:'Electra+ official France terms',
          sourceUrl:'https://www.go-electra.com/fr/electra-plus/',baseOfferId:base.id,
          discountPerKwhEur:plan.discountPerKwhEur,monthlyFeeEur:plan.monthlyFeeEur,
          validationDate:'2026-10-13'}}];
    });
  }

  // Never rank a contradictory tariff as though it were a verified best price.
  // Keep its evidence in the alternatives so its own lane still says ambiguous.
  function consistentLaneEvaluation(evaluation,station,selectedSubscriptions=[]){
    if(!evaluation)return evaluation;
    const all=[evaluation.best,...(evaluation.alternatives||[])].filter(Boolean);
    const lanes=['direct',...(selectedSubscriptions||[]).map(id=>'subscription:'+text(id)),'electra','electroverse'];
    const grouped=evaluationLanes(evaluation);
    const valid=lanes.filter(lane=>grouped.get(lane)?.some(pricedItem))
      .map(lane=>tariffLaneState(evaluation,station,lane,grouped.get(lane)))
      .filter(state=>state.status==='priced'&&state.item).map(state=>state.item)
      .sort((a,b)=>Number(a.total)-Number(b.total));
    const best=valid[0]||null;
    return{...evaluation,best,alternatives:all.filter(item=>item!==best)};
  }
  function variantsByPower(w,rows,session,selectedSubscriptions=[]){
    const planner=w.TCCV9SessionPlannerEngine,sessionEngine=w.TCCV9SessionEngine,scoreEngine=w.TCCV9StationScoreEngine;
    if(!planner?.planStation||!sessionEngine?.evaluateStation||!sessionEngine?.offerMatchesChargingKind||!scoreEngine?.scoreStation)throw new Error('per-power pricing engines unavailable');
    const variants=[];
    for(const row of rows||[]){
      const station=row?.station||{},groups=new Map(),unknownEvses=new Map(),unknownConnectorIds=new Set();
      for(const [evseIndex,evse] of (station.evses||[]).entries()){
        if(!(evse.connectors||[]).length)unknownEvses.set(evseIndex,[]);
        for(const [connectorIndex,raw] of (evse.connectors||[]).entries()){
        const power=num(raw.powerKw??raw.power??evse.powerKw);
        if(power==null||power<=0){
          const previous=unknownEvses.get(evseIndex)||[];previous.push(raw);unknownEvses.set(evseIndex,previous);
          if(raw.id||raw.connectorId)unknownConnectorIds.add(text(raw.id||raw.connectorId));
          continue;
        }
        const connector={...raw,powerKw:power},kind=connectorKind(connector),connectorId=text(connector.id||connector.connectorId)||null,plug=text(connector.plugName||connector.type||connector.plugType)||null;
        const evseKey=text(evse.id||evse.evseId)||'evse-'+evseIndex,evseTokens=new Set([evseKey,text(evse.evseId),...(evse.aliases||[]).map(text),...(evse.pdcIds||[]).map(text)].filter(Boolean)),connectorTokens=new Set(connectorId?[connectorId]:[]);
        const matching=(station.offers||[]).filter(offer=>offerAppliesToEvseGroup(offer,evseTokens,connectorTokens)&&sessionEngine.offerMatchesChargingKind(offer,kind,power,plug,connectorId,[...evseTokens])).map(offer=>text(offer.id||offer.offerId)||JSON.stringify(offer)).sort();
        const key=[kind,floorPower(power),matching.join(',')].join('|');
        const group=groups.get(key)||{kind,powerKw:floorPower(power),offerIds:matching,evseConnectors:new Map(),evseKeys:new Set(),evseTokens:new Set(),connectorIds:new Set()};
        const connectors=group.evseConnectors.get(evseIndex)||[];
        connectors.push({connectorIndex,connector});group.evseConnectors.set(evseIndex,connectors);group.evseKeys.add(evseKey);
        evseTokens.forEach(id=>group.evseTokens.add(id));connectorTokens.forEach(id=>group.connectorIds.add(id));groups.set(key,group);
        }
      }
      for(const group of groups.values()){
        const evses=[];
        for(const [evseIndex,connectors] of group.evseConnectors){
          const original=station.evses[evseIndex];
          evses.push({...original,connectors:connectors.map(item=>item.connector)});
        }
        const scopedOffers=(station.offers||[]).filter(offer=>offerAppliesToEvseGroup(offer,group.evseTokens,group.connectorIds));
        const guardedOffers=guardUnverifiedPowerOffers(station,group.kind,group.powerKw,scopedOffers);
        const unparsedOffers=(station.unparsedOffers||[]).filter(offer=>group.evseKeys.has(text(offer.scope?.evseId))&&
          (offer.scope?.connectorId==null||group.connectorIds.has(text(offer.scope.connectorId))));
        const variant={...station,evses,offers:guardedOffers.concat(electraPlusOffers({...station,offers:guardedOffers},selectedSubscriptions)),unparsedOffers},routeMap={[text(station.id||station.canonicalId||station.stationId)]:row.route||{}};
        const plan=planner.planStation(variant,session,{route:{byStationId:routeMap}});
        const rawEvaluation=sessionEngine.evaluateStation(variant,plan.effectiveSession,{selectedSubscriptions,targetCurrency:session.targetCurrency||'EUR',fxRates:session.fxRates||{}});
        const evaluation=consistentLaneEvaluation(rawEvaluation,variant,selectedSubscriptions);
        const score=scoreEngine.scoreStation(variant,evaluation,plan.effectiveSession,{route:{byStationId:routeMap},plan});
        const line={kind:group.kind,powerKw:group.powerKw,count:group.evseKeys.size};
        variants.push({...row,station:variant,powerLine:line,plan,evaluation,score,total:num(pricedBest(evaluation)?.total),costPerKm:num(pricedBest(evaluation)?.costPerRecoveredKm),recoveredKm:num(evaluation?.recoveredKm),displayKey:[text(station.name),line.kind,line.powerKw,group.offerIds.join(',')].join('|')});
      }
      if(!groups.size&&!unknownEvses.size){
        variants.push({...row,powerLine:{kind:'UNKNOWN',powerKw:null,count:0},evaluation:null,total:null,costPerKm:null});
      }
      if(unknownEvses.size){
        const evses=[...unknownEvses].map(([index,connectors])=>({...station.evses[index],connectors}));
        const evseIds=new Set(evses.map(evse=>text(evse.id||evse.evseId)));
        const unparsedOffers=(station.unparsedOffers||[]).filter(offer=>evseIds.has(text(offer.scope?.evseId))&&
          (offer.scope?.connectorId==null||unknownConnectorIds.has(text(offer.scope.connectorId))));
        variants.push({...row,station:{...station,evses,offers:[],unparsedOffers},
          powerLine:{kind:'UNKNOWN',powerKw:null,count:evseIds.size},evaluation:null,total:null,costPerKm:null,
          displayKey:[text(station.name),'UNKNOWN'].join('|')});
      }
    }
    return variants;
  }

  function siteKey(st,power){
    const normalize=value=>text(value).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,' ').trim();
    const latitude=num(st?.latitude),longitude=num(st?.longitude);
    const place=isTeslaStation(st)&&latitude!=null&&longitude!=null
      ?'tesla-site|'+latitude.toFixed(3)+'|'+longitude.toFixed(3)
      :(normalize(st?.address)||normalize(st?.name))+'|'+latitude?.toFixed(3)+'|'+longitude?.toFixed(3);
    return [text(st?.countryCode),normalize(st?.physicalOperator?.name),place,power].join('|');
  }
  function powerBuckets(st){
    const buckets=new Map();
    for(const evse of st?.evses||[]){
      const pdcs=(evse?.pdcIds||[]).map(text).filter(Boolean);
      const identity=text(evse?.aliases?.[0]||evse?.id);
      const count=Math.max(1,Math.floor(num(evse?.stalls)||1));
      const ids=pdcs.length?pdcs:Array.from({length:count},(_,index)=>`${identity}:${index}`);
      for(const connector of evse?.connectors||[]){
        const power=floorPower(connector?.powerKw);
        if(power==null||power<=0)continue;
        if(!buckets.has(power))buckets.set(power,new Set());
        for(const id of ids)buckets.get(power).add(id);
      }
    }
    if(!buckets.size)buckets.set(0,new Set());
    return buckets;
  }
  function energyOnlyEvaluation(row,power){
    const evaluations=[row.evaluation?.best,...(row.evaluation?.alternatives||[])].filter(Boolean);
    const connectors=(row.station?.evses||[]).flatMap(evse=>evse.connectors||[]).filter(connector=>floorPower(connector.powerKw)===power);
    for(const evaluated of evaluations){
      if(!pricedItem(evaluated))continue;
      const offer=(row.station?.offers||[]).find(offer=>text(offer.id)===text(evaluated.offerId)&&offer.metadata?.energyOnly===true);
      if(!offer)continue;
      const kinds=(offer.connectorKinds||[]).map(kind=>text(kind).toUpperCase());
      const eligible=connectors.some(connector=>{
        const kind=text(connector.kind).toUpperCase(),value=num(connector.powerKw);
        return (!kinds.length||kinds.includes(kind))&&(num(offer.minPowerKw)==null||floorPower(value)>=floorPower(offer.minPowerKw))&&(num(offer.maxPowerKw)==null||floorPower(value)<=floorPower(offer.maxPowerKw));
      });
      if(eligible)return{...row.evaluation,best:evaluated,alternatives:[],incomplete:[]};
    }
    return null;
  }
  function stationAtPower(station,power){
    const evses=(station?.evses||[]).map(evse=>({...evse,connectors:(evse.connectors||[]).filter(connector=>floorPower(connector.powerKw)===power)})).filter(evse=>evse.connectors.length);
    return {...station,evses};
  }
  function evaluatePower(row,power,context){
    const station=stationAtPower(row.station,power),engine=context.engine,area=context.area;
    const session=area?.effectiveSession,route=area?.routes;
    if(!station.evses.length||!session||!engine?.planStation||!engine?.evaluateStation)return null;
    const plan=engine.planStation(station,session,{route});
    const evaluation=engine.evaluateStation(station,plan.effectiveSession||session,{
      selectedSubscriptions:context.selectedSubscriptions||[],targetCurrency:session.targetCurrency||'EUR',fxRates:session.fxRates||{}
    });
    const score=engine.scoreStation?.(station,evaluation,plan.effectiveSession||session,{route,plan})||row.score;
    return{...row,station,plan,evaluation,score,total:num(pricedBest(evaluation)?.total),costPerKm:num(pricedBest(evaluation)?.costPerRecoveredKm),distanceKm:num(score?.distanceKm??row.distanceKm)};
  }
  function combinedEvaluation(group){
    const selected=group.evaluation;
    const all=group.evaluations.flatMap(evaluation=>[evaluation?.best,...(evaluation?.alternatives||[]),...(evaluation?.incomplete||[])]).filter(Boolean);
    const unique=new Map();
    for(const offer of all){
      const key=[text(offer.provider),text(offer.kind),text(offer.subscriptionId),Number.isFinite(offer.total)?Number(offer.total).toFixed(6):text(offer.result?.reason)].join('|');
      if(!unique.has(key))unique.set(key,offer);
    }
    const values=[...unique.values()];
    const best=pricedBest(selected);
    const bestKey=best&&[text(best.provider),text(best.kind),text(best.subscriptionId),Number.isFinite(best.total)?Number(best.total).toFixed(6):text(best.result?.reason)].join('|');
    return{...(selected||{}),best,alternatives:values.filter(offer=>pricedItem(offer)&&[text(offer.provider),text(offer.kind),text(offer.subscriptionId),Number.isFinite(offer.total)?Number(offer.total).toFixed(6):text(offer.result?.reason)].join('|')!==bestKey),incomplete:values.filter(offer=>!pricedItem(offer))};
  }

  function tariffGroupSignature(row){
    if(isTeslaStation(row?.station))return'tesla-identity';
    const evaluation=row?.evaluation;
    if(!evaluation)return'non-disponible';
    const entries=[evaluation.best,...(evaluation.alternatives||[]),...(evaluation.incomplete||[])].filter(Boolean);
    if(!entries.length)return'non-disponible';
    return entries.map(item=>{
      const source=(row.station?.offers||[]).find(offer=>text(offer?.id||offer?.offerId)===text(item.offerId));
      return JSON.stringify([offerPriceCategory(item),text(item.provider),text(item.subscriptionId),num(item.total),
        item.comparable===false?text(item.result?.reason||item.incompletePricingReason):'',
        source?.pricing||item.result?.matchedRule||null]);
    }).sort().join('||');
  }
  function groupRows(rows,context){
    const groups=new Map();
    for(const row of rows||[]){
      for(const [power,ids] of powerBuckets(row.station)){
        const key=siteKey(row.station,power)+'|'+connectorKind((row.station?.evses||[]).flatMap(evse=>evse.connectors||[]).find(connector=>floorPower(connector.powerKw)===power)||{})+'|'+tariffGroupSignature(row),selectedConnector=text(row.evaluation?.chargingConnectorId);
        const matchingConnector=selectedConnector&&(row.station?.evses||[]).some(evse=>(evse.connectors||[]).some(connector=>text(connector.id)===selectedConnector&&floorPower(connector.powerKw)===power));
        const scoped=context?evaluatePower(row,power,context):null;
        const evaluated=matchingConnector||(!selectedConnector&&power===floorPower(maxPower(row.station)));
        const evaluation=scoped?.evaluation||(evaluated?row.evaluation:energyOnlyEvaluation(row,power));
        const candidate={...(scoped||row),displayPowerKw:power,evaluation,total:num(pricedBest(evaluation)?.total),costPerKm:num(pricedBest(evaluation)?.costPerRecoveredKm)};
        let group=groups.get(key);
        if(!group){group={...candidate,pointIds:new Set(),pointCount:0,groupedStationCount:0,evaluations:[]};groups.set(key,group);}
        if(evaluation)group.evaluations.push(evaluation);
        group.groupedStationCount++;
        if(isTeslaStation(row.station))group.pointCount=Math.max(group.pointCount,ids.size||1);
        else if(ids.size){for(const id of ids)group.pointIds.add(id);}else group.pointCount++;
        if((Number.isFinite(candidate.total)&&(!Number.isFinite(group.total)||candidate.total<group.total))||(!Number.isFinite(group.total)&&candidate.distanceKm<group.distanceKm))Object.assign(group,{station:candidate.station,evaluation:candidate.evaluation,score:candidate.score,route:candidate.route,total:candidate.total,distanceKm:candidate.distanceKm,distanceEstimated:candidate.distanceEstimated});
      }
    }
    return [...groups.values()].map(group=>{group.pointCount+=group.pointIds.size;delete group.pointIds;group.evaluation=combinedEvaluation(group);delete group.evaluations;return group;});
  }

  // A presentation card uses the canonical station identity. Pricing stays on
  // the already evaluated connector/offer variants, never on a merged station.
  function pdcEntries(row){
    const entries=new Map();
    for(const [index,evse] of (row?.station?.evses||[]).entries()){
      const evseId=text(evse?.id||evse?.evseId)||'EVSE '+(index+1);
      const exactIds=(evse?.pdcIds?.length?evse.pdcIds:(evse?.officialEvseId?[evse.officialEvseId]:[])).map(text).filter(Boolean);
      const count=exactIds.length||Math.max(1,Math.floor(num(evse?.stalls)||1));
      const ids=exactIds.length?exactIds:Array.from({length:count},(_,slot)=>evseId+':slot:'+slot);
      for(const [slot,id] of ids.entries()){
        const entry=entries.get(id)||{id,label:exactIds.length?id:'PDC '+(slot+1)+' · identifiant individuel non fourni',evses:[]};
        if(!entry.evses.includes(evse))entry.evses.push(evse);
        entries.set(id,entry);
      }
    }
    return [...entries.values()];
  }
  function cardLanes(subscriptions=[]){return['direct',...(subscriptions||[]).map(id=>'subscription:'+text(id)),'electra','electroverse'];}
  function stationCards(variants,subscriptions=[],summaryOnly=false){
    const cards=new Map(),lanes=cardLanes(subscriptions);
    for(const [index,row] of (variants||[]).entries()){
      const station=row?.station||{},id=text(station.id||station.canonicalId||station.stationId);
      // A missing identifier must never merge two stations by name or location.
      const key=id?text(station.countryCode)+'|'+id:'unidentified:'+index;
      let card=cards.get(key);
      if(!card){card={station,stationKey:key,variants:[],powerGroups:[],pdcIds:new Set(),bestChoice:null,rankingChoices:[],
        evaluation:null,total:null,costPerKm:null,score:row.score,route:row.route,
        distanceKm:row.distanceKm,distanceEstimated:row.distanceEstimated};cards.set(key,card);}
      // Keep the station-wide view independent from the selected cheapest PDC.
      // Input variants contain only the EVSE/connector subset evaluated upstream.
      if(!summaryOnly&&card.variants.length){
        const evses=new Map((card.station.evses||[]).map(evse=>[text(evse.id||evse.evseId),evse]));
        for(const evse of station.evses||[]){
          const id=text(evse.id||evse.evseId);
          if(!evses.has(id)){evses.set(id,evse);continue;}
          const previous=evses.get(id);
          const connectors=new Map((previous.connectors||[]).map(connector=>[
            text(connector.id||connector.connectorId)||[text(connector.kind),text(connector.powerKw)].join('|'),connector]));
          for(const connector of evse.connectors||[]){
            const connectorId=text(connector.id||connector.connectorId)||[text(connector.kind),text(connector.powerKw)].join('|');
            if(!connectors.has(connectorId))connectors.set(connectorId,connector);
          }
          evses.set(id,{...previous,connectors:[...connectors.values()]});
        }
        card.station={...card.station,evses:[...evses.values()]};
      }
      const grouped=evaluationLanes(row.evaluation);
      // A lane can be priced only if it contains a priced candidate. Keep all
      // candidates in that lane for the per-PDC ambiguity and scope checks.
      const rankable=lanes.filter(lane=>grouped.get(lane)?.some(pricedItem));
      if(summaryOnly&&!rankable.length)continue;
      const entries=pdcEntries(row);
      let group;
      if(!summaryOnly){
        card.variants.push(row);
        const kind=text(row.powerLine?.kind||connectorKind((station.evses||[]).flatMap(evse=>evse.connectors||[])[0]||{})).toUpperCase();
        const power=num(row.powerLine?.powerKw??row.displayPowerKw);
        const groupKey=kind+'|'+String(power);
        group=card.powerGroups.find(item=>item.key===groupKey);
        if(!group){group={key:groupKey,kind,powerKw:power,variants:[],pdcIds:new Set()};card.powerGroups.push(group);}
        group.variants.push({...row,pdcEntries:entries});
      }
      for(const pdc of entries){
        if(group){card.pdcIds.add(pdc.id);group.pdcIds.add(pdc.id);}
        const scoped={...station,evses:pdc.evses};
        for(const lane of rankable){
          const state=tariffLaneState(row.evaluation,scoped,lane,grouped.get(lane));
          if(state.status!=='priced'||!pricedItem(state.item))continue;
          const total=state.item.congestion?.available?congestionAdjustedTotal(state.item,congestionLaneKey(scoped,row.evaluation,lane)):num(state.item.total);
          if(total==null)continue;
          const costPerKm=num(state.item.costPerRecoveredKm);
          card.rankingChoices.push(summaryOnly?{costPerKm,score:row.score}:{row,pdc,lane,total,costPerKm,score:row.score});
          if(!card.bestChoice||total<card.bestChoice.total){
            card.bestChoice={row,pdc,station:scoped,item:state.item,lane,total};
            card.evaluation={...row.evaluation,best:state.item};
            card.total=total;card.costPerKm=num(state.item.costPerRecoveredKm);
            card.score=row.score;card.route=row.route;card.distanceKm=row.distanceKm;
            card.distanceEstimated=row.distanceEstimated;
          }
        }
      }
    }
    if(summaryOnly)return [...cards.values()];
    return [...cards.values()].map(card=>{
      card.pointCount=card.pdcIds.size;
      card.powerGroups.sort((a,b)=>a.kind.localeCompare(b.kind)||a.powerKw-b.powerKw);
      delete card.pdcIds;
      for(const group of card.powerGroups){group.pointCount=group.pdcIds.size;delete group.pdcIds;}
      return card;
    });
  }

  function powerLaneSummary(group,lane,fxRates){
    const states=group.variants.flatMap(row=>row.pdcEntries.map(pdc=>
      tariffLaneState(row.evaluation,{...row.station,evses:pdc.evses},lane)));
    if(!states.length||states.every(state=>state.status==='missing'))return'Prix non disponible';
    if(states.every(state=>state.status==='priced')){
      const signatures=new Set(states.map(state=>JSON.stringify([text(state.item.offerId),text(state.item.currency),num(state.item.total)])));
      if(signatures.size===1)return'Prix calculé · '+displayAmount(states[0].item,fxRates);
    }
    if(states.every(state=>state.status==='ambiguous'||state.status==='unresolved'))return'Tarif incalculable';
    return'Tarifs selon PDC · voir détails';
  }
  function evseIdentityLabels(evses){
    const unique=values=>[...new Set(values.map(text).filter(Boolean))];
    const official=unique(evses.map(evse=>evse.officialEvseId));
    const source=unique(evses.filter(evse=>!text(evse.officialEvseId)).map(evse=>evse.sourceEvseId));
    const internal=unique(evses.filter(evse=>!text(evse.officialEvseId)&&!text(evse.sourceEvseId))
      .map(evse=>evse.id));
    return [official.length?'EVSE_ID officiel : '+official.join(', '):null,
      source.length?'Identifiant EVSE source : '+source.join(', '):null,
      internal.length?'Clé interne : '+internal.join(', '):null].filter(Boolean).join(' · ')||
      'Identifiant EVSE non fourni';
  }
  function renderStationCard(card,index,area){
    const station=card.station,best=card.bestChoice,fx=area?.displayFxRates||{},subs=area?.selectedSubscriptions||[];
    const laneNames={direct:'Direct',electra:'Electra',electroverse:'Electroverse'};
    const bestLabel=best?(laneNames[best.lane]||best.lane)+' · '+displayAmount({...best.item,total:best.total},fx)+' · '+best.row.powerLine?.powerKw+' kW '+best.row.powerLine?.kind:
      card.variants.some(row=>(row.station?.unparsedOffers||[]).some(offer=>offer.calculationStatus==='not_evaluated')||
        [row.evaluation?.best,...(row.evaluation?.alternatives||[]),...(row.evaluation?.incomplete||[])].some(Boolean))?'Tarif incalculable':'Prix non disponible';
    const powerHtml=card.powerGroups.map(group=>{
      const lanes=[['direct','Direct','#f4a64a'],['electra','Electra','#74d7ec'],['electroverse','Electroverse','#c9b3f4']];
      const summary='<span class="v9-power-lane-grid">'+lanes.map(([id,label,color])=>
        '<span class="v9-power-lane" style="border-color:'+color+'"><b>'+label+'</b><small>'+esc(powerLaneSummary(group,id,fx))+'</small></span>').join('')+'</span>';
      const byPdc=new Map();
      for(const row of group.variants)for(const pdc of row.pdcEntries){
        const variants=byPdc.get(pdc.id)||[];variants.push({row,pdc});byPdc.set(pdc.id,variants);
      }
      const pdcs=[...byPdc.values()].map(variants=>{
        const pdc=variants[0].pdc,allEvses=variants.flatMap(item=>item.pdc.evses);
        const connectors=[...new Set(allEvses.flatMap(evse=>(evse.connectors||[]).map(connector=>
          [text(connector.plugName||connector.type||connector.standard||connector.plugType||connector.kind||'Prise'),
            num(connector.powerKw)!=null?connector.powerKw+' kW':''].filter(Boolean).join(' · '))))];
        const evseIdentity=evseIdentityLabels(allEvses);
        const status=allEvses.map(evse=>text(evse.status?.state||evse.status?.value||
          (typeof evse.status==='string'?evse.status:null)||variants[0].row.station.status?.state)).filter(Boolean);
        const source=text(allEvses[0]?.sourceId||allEvses[0]?.provenance?.sourceId)||stationBaseSource(variants[0].row.station);
        const tariffs=variants.map(({row,pdc})=>{
          const scoped={...row.station,evses:pdc.evses};
          const plug=[...new Set(pdc.evses.flatMap(evse=>(evse.connectors||[]).map(connector=>
            text(connector.plugName||connector.type||connector.standard||connector.plugType||connector.kind))))].filter(Boolean).join(' / ');
          return(variants.length>1?'<div class="small" style="margin-top:8px">Prise : '+esc(plug||group.kind)+'</div>':'')+
            renderTariffs(row.evaluation,scoped,fx,subs);
        }).join('');
        return'<details class="v9-pdc-detail"><summary><b>'+esc(pdc.label)+'</b> · '+esc(connectors.join(' / ')||(group.powerKw==null?'Puissance non renseignée':group.kind+' '+group.powerKw+' kW'))+'</summary>'+
          '<div class="small">'+esc(evseIdentity)+' · Statut : '+esc([...new Set(status)].join(', ')||'non renseigné')+' · Source : '+esc(source)+'</div>'+
          tariffs+'</details>';
      }).join('');
      return'<details class="v9-power-group"><summary><b>'+esc(group.powerKw==null?'Puissance non renseignée':group.powerKw+' kW '+group.kind)+'</b> · '+(group.pointCount>0?group.pointCount+' PDC':'Nombre de PDC non renseigné')+summary+'</summary>'+
        '<div class="v9-power-content">'+pdcs+'</div></details>';
    }).join('');
    return'<article class="box v9-result-card" data-v9-station-id="'+esc(station.id||station.canonicalId||station.stationId||'')+'" style="margin-top:10px">'+
      '<b>'+(index+1)+'. '+esc(stationDisplayName(station))+'</b><div class="small">'+esc(station.physicalOperator?.name||'Opérateur inconnu')+' · '+(card.pointCount>0?card.pointCount+' PDC':'Nombre de PDC non renseigné')+'</div>'+
      '<div class="small">'+esc(station.address||station.countryCode||'Localisation non renseignée')+'</div>'+
      '<div class="small" style="color:#9fa9b5">Base source : '+esc(stationBaseSource(station))+
      ((station.provenance||[]).some(row=>row.generatedAt)?' · Extraction : '+esc((station.provenance||[]).find(row=>row.generatedAt).generatedAt):'')+'</div>'+renderStationLinks(station)+
      '<div class="v9-station-best"><b>Meilleure option du scénario</b> · '+esc(bestLabel)+'</div>'+powerHtml+
      (best&&num(best.row.plan?.chargingMinutes)!=null?'<div class="small">Durée de charge estimée : '+esc(formatMinutes(best.row.plan.chargingMinutes))+'</div>':'')+
      (Number.isFinite(card.distanceKm)?'<div class="small">'+card.distanceKm.toFixed(1)+(card.distanceEstimated?' km à vol d’oiseau':' km')+'</div>':'')+
      renderCostPerKm(card)+'</article>';
  }

  function renderStationLinks(station){
    const lat=num(station?.latitude),lon=num(station?.longitude),date=text(station?.status?.updatedAt);
    const maps=lat!=null&&lon!=null?'https://maps.google.com/maps?daddr='+encodeURIComponent(lat+','+lon):null;
    let tesla=null;
    try{const url=new URL(text(station?.teslaUrl));if(url.protocol==='https:'&&/^(www\.)?tesla\.com$/i.test(url.hostname))tesla=url.href;}catch(_){ }
    return'<div class="small v9-station-links">'+(isTeslaStation(station)?'<span title="Source Tesla distincte des bases nationales">Réseau Tesla · '+esc(stationBaseSource(station))+'</span> · ':'')+(date?'MAJ '+esc(date)+' · ':'')+
      (maps?'<a href="'+esc(maps)+'" target="_blank" rel="noopener noreferrer">Itinéraire Google Maps</a>':'')+
      (tesla?' · <a href="'+esc(tesla)+'" target="_blank" rel="noopener noreferrer">Fiche Tesla</a>':'')+'</div>';
  }
  function renderCandidate(w,area,rows,originLabel){
    const results=w.document.getElementById('results'),routeStatus=w.document.getElementById('routeStatus');if(!results)throw new Error('stable results container missing');
    if(routeStatus)routeStatus.innerHTML='<span class="good">Moteur V9 canary · '+rows.length+' station(s) classée(s) depuis '+esc(originLabel)+'.</span>';
    if(!rows.length){renderMapSummary(w,area,rows);results.innerHTML='<div class="warn">Aucune station V9 exploitable pour cette recherche.</div>';return;}
    const preview=area?.preproductionCandidate;
    const previewBanner=preview?'<div class="small box" role="status"><b>Préproduction isolée · données candidates non publiées</b> · tarifs bruts non évalués : exclus du classement et des coûts simulés.'+
      (preview.status==='partial_failure'?' · Sources refusées : '+esc((preview.rejected||[]).map(r=>r.source).join(', ')||'voir journal'):'')+'</div>':'';
    const matching=Number(area?.diagnostics?.sourceStationCount),offset=Number(area?.query?.stationOffset)||0,shown=Number(area?.stations?.length),
      limitedBanner=Number.isFinite(matching)&&matching>shown?'<div class="small box" role="status"><b>Recherche paginée</b> · stations '+esc(offset+1)+' à '+esc(offset+shown)+' sur '+esc(matching)+'. Les autres sont accessibles avec la pagination.</div>':'';
    const batchSize=20,initial=Math.min(rows.length,batchSize);
    results.innerHTML=previewBanner+limitedBanner+'<div class="small box"><b>Moteur V9</b> · une carte par station, toutes les puissances et tous les PDC.</div>'+
      rows.slice(0,initial).map((row,i)=>renderStationCard(row,offset+i,area)).join('')+
      (initial<rows.length?'<button type="button" class="secondary v9-more-stations" style="margin-top:12px">Afficher les stations suivantes · '+initial+' / '+rows.length+'</button>':'')+
      (offset>0||offset+shown<matching?'<nav class="v9-page-nav" aria-label="Pages de stations" style="display:flex;gap:8px;margin-top:12px">'+(offset>0?'<button type="button" class="secondary v9-prev-page">Page précédente</button>':'')+(offset+shown<matching?'<button type="button" class="secondary v9-next-page">Page suivante</button>':'')+'</nav>':'');
    if(initial<rows.length){
      let shown=initial;
      const more=results.querySelector('.v9-more-stations');
      more.addEventListener('click',()=>{
        const next=Math.min(rows.length,shown+batchSize);
        more.insertAdjacentHTML('beforebegin',rows.slice(shown,next).map((row,i)=>renderStationCard(row,offset+shown+i,area)).join(''));
        shown=next;
        if(shown===rows.length)more.remove();
        else more.textContent='Afficher les stations suivantes · '+shown+' / '+rows.length;
      });
    }

    renderMapSummary(w,area,rows);
  }


  function areaFiltersFromInputs(input){
    return{
      ...(input?.operatorIds?.length?{operatorIds:input.operatorIds.slice()}:{}),
      ...(input?.connectorKinds?.length?{connectorKinds:input.connectorKinds.slice()}:{}),
      ...(input?.minPowerKw!=null?{minPowerKw:Number(input.minPowerKw)}:{}),
      ...(input?.maxPowerKw!=null?{maxPowerKw:Number(input.maxPowerKw)}:{})
    };
  }
  function countryQueryMode(countryCode,scope,operatorIds=[]){
    if(!scope?.length||scope.includes(countryCode))return'full';
    if(operatorIds.some(id=>text(id).toLowerCase()!=='tesla'))throw new Error(`country outside V9 shell scope: ${countryCode}`);
    return'tesla-only';
  }
  function variantMatchesFilters(row,input={}){
    const line=row?.powerLine||{},kind=text(line.kind).toUpperCase(),power=num(line.powerKw);
    return(!input.connectorKinds?.length||input.connectorKinds.includes(kind))&&
      (input.minPowerKw==null||power!=null&&power>=input.minPowerKw)&&
      (input.maxPowerKw==null||power!=null&&power<=input.maxPowerKw);
  }
  // Keep only compact ranking facts across batches; full EVSE/tariff cards live on one page.
  const searchRankingCache=new WeakMap();
  function rankingSummary(card){
    const st=card.station,best=pricedBest(card.evaluation);
    return{station:{id:st.id,name:st.name,countryCode:st.countryCode,latitude:st.latitude,longitude:st.longitude,
      physicalOperator:st.physicalOperator,hasRawOffer:(st.unparsedOffers||[]).some(o=>o.calculationStatus==='not_evaluated')},
      total:card.total,costPerKm:card.costPerKm,distanceKm:card.distanceKm,distanceEstimated:card.distanceEstimated,
      score:{totalTimeMinutes:card.score?.totalTimeMinutes},
      rankingChoices:(card.rankingChoices||[]).map(c=>({costPerKm:c.costPerKm,score:{totalTimeMinutes:c.score?.totalTimeMinutes}})),
      evaluation:best?{best:{total:best.total,targetCurrency:best.targetCurrency,costPerRecoveredKm:best.costPerRecoveredKm,result:{complete:true}}}:null,
      summaryOnly:true};
  }
  async function rankedPage(w,engine,query,input,origin,selected){
    const key=JSON.stringify({...query,stationOffset:0});
    const cardsFor=area=>stationCards(variantsByPower(w,rowsFromArea(area,origin),area.effectiveSession||query.session,selected)
      .filter(row=>variantMatchesFilters(row,input)),selected);
    let cached=searchRankingCache.get(engine);
    if(!cached||cached.key!==key){
      const pending=(async()=>{
        const summaries=[];let inventory=[],count=Infinity,lastYield=performance.now();
        for(let offset=0;offset<count;offset+=40){
          const batch=await engine.queryArea({...query,stationOffset:offset,stationLimit:40,skipSessionEvaluation:true,omitSubscriptionOptions:true,omitMapInventory:offset>0});
          if(offset===0){count=Number(batch.diagnostics?.sourceStationCount) || batch.stations.length;inventory=batch.mapStations||[];}
          const baseRows=rowsFromArea(batch,origin),pricedStations=baseRows.filter(row=>row.station.offers?.length),unpriced=baseRows.filter(row=>!row.station.offers?.length);
          const evaluated=stationCards(variantsByPower(w,pricedStations,batch.effectiveSession||query.session,selected)
            .filter(row=>variantMatchesFilters(row,input)),selected,true);
          const byId=new Map(evaluated.map(card=>[card.station.id,rankingSummary(card)]));
          for(const row of unpriced){
            const lines=powerLines(row);
            if((lines.length?lines:[{kind:'UNKNOWN',powerKw:null}]).some(powerLine=>variantMatchesFilters({powerLine},input)))
              byId.set(row.station.id,rankingSummary({...row,evaluation:null,total:null,costPerKm:null}));
          }
          summaries.push(...baseRows.map(row=>byId.get(row.station.id)).filter(Boolean));
          // Keep input and paint responsive while avoiding a timer for every
          // small batch. A slower device still yields after its first batch.
          if(offset+40<count&&performance.now()-lastYield>=50){
            await new Promise(resolve=>setTimeout(resolve,0));lastYield=performance.now();
          }
        }
        return{summaries,inventory,count,order:null};
      })();
      cached={key,pending};searchRankingCache.set(engine,cached);
      pending.catch(()=>{if(searchRankingCache.get(engine)===cached)searchRankingCache.delete(engine);});
    }
    const calculated=await cached.pending;
    // Sorting does not change vehicle, EVSE, tariff or session inputs. Retain
    // those exact search results and rebuild only order + map page numbers.
    if(calculated.order?.mode!==input.rankingMode){
      const ranked=rankRows(calculated.summaries,input.rankingMode,calculated.summaries.length);
      const ranks=new Map(ranked.map((row,index)=>[row.station.id,index]));
      calculated.order={mode:input.rankingMode,ranked,count:calculated.count,
        inventory:calculated.inventory.filter(st=>ranks.has(st.id)).map(st=>({...st,page:Math.floor(ranks.get(st.id)/160)}))};
    }
    const snapshot=calculated.order,selectedRows=snapshot.ranked.slice(query.stationOffset,query.stationOffset+160);
    const area=await engine.queryArea({...query,stationIds:selectedRows.map(row=>row.station.id),omitMapInventory:true});
    const byId=new Map(cardsFor(area).map(row=>[row.station.id,row]));
    const rows=selectedRows.map(row=>byId.get(row.station.id)).filter(Boolean);
    area.mapStations=snapshot.inventory;area.mapRankingRows=snapshot.ranked;
    area.diagnostics={...area.diagnostics,spatialStationCount:snapshot.count,sourceStationCount:snapshot.ranked.length,globallyRankedStationCount:snapshot.ranked.length};
    return{area,rows};
  }
  async function executeV9(w,engine,cfg,input){
    if(!Number.isFinite(input.startSoc)||!Number.isFinite(input.targetSoc)||input.startSoc<0||input.targetSoc>100||!(input.targetSoc>input.startSoc))throw new Error('Renseignez les niveaux de batterie entre 0 et 100 %, avec une cible supérieure au départ.');if(!input.originText)throw new Error('origin required');
    if(cfg.mode==='candidate'&&!(input.radiusKm>0))throw new Error('unbounded radius not production-equivalent');
    if(typeof w.resolveOrigin!=='function')throw new Error('stable origin resolver unavailable');const origin=await w.resolveOrigin(input.originText),countryCode=await countryCodeForOrigin(w,origin),scope=cfg.engineScopeCountries||[];
    const queryMode=countryQueryMode(countryCode,scope,input.operatorIds||[]);
    if(input.radiusKm>100)throw new Error('Le rayon maximal est de 100 km. Choisissez un rayon inférieur ou égal à 100 km.');
    const queryRadius=input.radiusKm>0?input.radiusKm:20,filters=areaFiltersFromInputs(input),session=buildSession(input,countryCode);session.fxRates=engine.__tccFxRates||{};
    if(queryMode==='tesla-only')filters.operatorIds=['tesla'];
    const selected=selectedSubscriptionsForConfig(w,cfg);
    const {area,rows}=await rankedPage(w,engine,{countryCode,origin:{lat:Number(origin.lat),lon:Number(origin.lon)},radiusKm:queryRadius,filters,session,vehicleProfileId:'generic-ev-preview',selectedSubscriptions:selected,subscriptionFilters:{countryCodes:[countryCode],coverageMode:'any'},globalRouting:true,routingBudget:80,perOperatorFloor:2,stationLimit:160,stationOffset:Math.max(0,Math.floor(Number(input.stationOffset)||0)),sortBy:'finalCost'},input,origin,selected);
    if(queryMode==='tesla-only'&&!area.stations?.some(isTeslaStation))throw new Error(`no Tesla V9 station in ${countryCode}`);
    area.selectedSubscriptions=selected;area.preproductionCandidate=engine.__tccPreparedCandidate||null;
    area.displayFxRates=session.fxRates;return{area,rows,origin,countryCode,queryRadius,partialRadius:!(input.radiusKm>0),selectedSubscriptions:selected};
  }

  function normalizeLegacyChrome(w){
    const d=w.document;
    const radiusInput=d.getElementById('simMaxDistance');if(radiusInput){radiusInput.max='100';radiusInput.setAttribute('aria-description','Rayon maximal : 100 km');}
    d.documentElement.dataset.tccVersion='v9';
    d.title='Tesla Charge Companion V9';
    const heading=d.querySelector('header h1,h1');
    if(heading)heading.textContent='⚡ Tesla Charge Companion V9';
    const versionNodes=[...d.querySelectorAll('header *,body *')].filter(el=>el.children.length===0);
    const version=versionNodes.find(el=>/Version 7\.3 Stable/i.test(text(el.textContent)));
    if(version)version.textContent='Version V9 · snapshot figé · comparaison de prix';
    const hideLegacyNlBlocks=()=>{
      const refreshButtons=[...d.querySelectorAll('button')].filter(btn=>/recharger les données|recharger.*pays[-\s]?bas/i.test(text(btn.textContent)));
      refreshButtons.forEach(btn=>{
        const obsoleteCard=btn.closest('.card');
        if(obsoleteCard&&obsoleteCard!==d.querySelector('#compare > .card'))obsoleteCard.remove();
        else btn.remove();
      });
      [...d.querySelectorAll('.small,p,small')].filter(el=>/snapshot DOT[-\s]?NL|données Pays[-\s]?Bas|données des Pays[-\s]?Bas/i.test(text(el.textContent))).forEach(el=>{
        const obsoleteCard=el.closest('.card');
        if(obsoleteCard&&obsoleteCard!==d.querySelector('#compare > .card'))obsoleteCard.remove();
        else el.remove();
      });
    };
    hideLegacyNlBlocks();
    if(typeof w.MutationObserver==='function'){
      const observer=new w.MutationObserver(hideLegacyNlBlocks);
      observer.observe(d.body,{childList:true,subtree:true});
    }
    const legacyTabs=[...d.querySelectorAll('button')].filter(btn=>/^(Bornes|Ajouter \/ modifier|Devises|Synchronisation)$/i.test(text(btn.textContent)));
    legacyTabs.forEach(btn=>{btn.hidden=true;btn.style.display='none';});
  }
  function installUsageHelpTab(w){
    const d=w.document,nav=d.querySelector('header nav'),main=d.querySelector('main');
    if(!nav||!main||d.getElementById('v9UsageHelpTab'))return;
    const button=d.createElement('button');button.id='v9UsageHelpTab';button.type='button';button.textContent='Mode d’emploi';
    button.setAttribute('aria-controls','v9UsageHelp');button.setAttribute('aria-label','Ouvrir le mode d’emploi');
    const panel=d.createElement('section');panel.id='v9UsageHelp';panel.className='panel';
    panel.innerHTML='<div class="card"><h2>Mode d’emploi</h2>'+
      '<h3>1. Préparer la recherche</h3><p>Saisis une adresse de départ ou utilise « Position actuelle », puis règle le niveau de batterie, l’objectif et le profil de calcul. Dans la préproduction, tu peux aussi modifier la capacité utile, la consommation et les puissances maximales AC/DC du véhicule. Les valeurs affichées au départ sont un profil indicatif, pas des caractéristiques confirmées de ton véhicule.</p>'+
      '<h3>2. Choisir les réseaux</h3><p>Tous les réseaux sont sélectionnés au départ. « Tesla uniquement » limite la recherche au réseau Tesla. La liste Opérateurs permet de choisir plusieurs réseaux et applique chaque changement directement.</p>'+
      '<h3>3. Régler les filtres et lancer le calcul</h3><p>Choisis le type AC/DC, la puissance minimale et maximale, la distance et la priorité de classement. Appuie sur « Simuler » pour afficher les résultats.</p>'+
      '<h3>4. Lire les prix</h3><p>Chaque PDC présente les voies Direct, Electra et Electroverse, ainsi que les abonnements sélectionnés lorsqu’ils s’appliquent. « Prix non disponible » signifie qu’aucune offre tarifaire exploitable n’est identifiée dans cette catégorie; « Tarif incalculable » signale une offre identifiée sans calcul fiable. Le tarif calculable le plus bas est mis en évidence. Déplie « Détail du tarif » pour consulter la grille complète et la source.</p>'+
      '<h3>5. Comprendre une fiche</h3><p>Chaque station occupe une fiche unique regroupant toutes ses puissances AC/DC et leurs PDC. Déplie une puissance, puis un PDC, pour consulter les tarifs qui lui correspondent et leurs conditions. Le coût par kilomètre récupéré aide au classement; le routage détaillé se lance à la demande.</p>'+
      '<h3>6. Fraîcheur des données</h3><p>En bas de page, consulte la dernière date fournie par les métadonnées de chaque base. Si la source ne donne pas de date, la page indique la date de révision du snapshot épinglé.</p>'+
      '<p class="small">Les états de disponibilité en temps réel ne sont pas utilisés. Les tarifs non validés ou non comparables restent signalés comme indisponibles.</p></div>';
    main.appendChild(panel);
    button.addEventListener('click',()=>{
      d.querySelectorAll('nav button,.panel').forEach(el=>el.classList.remove('active'));
      button.classList.add('active');panel.classList.add('active');
    });
    nav.querySelectorAll('button').forEach(tab=>tab.addEventListener('click',()=>{
      if(tab===button)return;
      button.classList.remove('active');panel.classList.remove('active');
      const targetId=tab.getAttribute('data-tab');
      const targetNode=targetId?d.getElementById(targetId):null;
      const target=targetNode?.classList.contains('panel')?targetNode:
        targetNode?.closest('.panel')||targetNode?.querySelector('.panel');
      if(target)d.querySelectorAll('.panel').forEach(item=>item.classList.toggle('active',item===target));
    }));
    nav.appendChild(button);
  }

  function installPreviewValidation(w,cfg){
    if(cfg?.preproductionIsolated!==true)return;
    const d=w.document,nav=d.querySelector('header nav'),main=d.querySelector('main');
    if(!nav||!main||d.getElementById('v9ValidationTab'))return;
    const tab=d.createElement('button');tab.id='v9ValidationTab';tab.type='button';tab.textContent='Tester TCC V9';
    tab.setAttribute('aria-controls','v9ValidationPanel');
    const panel=d.createElement('section');panel.id='v9ValidationPanel';panel.className='panel';
    panel.innerHTML='<div class="card"><h2>Parcours de validation TCC V9</h2>'+
      '<ol><li>Recherche une station ou utilise ta position, puis ouvre sa fiche sur la carte.</li>'+
      '<li>Vérifie les EVSE, les prises et les puissances AC/DC regroupées.</li>'+
      '<li>Compare Direct, Electra et Electroverse. « Tarif incalculable » indique une offre sans calcul fiable.</li>'+
      '<li>Règle batterie, objectif, consommation et puissance du véhicule ; vérifie coût, durée et coût/km lorsqu’ils sont calculables.</li>'+
      '<li>Essaie les filtres, abonnements et la vue mobile.</li></ol>'+
      '<label for="v9FeedbackText">Une anomalie ? Décris la station, le tarif ou le calcul observé.</label>'+
      '<textarea id="v9FeedbackText" rows="4" style="width:100%;box-sizing:border-box;margin-top:8px" placeholder="Décris ce qui ne correspond pas à tes attentes"></textarea>'+
      '<button id="v9FeedbackShare" type="button" class="primary" style="margin-top:8px">Partager ce signalement</button>'+
      '<p id="v9FeedbackStatus" class="small" role="status" aria-live="polite"></p></div>';
    main.appendChild(panel);nav.appendChild(tab);
    tab.addEventListener('click',()=>{d.querySelectorAll('nav button,.panel').forEach(el=>el.classList.remove('active'));tab.classList.add('active');panel.classList.add('active');});
    nav.querySelectorAll('button').forEach(other=>{if(other!==tab)other.addEventListener('click',()=>{tab.classList.remove('active');panel.classList.remove('active');});});
    panel.querySelector('#v9FeedbackShare').addEventListener('click',async()=>{
      const description=panel.querySelector('#v9FeedbackText').value.trim(),status=panel.querySelector('#v9FeedbackStatus');
      if(!description){status.textContent='Décris d’abord l’anomalie à signaler.';return;}
      const body='TCC V9 · signalement\nBundle : '+text(cfg.preparedBundleId)+'\nPage : '+w.location.href+'\n\n'+description;
      try{
        if(typeof w.navigator.share==='function'){
          await w.navigator.share({title:'Signalement TCC V9',text:body});status.textContent='Signalement partagé.';
        }else if(w.navigator.clipboard?.writeText){
          await w.navigator.clipboard.writeText(body);status.textContent='Signalement copié. Colle-le dans ta conversation TCC.';
        }else{status.textContent='Copie ce texte et envoie-le dans ta conversation TCC : '+body;}
      }catch(error){status.textContent=error?.name==='AbortError'?'Partage annulé.':'Partage indisponible. Copie ton message et envoie-le dans ta conversation TCC.';}
    });
  }

  function installBaseUpdatesFooter(w,cfg){
    const d=w.document;if(d.getElementById('v9BaseUpdates'))return;
    const footer=d.createElement('footer');footer.id='v9BaseUpdates';footer.className='card small';
    footer.style.cssText='max-width:720px;margin:18px auto 24px;padding:12px 16px;box-sizing:border-box';
    footer.innerHTML='<details><summary><b>Dates de mise à jour des bases TCC</b></summary><p>Chargement des dates des sources…</p></details>';
    (d.querySelector('main')||d.body).appendChild(footer);
    const base=String(cfg?.runtimeBase||'runtime');
    w.fetch(base+'/data/v9/base-dates.json',{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error('dates '+response.status);return response.json();}).then(data=>{
      const rows=(data?.bases||[]).map(item=>{
        const date=item.date?new Date(item.date+'T00:00:00').toLocaleDateString('fr-FR',{timeZone:'Europe/Paris'}):'Date non fournie';
        const note=item.dateType==='source'?'Source':'Révision épinglée';
        return'<tr><th style="text-align:left;padding:4px 10px 4px 0">'+esc(item.label||item.id)+'</th><td style="padding:4px 8px">'+esc(date)+'</td><td style="padding:4px 0;color:#9299a2">'+note+'</td></tr>';
      }).join('');
      footer.querySelector('details').innerHTML='<summary><b>Dates de mise à jour des bases TCC</b></summary><p>Dates source si disponibles; sinon date de révision épinglée du snapshot.</p><div style="overflow:auto"><table><tbody>'+rows+'</tbody></table></div><p class="small">Snapshot '+esc(data.snapshotId||'V9')+' · données figées pour les tests.</p>';
    }).catch(()=>{footer.querySelector('details').innerHTML='<summary><b>Dates de mise à jour des bases TCC</b></summary><p>Le relevé des dates est indisponible dans cette version du snapshot.</p>';});
  }
  function installV9MobileLayout(w){
    const d=w.document;
    if(d.getElementById('v9MobileLayoutStyle'))return;
    const style=d.createElement('style');
    style.id='v9MobileLayoutStyle';
    style.textContent='html,body{width:100%!important;max-width:none!important;overflow-x:hidden!important}body{zoom:1!important}#compare,#compare .card,#compare .grid,#results{width:100%!important;max-width:720px!important;box-sizing:border-box!important;margin-left:auto!important;margin-right:auto!important}#v9OperatorControls{align-items:center!important}#v9OperatorDropdown{min-width:200px}#v9UsageHelp{max-width:720px;margin:0 auto}#v9UsageHelp .card{line-height:1.55}#v9UsageHelp h2{margin-top:0}#v9BaseUpdates{width:calc(100% - 20px)}@media(max-width:600px){body{font-size:16px!important}#compare{padding-left:10px!important;padding-right:10px!important}#v9OperatorControls{display:grid!important;grid-template-columns:1fr 1fr}#v9OperatorControls select{grid-column:1/-1;width:100%;box-sizing:border-box}.v9-select-dropdown{grid-column:1/-1;width:100%;box-sizing:border-box}.v9-select-dropdown select{max-height:230px;overflow:auto}.v9-dropdown-panel{max-height:240px;overflow:auto}.v9-dropdown-value{float:right;color:#aaa;font-weight:400;max-width:58%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}#compare .v9-filter-group .grid{grid-template-columns:minmax(0,1fr) minmax(0,1fr)!important;min-width:0!important}#compare .v9-filter-group .grid>div{min-width:0!important}#compare input#simDate,#compare input#simTime,#compare input#simUnplugTime{display:block!important;width:100%!important;max-width:160px!important;min-width:0!important;height:42px!important;min-height:42px!important;padding:6px 8px!important;font-size:15px!important;line-height:1.2!important;box-sizing:border-box!important;-webkit-appearance:none!important;appearance:none!important}#compare input#simTime,#compare input#simUnplugTime{text-align:center!important}}';
    style.textContent+='body{box-sizing:border-box!important}.v9-result-card{min-width:0;overflow-wrap:anywhere}.v9-station-best{margin:10px 0;padding:8px 10px;border-radius:8px;background:#232b34}.v9-power-group{margin:8px 0;border:1px solid #34404c;border-radius:8px;padding:8px}.v9-power-group>summary,.v9-pdc-detail>summary{cursor:pointer}.v9-power-group>summary::marker,.v9-pdc-detail>summary::marker{color:#f4a64a}.v9-power-lane-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:7px}.v9-power-lane{display:flex;flex-direction:column;gap:3px;min-width:0;padding:6px;border:1px solid;border-radius:6px}.v9-power-lane small{overflow-wrap:anywhere}.v9-power-content{padding:4px 0}.v9-pdc-detail{margin:7px 0;padding:8px;border-radius:6px;background:#171e26}.v9-pdc-detail .v9-tariffs{max-width:100%}@media(max-width:600px){.v9-power-lane-grid{grid-template-columns:1fr}.v9-power-lane{flex-direction:row;justify-content:space-between;gap:8px}.v9-pdc-detail .v9-tariff-row{grid-template-columns:minmax(0,1fr)!important}.v9-pdc-detail .v9-lane-amount{text-align:left}}';
    style.textContent+='#v9FloatingNavigation{position:fixed;right:max(12px,env(safe-area-inset-right));bottom:max(14px,env(safe-area-inset-bottom));z-index:999;display:flex;gap:8px;max-width:calc(100vw - 24px)}#v9FloatingNavigation button{width:auto;min-width:72px;padding:10px 12px;border-radius:999px;background:#202c39;color:#fff;border:1px solid #8796a8;box-shadow:0 3px 12px #0008;cursor:pointer}#v9FloatingNavigation button:focus-visible{outline:3px solid #f4a64a;outline-offset:3px}#compare .v9-filter-group{margin:6px 0;padding:8px 10px}#compare .v9-filter-group>summary{cursor:pointer;font-weight:600}#compare .v9-filter-group .grid{gap:8px}@media(max-width:600px){#v9FloatingNavigation{right:10px;bottom:max(10px,env(safe-area-inset-bottom));gap:6px}#v9FloatingNavigation button{min-width:62px;padding:8px 10px;font-size:13px}#compare .v9-filter-group{padding:7px 8px}}@media(prefers-reduced-motion:reduce){#v9FloatingNavigation *{scroll-behavior:auto}}';
    d.head.appendChild(style);
  }

  // Lot 2: accessible, compact navigation without changing form semantics.
  function installFloatingNavigation(w){
    const d=w.document;
    if(d.getElementById('v9FloatingNavigation'))return;
    const compare=d.getElementById('compare');
    if(!compare)return;
    const nav=d.createElement('nav');
    nav.id='v9FloatingNavigation';
    nav.setAttribute('aria-label','Navigation rapide TCC');
    nav.innerHTML='<button type="button" id="v9JumpFilters" aria-label="Ouvrir les filtres">Filtres</button>'+
      '<button type="button" id="v9JumpTop" aria-label="Revenir en haut de page">Haut ↑</button>';
    d.body.appendChild(nav);
    const filters=nav.querySelector('#v9JumpFilters');
    const top=nav.querySelector('#v9JumpTop');
    filters.addEventListener('click',()=>{
      const panel=d.querySelector('#compare .v9-filter-group');
      const target=panel||compare;
      if(panel)panel.open=true;
      const containingPanel=compare.closest('.panel');
      if(containingPanel&&!containingPanel.classList.contains('active')){
        const tab=[...d.querySelectorAll('header nav button')].find(button=>
          d.getElementById(button.getAttribute('data-tab'))===containingPanel);
        tab?.click();
      }
      target.scrollIntoView?.({behavior:'smooth',block:'start'});
      (panel?.querySelector('summary')||compare.querySelector('input,select,button'))?.focus?.({preventScroll:true});
    });
    top.addEventListener('click',()=>w.scrollTo?.({top:0,behavior:'smooth'}));
  }
  function installCurrentPositionButton(w){
    const input=w.document.getElementById('simOrigin');
    if(!input||w.document.getElementById('v9UseCurrentPosition'))return;
    const button=w.document.createElement('button');
    button.id='v9UseCurrentPosition';button.type='button';
    button.className='secondary';button.textContent='⌖ Position actuelle';
    button.setAttribute('aria-label','Utiliser ma position actuelle');
    button.title='Utiliser la position GPS actuelle';
    button.style.cssText='width:auto;margin-top:6px;padding:8px 12px';
    const host=input.parentElement||input;
    const actions=w.document.createElement('div');
    actions.className='v9-origin-actions';actions.style.cssText='display:flex;gap:8px;flex-wrap:wrap;align-items:center';
    host.appendChild(actions);actions.appendChild(button);
    const save=w.document.querySelector('button[onclick="saveDefaultOrigin()"]');
    if(save){save.id='v9SaveDefaultOrigin';save.type='button';
      save.style.cssText='width:auto;margin-top:6px;padding:8px 12px';actions.appendChild(save);}

    button.addEventListener('click',()=>{
      if(!w.navigator?.geolocation){button.textContent='GPS indisponible';return;}
      button.disabled=true;button.textContent='Localisation…';
      w.navigator.geolocation.getCurrentPosition(
        position=>{
          const lat=Number(position.coords.latitude).toFixed(6),lon=Number(position.coords.longitude).toFixed(6);
          input.value=lat+', '+lon;input.dataset.v9Coordinates='true';
          input.dispatchEvent(new w.Event('input',{bubbles:true}));
          button.disabled=false;button.textContent='⌖ Position actuelle';
        },
        error=>{
          button.disabled=false;button.textContent='⌖ Position actuelle';
          diagnosticStore(w,{mode:'candidate',outcome:'geolocation-error',reason:error?.message||'permission-or-unavailable'});
        },
        {enableHighAccuracy:true,maximumAge:120000,timeout:10000}
      );
    });
  }

  function mountCheckboxDropdown(w,select,detailsId,{title,allValue=null}={}){
    if(!select)return null;
    select.multiple=true;
    select.style.display='block';
    select.setAttribute('aria-label',title||'Sélection multiple');
    select.style.width='100%';
    select.style.minHeight='96px';
    let details=w.document.getElementById(detailsId);
    if(!details){
      details=w.document.createElement('details');
      details.id=detailsId;
      details.className='v9-select-dropdown';
      select.parentNode?.insertBefore(details,select);
    }
    details.innerHTML='<summary><b>'+esc(title||'Sélection')+'</b><span class="v9-dropdown-value"></span></summary>';details.style.flex='1 1 auto';
    details.appendChild(select);
    const summary=details.querySelector('.v9-dropdown-value');
    const redraw=()=>{
      const options=[...select.options],selected=[...select.selectedOptions];
      const labels=selected.map(o=>text(o.textContent));
      if(summary)summary.textContent=allValue&&selected.some(o=>text(o.value)===allValue)?'Tous les réseaux':(select.dataset.v9Mode==='all'?'Tous les réseaux':select.dataset.v9Mode==='tesla'?'Tesla uniquement':(labels.length?labels.join(', '):'Aucun'));
    };
    if(!select.dataset.v9DropdownBound){
      select.dataset.v9DropdownBound='true';
      select.addEventListener('change',()=>{
        if(allValue){
          const all=[...select.options].find(o=>text(o.value)===allValue);
          const picked=[...select.selectedOptions];
          if(all&&picked.some(o=>o===all)&&picked.length>1){
            [...select.options].forEach(o=>{o.selected=o===all;});
          }else if(all&&picked.some(o=>o!==all)){
            all.selected=false;
          }
        }
        redraw();
      });
    }
    select._v9Redraw=redraw;
    redraw();
    return details;
  }

  function mountOperatorPicker(w,select){
    let panel=w.document.getElementById('v9OperatorDropdown');
    if(!panel){panel=w.document.createElement('details');panel.id='v9OperatorDropdown';}
    panel.style.cssText='flex:1 1 280px;min-width:240px;max-width:450px;border:1px solid #46505b;border-radius:8px;padding:8px;background:#1a222b;box-sizing:border-box';
    panel.innerHTML='<summary style="cursor:pointer;font-weight:600">Opérateurs · choisir plusieurs réseaux</summary><div class="v9-operator-choices" role="group" aria-label="Choix des réseaux" style="max-height:150px;overflow:auto;display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:4px"></div>';
    const choices=panel.querySelector('.v9-operator-choices'),selected=()=>new Set([...select.selectedOptions].map(option=>text(option.value)));
    const redraw=()=>{const values=selected();choices.innerHTML=[...select.options].map(option=>'<label style="display:flex;align-items:center;gap:5px;margin:0"><input type="checkbox" value="'+esc(option.value)+'" '+(values.has(text(option.value))?'checked':'')+' style="width:auto;margin:0"><span>'+esc(option.textContent)+'</span></label>').join('');};
    choices.addEventListener('change',()=>{const values=new Set([...choices.querySelectorAll('input:checked')].map(input=>text(input.value)));for(const option of [...select.options])option.selected=values.has(text(option.value));select.dispatchEvent(new w.Event('change',{bubbles:true}));});
    select._v9Redraw=redraw;redraw();return panel;
  }

  function installOperatorMultiSelect(w){
    const select=w.document.getElementById('simOperatorFilter');
    if(!select)return;
    const field=select.closest('.full')||select.parentElement;
    field?.querySelector(':scope > label')?.remove();
    select.parentElement?.querySelector(':scope > label')?.remove();
    const previousValues=select.multiple?[...select.selectedOptions].map(option=>text(option.value)).filter(Boolean):[];
    const options=new Map();
    for(const option of [...select.options]){
      const value=text(option.value),label=text(option.textContent);
      if(!value||value==='all')continue;
      options.set(value,value==='tesla'?'Tesla':label);
    }
    if(!options.has('tesla'))options.set('tesla','Tesla');
    select.multiple=true;select.setAttribute('multiple','');select.dataset.v9Multi='true';
    select.setAttribute('aria-label','Opérateurs à afficher');
    const remembered=w.__TCCV9OperatorSelection;
    const mode=remembered?.mode||'all';
    select.innerHTML=[...options.entries()].map(([value,label])=>'<option value="'+esc(value)+'">'+esc(label)+'</option>').join('');
    const initial=mode==='all'?[]:mode==='tesla'?['tesla']:(remembered?.values||previousValues).filter(value=>options.has(value));
    for(const option of [...select.options])option.selected=initial.includes(text(option.value));
    select.dataset.v9Mode=initial.length?(initial.length===1&&initial[0]==='tesla'?'tesla':'selected'):'all';
    let controls=w.document.getElementById('v9OperatorControls');
    if(!controls){controls=w.document.createElement('div');controls.id='v9OperatorControls';controls.style.cssText='display:flex;align-items:center;gap:8px;flex-wrap:wrap;width:100%;box-sizing:border-box';}
    const makeButton=(id,label,title)=>{
      let button=w.document.getElementById(id);
      if(!button){button=w.document.createElement('button');button.type='button';button.id=id;button.className='secondary';button.textContent=label;button.title=title;button.style.cssText='width:auto;margin:0;padding:10px 12px;white-space:nowrap';}
      return button;
    };
    const group=select.closest('.v9-network-controls'),displayLabel=group?.querySelector('.v9-network-heading');
    let active=w.document.getElementById('v9ActiveNetworkFilter');
    if(!active){active=w.document.createElement('span');active.id='v9ActiveNetworkFilter';}
    if(displayLabel){displayLabel.textContent='Réseaux affichés — ';displayLabel.appendChild(active);}
    const updateSummary=()=>{
      const mode=select.dataset.v9Mode||'all',names=[...select.selectedOptions].map(option=>text(option.textContent));
      w.__TCCV9OperatorSelection={mode,values:[...select.selectedOptions].map(option=>text(option.value))};
      active.textContent=mode==='all'?'Tous les réseaux':mode==='tesla'?'Tesla uniquement':(names.join(', ')||'Tous les réseaux');select._v9Redraw?.();
    };
    const choose=mode=>{
      select.dataset.v9Mode=mode;
      for(const option of [...select.options])option.selected=mode==='tesla'&&text(option.value)==='tesla';
      select.dispatchEvent(new w.Event('change',{bubbles:true}));
    };
    if(!select.dataset.v9SummaryBound){
      select.addEventListener('change',()=>{
        const values=[...select.selectedOptions].map(option=>text(option.value));
        select.dataset.v9Mode=values.length?(values.length===1&&values[0]==='tesla'?'tesla':'selected'):'all';
        updateSummary();
      });
      select.dataset.v9SummaryBound='true';
    }
    const tesla=makeButton('v9TeslaOnly','Tesla uniquement','Afficher uniquement le réseau Tesla');
    const all=makeButton('v9AllNetworks','Tous les réseaux','Afficher tous les réseaux');
    if(!tesla.dataset.v9Bound){tesla.addEventListener('click',()=>choose('tesla'));tesla.dataset.v9Bound='true';}
    if(!all.dataset.v9Bound){all.addEventListener('click',()=>choose('all'));all.dataset.v9Bound='true';}
    const dropdown=mountOperatorPicker(w,select);
    controls.append(tesla,all,dropdown);
    if(controls.parentElement!==field)field?.insertBefore(controls,field.firstChild);
    select.style.cssText='display:none';
    updateSummary();
    if(w.__TCCV9OperatorSelect!==select){
      w.__TCCV9OperatorSelect=select;
      const observer=new w.MutationObserver(()=>{
        const current=w.document.getElementById('simOperatorFilter');
        if(current&&current!==w.__TCCV9OperatorSelect)installOperatorMultiSelect(w);
        else if(current&&!current.multiple){current.multiple=true;current.setAttribute('multiple','');}
      });
      observer.observe(w.document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['multiple']});
      w.__TCCV9OperatorObserver=observer;
    }
  }

  const OPERATOR_CATALOG_KEY='tccV9OperatorCatalogsV1';
  function operatorCatalogKey(area){
    const origin=area?.query?.origin||{};
    const filters=area?.query?.filters||{};
    const key={country:text(area?.query?.countryCode).toUpperCase(),lat:Number(origin.lat).toFixed(3),lon:Number(origin.lon).toFixed(3),radius:Number(area?.query?.radiusKm)||0,connectorKinds:(filters.connectorKinds||[]).slice().sort(),minPowerKw:num(filters.minPowerKw),maxPowerKw:num(filters.maxPowerKw)};
    return JSON.stringify(key);
  }
  function operatorRows(area){
    const operators=new Map([['tesla','Tesla']]);
    for(const operator of area?.availableOperators||area?.operators||[]){const id=text(operator?.id||'').toLowerCase(),label=text(operator?.name||'');if(id&&label&&id!=='tesla')operators.set(id,label);}
    for(const station of area?.stations||[]){
      const op=station.physicalOperator||station.operator||{};
      const id=text(op.id||station.operatorId||'').toLowerCase();
      const label=text(op.name||station.operatorName||'');
      if(id&&label&&id!=='tesla')operators.set(id,label);
    }
    return operators;
  }
  function refreshOperatorOptions(w,area){
    const select=w.document.getElementById('simOperatorFilter');if(!select)return;
    const current=select.multiple?[...select.selectedOptions].map(option=>text(option.value)).filter(Boolean):(text(select.value)?[text(select.value)]:[]);
    const mode=select.dataset.v9Mode||'all',key=operatorCatalogKey(area),cacheKey=OPERATOR_CATALOG_KEY;
    let catalogs={};try{catalogs=JSON.parse(w.sessionStorage.getItem(cacheKey)||'{}');}catch(_){}
    const incoming=operatorRows(area),operators=new Map([['tesla','Tesla']]);
    const cached=catalogs[key];
    if(cached&&Array.isArray(cached)&&mode!=='all')for(const row of cached){if(Array.isArray(row)&&row.length===2)operators.set(text(row[0]),text(row[1]));}
    for(const [id,label] of incoming)operators.set(id,label);
    catalogs[key]=[...operators.entries()];
    try{w.sessionStorage.setItem(cacheKey,JSON.stringify(catalogs));}catch(_){}
    select.innerHTML=[...operators.entries()].map(([value,label])=>'<option value="'+esc(value)+'">'+esc(label)+'</option>').join('');
    const keep=mode==='all'?[]:mode==='tesla'?['tesla']:current;
    for(const option of [...select.options])option.selected=keep.includes(text(option.value));
    select.dataset.v9Mode=keep.length?(keep.length===1&&keep[0]==='tesla'?'tesla':'selected'):'all';
    select._v9Redraw?.();
    select.dispatchEvent(new w.Event('change',{bubbles:true}));
  }

  function installPowerTypeFilter(w){
    const operator=w.document.getElementById('simOperatorFilter');if(!operator||w.document.getElementById('simPowerType'))return;
    const host=w.document.createElement('div');host.className='full';
    host.innerHTML='<div><b>Type et puissance de recharge</b><div style="display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-top:6px"><div role="group" aria-label="Type de recharge" style="display:flex;align-items:center;gap:10px;padding-top:21px"><label style="display:flex;align-items:center;gap:5px;margin:0"><input id="simPowerAc" type="checkbox" style="width:auto;margin:0">AC</label><label style="display:flex;align-items:center;gap:5px;margin:0"><input id="simPowerDc" type="checkbox" style="width:auto;margin:0">DC</label></div><div style="flex:1 1 220px"><div style="display:grid;grid-template-columns:1fr 1fr;gap:6px"><label>Minimum (kW)<input id="simMinPowerKw" type="number" min="1" step="1" inputmode="numeric" placeholder="1" aria-label="Puissance minimale en kW" style="width:100%;margin-top:3px"></label><label>Maximum (kW)<input id="simMaxPowerKw" type="number" min="1" step="1" inputmode="numeric" placeholder="250+" aria-label="Puissance maximale en kW" style="width:100%;margin-top:3px"></label></div></div></div><select id="simPowerType" multiple aria-hidden="true" tabindex="-1" style="display:none"><option value="AC">AC</option><option value="DC">DC</option></select><span class="small" style="display:block;margin-top:4px">Aucune case cochée : AC et DC. Laisse les champs vides pour ne pas limiter la puissance.</span></div>';
    const parent=operator.closest('label')||operator.parentElement;parent?.parentElement?.insertBefore(host,parent.nextSibling);
    const select=host.querySelector('#simPowerType'),ac=host.querySelector('#simPowerAc'),dc=host.querySelector('#simPowerDc');
    const sync=()=>{for(const option of [...select.options])option.selected=option.value==='AC'?ac.checked:dc.checked;select.dispatchEvent(new w.Event('change',{bubbles:true}));};
    ac.addEventListener('change',sync);dc.addEventListener('change',sync);
  }

  function installRankingOption(w){
    const select=w.document.getElementById('simRanking');if(!select)return;
    for(const [value,label] of [['costPerKm','Coût au km récupéré'],['totalTime','Temps total trajet + charge']]){
      if([...select.options].some(option=>option.value===value))continue;
      const option=w.document.createElement('option');option.value=value;option.textContent=label;select.appendChild(option);
    }
  }

  function installProgressiveSearchForm(w){
    const grid=w.document.querySelector('#compare .card .grid');
    if(!grid||grid.dataset.v9Progressive==='true')return;
    const field=id=>w.document.getElementById(id)?.parentElement||null;
    const origin=field('simOrigin');if(!origin)return;
    const groups=[
      {title:'Date et horaires',ids:['simDate','simTime','simUnplugTime']},
      {title:'Batterie et objectif',ids:['simNow','simTarget','simCondition','simProfile']},
      {title:'Réseaux affichés',ids:['simOperatorFilter']},
      {title:'Type de recharge',ids:['simPowerType']},
      {title:'Distance maximale',ids:['simMaxDistance']},
      {title:'Priorité de classement',ids:['simRanking']}
    ];
    const captured=groups.map(group=>({group,nodes:group.ids.map(field).filter(Boolean)}));
    const battery=captured.find(row=>row.group.title==='Batterie et objectif');
    if(w.__TCC_V9_SHELL_CONFIG__?.preproductionIsolated===true&&battery){
      for(const [id,label,value,min,max,step] of [
        ['v9BatteryCapacity','Capacité utile de batterie (kWh)',75,10,250,1],
        ['v9Consumption','Consommation (kWh/100 km)',15,5,60,0.1],
        ['v9MaxAc','Puissance AC maximale du véhicule (kW)',11,1,43,1],
        ['v9MaxDc','Puissance DC maximale du véhicule (kW)',250,1,500,1]]){
        const wrapper=w.document.createElement('label');wrapper.textContent=label;
        const input=w.document.createElement('input');input.id=id;input.type='number';input.min=String(min);input.max=String(max);input.step=String(step);input.value=String(value);input.required=true;
        wrapper.appendChild(input);battery.nodes.push(wrapper);
      }
    }
    grid.innerHTML='';origin.classList.add('full');grid.appendChild(origin);
    for(const {group,nodes} of captured){
      if(group.title==='Réseaux affichés'){
        const section=w.document.createElement('section');section.className='full box v9-network-controls';
        const heading=w.document.createElement('b');heading.className='v9-network-heading';heading.textContent=group.title;section.appendChild(heading);
        for(const node of nodes)section.appendChild(node);
        grid.appendChild(section);continue;
      }
      const details=w.document.createElement('details');details.className='full box v9-filter-group';
      const summary=w.document.createElement('summary');summary.textContent=group.title;
      details.appendChild(summary);
      const body=w.document.createElement('div');body.className='grid';body.style.marginTop='10px';
      for(const node of nodes){
        body.appendChild(node);
        if(group.title==='Date et horaires'){
          const input=node.querySelector('input');
          if(input&&['simDate','simTime','simUnplugTime'].includes(input.id)){
            node.style.width='100%';node.style.maxWidth='260px';node.style.minWidth='0';node.style.boxSizing='border-box';
            input.style.setProperty('width','100%','important');
            input.style.setProperty('max-width','260px','important');
            input.style.setProperty('min-width','0','important');
            input.style.setProperty('box-sizing','border-box','important');
          }
        }
      }
      details.appendChild(body);grid.appendChild(details);
    }
    grid.dataset.v9Progressive='true';
  }

  async function waitForStableShell(w,timeoutMs=30000){
    const deadline=Date.now()+timeoutMs;
    while(Date.now()<deadline){
      if(w.__TCC_V9_SHELL_CONFIG__&&typeof w.compare==='function'&&w.document.readyState!=='loading'&&w.document.getElementById('results')&&w.document.getElementById('simOperatorFilter'))return;
      await new Promise(resolve=>setTimeout(resolve,50));
    }
    if(!w.__TCC_V9_SHELL_CONFIG__)throw new Error('shell config unavailable');
    if(typeof w.compare!=='function')throw new Error('stable compare unavailable');
  }
  async function install(w){
    if(w.__TCC_V9_SHELL__?.ready)return w.__TCC_V9_SHELL__;
    if(w.__TCC_V9_SHELL__?.pending)return w.__TCC_V9_SHELL__;
    const cfg=w.__TCC_V9_SHELL_CONFIG__;
    if(!cfg||!['shadow','candidate'].includes(cfg.mode))throw new Error('shell config unavailable');
    const marker={mode:cfg.mode,candidateSha:cfg.observedCandidateSha,engineScopeCountries:(cfg.engineScopeCountries||[]).slice(),fallback:cfg.fallback||'legacy-compare',pending:true};
    w.__TCC_V9_SHELL__=marker;
    await waitForStableShell(w);
    normalizeLegacyChrome(w);
    installV9MobileLayout(w);
    const legacyCompare=w.compare;
    const enginePromise=createEngine(w,cfg);
    const subscriptionCataloguePromise=loadSubscriptionCatalogue(w,cfg);
    installCurrentPositionButton(w);
    installUsageHelpTab(w);
    installPreviewValidation(w,cfg);
    installBaseUpdatesFooter(w,cfg);
    installPowerTypeFilter(w);
    installRankingOption(w);
    installProgressiveSearchForm(w);
    installFloatingNavigation(w);
    bindCongestionToggles(w);
    installOperatorMultiSelect(w);
    w.compare=async function(){
      if(cfg.preproductionIsolated===true){
        for(const id of ['v9BatteryCapacity','v9Consumption','v9MaxAc','v9MaxDc']){
          const field=w.document.getElementById(id);
          if(!field||!field.checkValidity()){
            field?.reportValidity();
            const status=w.document.getElementById('routeStatus');
            if(status)status.textContent='Vérifie les paramètres du véhicule avant de calculer.';
            return null;
          }
        }
      }
      const input=readInputs(w);if(cfg.mode==='shadow'){
      const stable=await legacyCompare.apply(this,arguments);enginePromise.then(engine=>executeV9(w,engine,cfg,input)).then(run=>diagnosticStore(w,{mode:'shadow',outcome:'v9-ok',countryCode:run.countryCode,stationCount:run.area?.stations?.length||0,rankedCount:run.rows.length,sourceErrors:run.area?.diagnostics?.errors?.length||0,routingErrors:run.area?.diagnostics?.routingErrorCount||0,partialRadius:run.partialRadius})).catch(err=>diagnosticStore(w,{mode:'shadow',outcome:'v9-fallback',reason:err.message}));return stable;
    }
      const pendingResults=w.document.getElementById('results');
      if(cfg.preproductionIsolated===true){
        const pendingStatus=w.document.getElementById('routeStatus');
        if(pendingStatus)pendingStatus.textContent='Chargement des stations V9…';
        pendingResults?.setAttribute('aria-busy','true');
      }
      try{const engine=await enginePromise,run=await executeV9(w,engine,cfg,input);refreshOperatorOptions(w,run.area);renderSubscriptionSelector(w,subscriptionOptionsForArea(run.area,run.countryCode,await subscriptionCataloguePromise),run.countryCode,run.area?.stations||[]);renderCandidate(w,run.area,run.rows,run.origin.label||input.originText);
        let currentRun=run;const pageSize=160;const navigateToPage=async page=>{const wasMap=w.document.getElementById('v9MapSummary')?.dataset.v9View==='map';const nextInput={...input,stationOffset:Math.max(0,page*pageSize)};currentRun=await executeV9(w,engine,cfg,nextInput);currentRun.area.navigateToPage=navigateToPage;renderCandidate(w,currentRun.area,currentRun.rows,currentRun.origin.label||input.originText);if(wasMap)w.document.querySelector('.v9-view-map')?.click();return currentRun.area;};run.area.navigateToPage=navigateToPage;const resultsNode=w.document.getElementById('results');resultsNode.onclick=async event=>{const button=event.target.closest('.v9-prev-page,.v9-next-page');if(!button)return;button.disabled=true;try{const delta=button.matches('.v9-prev-page')?-pageSize:pageSize,nextInput={...input,stationOffset:Math.max(0,(Number(currentRun.area?.query?.stationOffset)||0)+delta)};await navigateToPage(nextInput.stationOffset/pageSize);w.document.querySelector('#v9MapSummary')?.scrollIntoView?.({block:'start'});}catch(error){button.disabled=false;diagnosticStore(w,{mode:'candidate',outcome:'pagination-error',reason:error.message});}};diagnosticStore(w,{mode:'candidate',outcome:'v9-ok',countryCode:run.countryCode,stationCount:run.area?.stations?.length||0,rankedCount:run.rows.length,selectedSubscriptionCount:run.selectedSubscriptions.length,sourceErrors:run.area?.diagnostics?.errors?.length||0,routingErrors:run.area?.diagnostics?.routingErrorCount||0});return run.area;}catch(err){
        diagnosticStore(w,{mode:'candidate',outcome:'v9-error',reason:err.message,operatorIds:input.operatorIds||[]});
        if(cfg.preproductionCandidateBase||input.operatorIds?.length){
          const status=w.document.getElementById('routeStatus'),results=w.document.getElementById('results');
          if(status)status.innerHTML='<span class="warn">'+(cfg.preproductionCandidateBase?'Le candidat de préproduction isolé n’a pas pu être chargé.':'Le calcul V9 a échoué pour le filtre opérateur sélectionné.')+'</span>';
          if(results)results.innerHTML='<div class="warn">Les résultats filtrés n’ont pas pu être recalculés : '+esc(err.message||'erreur inconnue')+'. Relance la simulation après vérification de la source.</div>';
          return null;
        }
        return legacyCompare.apply(this,arguments);
      }finally{
        pendingResults?.removeAttribute('aria-busy');
      }
    };
    marker.pending=false;marker.ready=true;
    return marker;
  }
  return{congestionLaneKey,congestionAdjustedTotal,bindCongestionToggles,tariffLaneState,tariffGroupSignature,consistentLaneEvaluation,unverifiedFranceDcPower,guardUnverifiedPowerOffers,displayAmount,verifiedExchangeRates,rankingWeights,rankRows,combineDateTime,dcCurve,readInputs,buildSession,rowsFromArea,groupRows,stationCards,pdcEntries,powerLaneSummary,evseIdentityLabels,renderStationCard,powerLines,formatMinutes,tariffRateLabels,appliedTariffRateLabels,baseTariffsForPower,renderPowerLines,renderTariffs,feeBreakdown,formatCurrencyAmount,stationBaseSource,stationDisplayName,variantsByPower,offerAppliesToEvseGroup,electraPlusOffers,selectedSubscriptions,selectedSubscriptionsForConfig,saveSelectedSubscriptions,subscriptionLabel,subscriptionOptionsForArea,loadSubscriptionCatalogue,renderSubscriptionSelector,renderMapSummary,renderStationLinks,areaFiltersFromInputs,countryQueryMode,variantMatchesFilters,installV9MobileLayout,installCurrentPositionButton,installFloatingNavigation,installOperatorMultiSelect,installPowerTypeFilter,installProgressiveSearchForm,refreshOperatorOptions,operatorRows,executeV9,install};

});
