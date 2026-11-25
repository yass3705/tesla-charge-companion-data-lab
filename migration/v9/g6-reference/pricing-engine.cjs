(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.TCCV9PricingEngine=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const num=v=>{if(v===null||v===undefined||v==='')return null;const n=Number(v);return Number.isFinite(n)?n:null;};
  const money=v=>Math.round((Number(v)+Number.EPSILON)*1000000)/1000000;
  // Monetary rule fields must be interpreted or rejected. A newly archived
  // surcharge cannot silently disappear while the rest of a rule is ranked.
  const knownRuleFields=new Set([
    'afterMinutesCap','afterMinutesCapEnd','afterMinutesCapMode','afterMinutesCapStart',
    'afterMinutesComponent','afterMinutesRate','afterMinutesThreshold','billing',
    'chargePerMinute','chargingTimePerMinuteEur','chargingTimeStepSeconds',
    'congestionStartSoc','congestionThresholdSource','congestionTimePerMinute',
    'congestionTimeStepSeconds','connectedTimeAfterFreeStepSeconds',
    'connectedTimeAfterInitialPerMinuteEur','connectedTimeBlockEur',
    'connectedTimeBlockMinutes','connectedTimeBlockRounding','connectedTimeComponentEur',
    'connectedTimeFreeMinutes','connectedTimeInitialFlatEur','connectedTimeInitialMinutes',
    'connectedTimePerMinuteAfterFreeEur','connectedTimePerMinuteEur',
    'connectedTimeStepSeconds','connectionFee','currency','days','daysOfWeek','end',
    'energyRounding','energyStepWh','excludeHolidays','holidayOnly','idlePerMinute',
    'maxCongestionPct','maxDurationMinutes','maxEnergyKwh','maxPowerKw',
    'maxVehicleSoc','minCongestionPct','minDurationMinutes','minEnergyKwh',
    'minPowerKw','minVehicleSoc','minimumSessionEur','mustEndSameLocalDay',
    'ocpiCongestionDurationBands','ocpiDurationBands','parkingTimeStepSeconds',
    'powerBands','pricePerKwh','pricePerMinute','reservationState','scope',
    'sessionFeeEur','start','validFromDate','validThroughDate'
  ]);
  const billableField=/price|fee|rate|charge|parking|cap|minimum|step|round|tax|vat|surcharge|discount|tier/i;
  function unhandledBillableField(pricing){
    if(pricing?.type==='connected_kerb_midhope_guest_verified'){
      const specialKnown=new Set(['type','verifiedSourceVersion','includesVat',
        'energyPerKwhGbp','parkingPerStarted30minGbp','idleSupplementPerMinuteGbp']);
      return Object.keys(pricing).find(key=>!specialKnown.has(key))||null;
    }
    const topKnown=new Set(['type','currency','timeZone','rules','componentGroups',
      'minimumTotalEur','conditionalSessionFees','postChargeFee','priceSelectionBasis',
      'ocpiFirstMatch','holidayCalendar','incompletePricingReason','verifiedSourceVersion',
      'taxIncluded','longConnectionFee']);
    if(pricing?.type==='kwh'||pricing?.type==='simple')topKnown.add('pricePerKwh');
    for(const key of Object.keys(pricing||{}))
      if(billableField.test(key)&&!topKnown.has(key))return key;
    for(const group of Array.isArray(pricing?.componentGroups)?pricing.componentGroups:[])
      for(const key of Object.keys(group||{}))
        if(billableField.test(key)&&key!=='kind'&&key!=='rules')return key;
    const rules=[...(Array.isArray(pricing?.rules)?pricing.rules:[]),
      ...(Array.isArray(pricing?.componentGroups)?pricing.componentGroups:[])
        .flatMap(group=>Array.isArray(group?.rules)?group.rules:[])];
    for(const rule of rules)for(const key of Object.keys(rule||{}))
      if(billableField.test(key)&&!knownRuleFields.has(key))return key;
    return null;
  }
  // Intl formatters are immutable and expensive to construct. Tariff amounts
  // are never cached; the local clock reading below is keyed by exact instant
  // and time zone, so a changed session date or DST side cannot reuse it.
  const dateFormatters=new Map();
  const localMinutes=new Map();
  function dateFormatter(locale,options){
    const key=JSON.stringify([locale,options]);
    if(dateFormatters.has(key))return dateFormatters.get(key);
    const formatter=new Intl.DateTimeFormat(locale,options);
    if(dateFormatters.size>=64)dateFormatters.delete(dateFormatters.keys().next().value);
    dateFormatters.set(key,formatter);return formatter;
  }
  function offerTimeZone(offer,session={}){
    return offer?.pricing?.timeZone||offer?.metadata?.timeZone||session.stationTimeZone||session.timeZone||null;
  }
  function minuteOfDay(value,timeZone){
    if(typeof value==='number'&&Number.isFinite(value))return ((Math.floor(value)%1440)+1440)%1440;
    const d=value instanceof Date?value:new Date(value);if(Number.isNaN(d.getTime()))return null;
    if(timeZone){
      const key=String(d.getTime())+'|'+String(timeZone);
      if(localMinutes.has(key))return localMinutes.get(key);
      try{
        const parts=dateFormatter('en-GB',{timeZone,hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(d);
        const get=t=>Number(parts.find(p=>p.type===t)?.value||0);
        const minute=get('hour')*60+get('minute')+get('second')/60;
        if(localMinutes.size>=256)localMinutes.delete(localMinutes.keys().next().value);
        localMinutes.set(key,minute);
        return minute;
      }catch(_){return null;}
    }
    return d.getHours()*60+d.getMinutes()+d.getSeconds()/60;
  }
  function localDateParts(value,timeZone){
    const d=value instanceof Date?value:new Date(value);if(Number.isNaN(d.getTime()))return null;
    try{
      if(timeZone){
        const parts=dateFormatter('en-CA',{timeZone,year:'numeric',month:'2-digit',day:'2-digit',weekday:'short'}).formatToParts(d);
        const get=t=>parts.find(p=>p.type===t)?.value;
        const weekdays={Sun:0,Mon:1,Tue:2,Wed:3,Thu:4,Fri:5,Sat:6};
        const weekday=weekdays[get('weekday')];
        const year=Number(get('year')),month=Number(get('month')),day=Number(get('day'));
        if(!Number.isFinite(year)||!Number.isFinite(month)||!Number.isFinite(day)||weekday==null)return null;
        return{year,month,day,weekday,key:`${String(year).padStart(4,'0')}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`};
      }
      return{year:d.getFullYear(),month:d.getMonth()+1,day:d.getDate(),weekday:d.getDay(),key:`${String(d.getFullYear()).padStart(4,'0')}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`};
    }catch(_){return null;}
  }
  function easterSundayUtc(year){
    const a=year%19,b=Math.floor(year/100),c=year%100,d=Math.floor(b/4),e=b%4,f=Math.floor((b+8)/25),g=Math.floor((b-f+1)/3),h=(19*a+b-d-g+15)%30,i=Math.floor(c/4),k=c%4,l=(32+2*e+2*i-h-k)%7,m=Math.floor((a+11*h+22*l)/451),month=Math.floor((h+l-7*m+114)/31),day=((h+l-7*m+114)%31)+1;
    return new Date(Date.UTC(year,month-1,day));
  }
  function italianHolidayKeys(year){
    const fixed=['01-01','01-06','04-25','05-01','06-02','08-15','11-01','12-08','12-25','12-26'].map(md=>`${year}-${md}`);
    const easter=easterSundayUtc(year),monday=new Date(easter.getTime()+86400000);
    fixed.push(`${monday.getUTCFullYear()}-${String(monday.getUTCMonth()+1).padStart(2,'0')}-${String(monday.getUTCDate()).padStart(2,'0')}`);
    return new Set(fixed);
  }
  function isHoliday(calendar,value,timeZone){
    if(!calendar)return false;const p=localDateParts(value,timeZone);if(!p)return null;
    if(String(calendar).toUpperCase()==='IT')return italianHolidayKeys(p.year).has(p.key);
    return false;
  }
  function hm(v,fallback){
    if(!v)return fallback;const m=String(v).match(/^(\d{1,2}):(\d{2})$/);if(!m)return fallback;
    const h=Number(m[1]),min=Number(m[2]);if(h===24&&min===0)return 1440;if(h>23||min>59)return fallback;return h*60+min;
  }
  function ruleContains(rule,minute){
    if(rule?.scope==='allDay')return true;
    const start=hm(rule?.start,0),end=hm(rule?.end,1440);
    if(start===end)return true;
    if(end>start)return minute>=start&&minute<end;
    return minute>=start||minute<end;
  }
  function ruleThresholdStatus(rule,session={},timeZone=null){
    const energy=num(session.energyKwh),power=num(session.powerKw),soc=num(session.vehicleSoc),congestion=num(session.congestionPct),duration=num(session.durationMinutes);
    const bound=(v,min,max)=>{if(min==null&&max==null)return'match';if(v==null)return'unknown';if(min!=null&&v<Number(min))return'no_match';if(max!=null&&v>Number(max))return'no_match';return'match';};
    for(const [v,min,max] of [[energy,rule?.minEnergyKwh,rule?.maxEnergyKwh],[power,rule?.minPowerKw,rule?.maxPowerKw],[duration,rule?.minDurationMinutes,rule?.maxDurationMinutes],[soc,rule?.minVehicleSoc,rule?.maxVehicleSoc],[congestion,rule?.minCongestionPct,rule?.maxCongestionPct]]){const s=bound(v,min,max);if(s!=='match')return s;}
    const reservation=rule?.reservationState;if(reservation!=null){const actual=String(session.reservationState||'').toUpperCase();if(!actual)return'no_match';if(actual!==String(reservation).toUpperCase())return'no_match';}
    const startDate=rule?.validFromDate,endDate=rule?.validThroughDate;if(startDate!=null||endDate!=null){const parts=localDateParts(session.startAt,timeZone||session.timeZone||null);if(!parts)return'unknown';if(startDate!=null&&parts.key<String(startDate))return'no_match';if(endDate!=null&&parts.key>String(endDate))return'no_match';}
    return'match';
  }
  function ruleThresholdMatches(rule,session={},timeZone=null){return ruleThresholdStatus(rule,session,timeZone)==='match';}
  function ruleDayMatches(rule,startAt,timeZone,pricing){
    const rawDays=rule?.daysOfWeek??rule?.days;const days=Array.isArray(rawDays)?rawDays.map(Number).filter(n=>n>=0&&n<=6):null;
    const constrained=Boolean(days?.length||rule?.holidayOnly===true||rule?.excludeHolidays===true);
    if(!constrained)return true;
    if(!startAt)return false;
    const parts=localDateParts(startAt,timeZone);if(!parts)return false;
    const holiday=isHoliday(pricing?.holidayCalendar,startAt,timeZone);
    if(rule?.holidayOnly===true&&holiday!==true)return false;
    if(rule?.excludeHolidays===true&&holiday===true)return false;
    if(days?.length&&!days.includes(parts.weekday))return false;
    return true;
  }
  function tariffRuleHasPositivePrice(rule){
    const fields=['pricePerKwh','pricePerMinute','chargePerMinute','chargingTimePerMinuteEur','connectedTimePerMinuteEur','idlePerMinute','connectionFee','connectedTimeBlockEur','connectedTimeComponentEur','sessionFeeEur','minimumSessionEur','congestionTimePerMinute','afterMinutesRate'];
    return fields.some(key=>(num(rule?.[key])??0)>0)||(Array.isArray(rule?.ocpiDurationBands)&&rule.ocpiDurationBands.some(b=>(num(b?.[3])??0)>0));
  }
  function zeroAllDayPlaceholder(rule){
    if(rule?.scope!=='allDay')return false;
    const fields=['pricePerKwh','pricePerMinute','chargePerMinute','chargingTimePerMinuteEur','connectedTimePerMinuteEur','idlePerMinute','connectionFee','connectedTimeBlockEur','connectedTimeComponentEur','sessionFeeEur','minimumSessionEur','congestionTimePerMinute','afterMinutesRate'];
    const values=fields.map(key=>num(rule?.[key])).filter(value=>value!=null);
    return values.length>0&&values.every(value=>value===0)&&!tariffRuleHasPositivePrice(rule)&&
      !(Array.isArray(rule?.ocpiDurationBands)&&rule.ocpiDurationBands.some(b=>(num(b?.[3])??0)!==0));
  }
  function matchingRuleDetailed(pricing,startAt,timeZone,session={}){
    const rules=Array.isArray(pricing?.rules)?pricing.rules:[];if(!rules.length)return{rule:null,unknown:false};
    const minute=minuteOfDay(startAt,timeZone),candidates=[];
    for(const rule of rules){
      if(minute==null&&rule.scope!=='allDay')continue;
      if(!ruleDayMatches(rule,startAt,timeZone,pricing))continue;
      if(minute!=null&&!ruleContains(rule,minute))continue;
      candidates.push({rule,status:ruleThresholdStatus(rule,session,timeZone)});
    }
    if(pricing?.ocpiFirstMatch===true){
      // Source OCPI price elements are ordered, and the first applicable
      // element wins. Generic offers retain ambiguity protection below.
      for(const candidate of candidates){
        if(candidate.status==='unknown')return{rule:null,unknown:true,reason:'missing_rule_context'};
        if(candidate.status==='match')return{rule:candidate.rule,unknown:false};
      }
      return{rule:null,unknown:false};
    }
    const specificity=rule=>Number(rule?.scope!=='allDay')+Number((rule?.daysOfWeek??rule?.days??[]).length>0)+Number(rule?.holidayOnly===true||rule?.excludeHolidays===true)+Number(rule?.validFromDate!=null||rule?.validThroughDate!=null)+Number(rule?.minDurationMinutes!=null||rule?.maxDurationMinutes!=null)+Number(rule?.minPowerKw!=null||rule?.maxPowerKw!=null);
    candidates.sort((a,b)=>specificity(b.rule)-specificity(a.rule));
    const specificPriced=candidates.some(candidate=>candidate.rule?.scope!=='allDay'&&candidate.status!=='no_match'&&tariffRuleHasPositivePrice(candidate.rule));
    const candidatesInForce=candidates.filter(candidate=>!(specificPriced&&zeroAllDayPlaceholder(candidate.rule)));
    for(const candidate of candidatesInForce){
      if(candidate.status==='unknown')return{rule:null,unknown:true,reason:'missing_rule_context'};
      if(candidate.status!=='match')continue;
      const samePriority=candidatesInForce.filter(row=>row.status==='match'&&specificity(row.rule)===specificity(candidate.rule));
      const signature=rule=>JSON.stringify([
        rule?.pricePerKwh,rule?.pricePerMinute,rule?.chargePerMinute,rule?.chargingTimePerMinuteEur,
        rule?.connectedTimePerMinuteEur,rule?.idlePerMinute,rule?.connectionFee,
        rule?.connectedTimeBlockMinutes,rule?.connectedTimeBlockEur,rule?.sessionFeeEur,
        rule?.minimumSessionEur,rule?.ocpiDurationBands,rule?.powerBands,
        rule?.afterMinutesRate,rule?.afterMinutesThreshold,rule?.afterMinutesComponent,rule?.afterMinutesCap,rule?.afterMinutesCapMode,rule?.afterMinutesCapStart,rule?.afterMinutesCapEnd,
        rule?.congestionTimePerMinute,rule?.congestionStartSoc,rule?.congestionTimeStepSeconds,rule?.ocpiCongestionDurationBands,
        rule?.connectedTimeFreeMinutes,rule?.connectedTimePerMinuteAfterFreeEur,rule?.connectedTimeAfterFreeStepSeconds
      ]);
      if(new Set(samePriority.map(row=>signature(row.rule))).size>1)
        return{rule:null,unknown:true,reason:'ambiguous_overlapping_tariff_rules'};
      return{rule:candidate.rule,unknown:false};
    }
    return{rule:null,unknown:false};
  }
  function matchingRule(pricing,startAt,timeZone,session={}){return matchingRuleDetailed(pricing,startAt,timeZone,session).rule;}

  function minutesUntilRuleBoundary(rule,startAt,timeZone){
    if(!rule)return Infinity;
    const minute=minuteOfDay(startAt,timeZone);if(minute==null)return null;
    let delta=Infinity;
    if(rule.scope!=='allDay'){
      const end=hm(rule.end,1440);delta=end-minute;if(delta<=0)delta+=1440;
    }
    const ruleDays=rule?.daysOfWeek??rule?.days;const daySensitive=Array.isArray(ruleDays)&&ruleDays.length||rule?.holidayOnly===true||rule?.excludeHolidays===true||rule?.mustEndSameLocalDay===true;
    if(daySensitive)delta=Math.min(delta,1440-minute);
    return delta;
  }
  function durationBandRate(rule,dimension,fallback,durationMinutes){
    const seconds=Math.max(0,num(durationMinutes)??0)*60;
    const bands=Array.isArray(rule?.ocpiDurationBands)?rule.ocpiDurationBands:[];
    const matching=bands.filter(b=>String(b?.[0]||'').toUpperCase()===dimension&&seconds>=(num(b?.[1])??0)&&(b?.[2]==null||seconds<(num(b[2])??Infinity)));
    return matching.length===1?(num(matching[0][3])??fallback):fallback;
  }

  // An explicit source threshold takes precedence. Otherwise congestion starts at 80% SOC.
  function congestionBillableMinutes(session={},thresholdSoc=80){
    const threshold=num(thresholdSoc)??80,timeline=Array.isArray(session.chargeTimeline)?session.chargeTimeline:[];
    let above=0;const intervals=[];let firstSoc=num(session.arrivalSoc??session.startSoc),lastSoc=num(session.targetSoc);
    const offset=num(session.congestionSegmentOffsetMinutes),slice=num(session.congestionSegmentDurationMinutes);
    if(timeline.length){
      for(const step of timeline){
        const start=num(step?.startSoc),end=num(step?.endSoc),duration=num(step?.durationMinutes),startAt=num(step?.offsetMinutes);
        if(start==null||end==null||duration==null||startAt==null)return{complete:false,reason:'congestion_soc_timeline_incomplete'};
        if(end<=threshold||duration<=0)continue;
        const thresholdAt=start>=threshold?startAt:end>start?startAt+duration*(threshold-start)/(end-start):startAt;
        const rangeStart=offset==null?thresholdAt:Math.max(thresholdAt,offset);
        const rangeEnd=slice==null?startAt+duration:Math.min(startAt+duration,offset+slice);
        if(rangeEnd>rangeStart){above+=rangeEnd-rangeStart;intervals.push([rangeStart,rangeEnd]);}
      }
      if(lastSoc==null)lastSoc=num(timeline[timeline.length-1]?.endSoc);
    }else{
      const charging=num(session.chargingMinutes);
      if(firstSoc==null||lastSoc==null||charging==null)return{complete:false,reason:'congestion_soc_unavailable'};
      const thresholdAt=firstSoc>=threshold?0:lastSoc>threshold&&lastSoc>firstSoc?charging*(threshold-firstSoc)/(lastSoc-firstSoc):charging;
      const rangeStart=offset==null?thresholdAt:Math.max(thresholdAt,offset);
      const rangeEnd=slice==null?charging:Math.min(charging,offset+slice);
      if(rangeEnd>rangeStart){above+=rangeEnd-rangeStart;intervals.push([rangeStart,rangeEnd]);}
    }
    if(lastSoc==null)return{complete:false,reason:'congestion_final_soc_unavailable'};
    const totalDuration=num(session.durationMinutes);
    const isFinal=offset==null||slice==null||totalDuration==null||offset+slice>=totalDuration-1e-6;
    const parking=lastSoc>=threshold&&isFinal?Math.max(0,num(session.postChargeMinutes)??0):0;
    if(parking>0){const start=num(session.chargingMinutes)??0;intervals.push([start,start+parking]);}
    return{complete:true,minutes:above+parking,chargingMinutes:above,postChargeMinutes:parking,thresholdSoc:threshold,intervals};
  }
  function congestionFee(rule,session={}){
    const rate=num(rule?.congestionTimePerMinute)??0;
    const bands=Array.isArray(rule?.ocpiCongestionDurationBands)?rule.ocpiCongestionDurationBands:[];
    const hasFee=rate>0||bands.some(b=>Array.isArray(b)&&(num(b[2])??0)>0);
    if(!hasFee)return{complete:true,charged:false,totalEur:0};
    if(session.includeCongestionFees===false||session.includeCongestion===false)
      return{complete:true,charged:true,totalEur:0,included:false,thresholdSoc:num(rule?.congestionStartSoc)??80};
    const span=congestionBillableMinutes(session,num(rule?.congestionStartSoc)??80);
    if(!span.complete)return{...span,charged:true};
    if(bands.some(b=>!Array.isArray(b)||b.length<3||(num(b[0])??-1)<0||
      (b[1]!=null&&(num(b[1])??-1)<=b[0])||(num(b[2])??-1)<0))
      return{complete:false,charged:true,reason:'invalid_congestion_duration_band'};
    const rateAt=elapsedSeconds=>{
      const matching=bands.filter(b=>elapsedSeconds+1e-9>=Number(b[0])&&
        (b[1]==null||elapsedSeconds<Number(b[1])-1e-9));
      if(matching.length>1)return null; // genuinely overlapping price bands
      return matching.length?Number(matching[0][2]):rate;
    };
    let cost=0;
    for(const [start,end] of span.intervals||[]){
      const points=[start,end];
      for(const band of bands)for(const raw of [band[0],band[1]]){
        if(raw==null)continue;
        const boundary=Number(raw)/60;
        if(boundary>start+1e-9&&boundary<end-1e-9)points.push(boundary);
      }
      points.sort((a,b)=>a-b);
      for(let i=0;i<points.length-1;i++){
        const a=points[i],b=points[i+1],resolved=rateAt((a+b)*30);
        if(resolved==null)return{complete:false,charged:true,reason:'ambiguous_overlapping_congestion_bands'};
        cost+=(b-a)*resolved;
      }
    }
    const step=num(rule?.congestionTimeStepSeconds);
    if(step>0&&bands.length>0)return{complete:false,charged:true,reason:'congestion_band_rounding_unspecified'};
    const billed=step>0&&span.minutes>0?Math.ceil(span.minutes*60/step)*step/60:span.minutes;
    if(!bands.length)cost=billed*rate;
    return{complete:true,charged:true,ratePerMinute:rate,thresholdSoc:span.thresholdSoc,
      actualMinutes:span.minutes,billableMinutes:billed,chargingMinutes:span.chargingMinutes,
      postChargeMinutes:span.postChargeMinutes,stepSeconds:step??null,
      durationBands:bands.length, included:true,totalEur:money(cost)};
  }
  function evaluateRule(rule,session={}){
    if(rule?.billing==='powerMinute')return{complete:false,reason:'power_minute_requires_full_profile'};
    // Legacy afterMinutesRate is not enough: the source must say whether it
    // applies to charging TIME or idle PARKING_TIME. Do not return an exact
    // amount while silently omitting the surcharge.
    if((num(rule?.afterMinutesRate)??0)>0&&rule?.afterMinutesCap!=null&&
        (num(rule.afterMinutesCap)==null||num(rule.afterMinutesCap)<0))
      return{complete:false,totalEur:null,reason:'after_minutes_invalid_cap_value'};
    if((num(rule?.afterMinutesRate)??0)>0&&!['TIME','PARKING_TIME','CONNECTED_TIME'].includes(rule?.afterMinutesComponent)){
      return{complete:false,totalEur:null,reason:'after_minutes_component_unverified'};
    }
    if((num(rule?.afterMinutesRate)??0)>0&&(num(rule?.afterMinutesCap)??0)>0&&
      session.allowUncappedAfterMinutesForOffer!==true){
      return{complete:false,totalEur:null,reason:'after_minutes_cap_requires_full_session'};
    }
    if((num(rule?.afterMinutesRate)??0)>0){
      if(num(session.durationMinutes)==null)return{complete:false,reason:'duration_required'};
      if(rule.afterMinutesComponent!=='CONNECTED_TIME'&&num(session.chargingMinutes)==null)return{complete:false,reason:'charging_duration_required'};
      if(rule.afterMinutesComponent==='PARKING_TIME'&&num(session.postChargeMinutes)==null)return{complete:false,reason:'post_charge_duration_required'};
    }
    const {energyKwh=0,durationMinutes=0,chargingMinutes=null,tariffDurationMinutes=durationMinutes,postChargeMinutes=0,includeOneTimeFees=true}=session;
    const energy=Math.max(0,num(energyKwh)??0),duration=Math.max(0,num(durationMinutes)??0),charging=Math.max(0,Math.min(duration,num(chargingMinutes)??duration)),components={};let total=0;
    const perKwh=durationBandRate(rule,'ENERGY',num(rule?.pricePerKwh),tariffDurationMinutes);
    if(perKwh!=null){
      const stepWh=num(rule?.energyStepWh);const billedEnergy=stepWh>0&&energy>0?Math.ceil((energy*1000)/stepWh)*stepWh/1000:rule?.energyRounding==='started_kwh'&&energy>0?Math.ceil(energy):energy;
      components.energy=money(billedEnergy*perKwh);total+=components.energy;
      if(billedEnergy!==energy)components.energyBilling={actualKwh:energy,billedKwh:billedEnergy,rounding:stepWh>0?'started_step':'started_kwh',stepWh:stepWh>0?stepWh:undefined};
    }
    const blockMinutes=num(rule?.connectedTimeBlockMinutes),blockEur=num(rule?.connectedTimeBlockEur);
    if(blockMinutes>0&&blockEur!=null){
      const blocks=rule?.connectedTimeBlockRounding==='started_block'?Math.ceil(duration/blockMinutes):duration/blockMinutes;
      components.connectedTimeBlocks={blocks,blockMinutes,unitPriceEur:blockEur,costEur:money(blocks*blockEur)};total+=components.connectedTimeBlocks.costEur;
    }
    const genericPerMinute=num(rule?.pricePerMinute),legacyPerMinute=num(rule?.connectedTimePerMinuteEur),perMinute=genericPerMinute??legacyPerMinute;
    if(perMinute!=null){const step=num(rule?.connectedTimeStepSeconds),billed=step>0&&duration>0?Math.ceil(duration*60/step)*step/60:duration;components.connectedTimePerMinute=money(billed*perMinute);total+=components.connectedTimePerMinute;if(billed!==duration)components.connectedTimeBilling={actualMinutes:duration,billedMinutes:billed,stepSeconds:step};}
    const chargingPerMinute=durationBandRate(rule,'TIME',num(rule?.chargePerMinute)??num(rule?.chargingTimePerMinuteEur),tariffDurationMinutes);if(chargingPerMinute!=null){const step=num(rule?.chargingTimeStepSeconds),billed=step>0&&charging>0?Math.ceil(charging*60/step)*step/60:charging;components.chargingTime=money(billed*chargingPerMinute);total+=components.chargingTime;if(billed!==charging)components.chargingTimeBilling={actualMinutes:charging,billedMinutes:billed,stepSeconds:step};}
    const elapsed=Math.max(0,num(session.elapsedMinutes)??0);
    const afterRate=num(rule?.afterMinutesRate)??0,afterAt=num(rule?.afterMinutesThreshold);
    if(afterRate>0){
      if(afterAt==null||afterAt<0)return{complete:false,totalEur:null,components,reason:'invalid_after_minutes_threshold'};
      const phase=rule.afterMinutesComponent;
      const start=phase==='PARKING_TIME'?elapsed+charging:elapsed;
      const end=phase==='TIME'?elapsed+charging:phase==='PARKING_TIME'?start+Math.max(0,num(session.postChargeMinutes)??0):elapsed+duration;
      const billable=Math.max(0,end-Math.max(start,afterAt));
      const fee=money(billable*afterRate);
      components.afterMinutes={kind:phase,thresholdMinutes:afterAt,ratePerMinute:afterRate,billableMinutes:money(billable),costEur:fee};
      total+=fee;
    }
    const connectionFee=durationBandRate(rule,'FLAT',num(rule?.connectionFee),tariffDurationMinutes);
    if(includeOneTimeFees&&connectionFee!=null&&connectionFee!==0){components.connectionFee=money(connectionFee);total+=components.connectionFee;}
    const parkingRate=durationBandRate(rule,'PARKING_TIME',num(rule?.idlePerMinute),tariffDurationMinutes);
    const parkingMinutes=Math.max(0,num(postChargeMinutes)??0);
    const parkingStep=num(rule?.parkingTimeStepSeconds);
    const billedParking=parkingStep>0&&parkingMinutes>0?Math.ceil(parkingMinutes*60/parkingStep)*parkingStep/60:parkingMinutes;
    if(parkingRate!=null&&parkingRate!==0&&parkingMinutes>0){
      components.parkingTime=money(billedParking*parkingRate);total+=components.parkingTime;
      if(billedParking!==parkingMinutes)components.parkingTimeBilling={actualMinutes:parkingMinutes,billedMinutes:billedParking,stepSeconds:parkingStep};
    }
    const freeMinutes=num(rule?.connectedTimeFreeMinutes),afterFree=num(rule?.connectedTimePerMinuteAfterFreeEur);
    if(freeMinutes!=null&&freeMinutes>=0&&afterFree!=null){
      const actualMinutes=Math.max(0,duration-freeMinutes),step=num(rule?.connectedTimeAfterFreeStepSeconds);
      const billableMinutes=step>0&&actualMinutes>0?Math.ceil(actualMinutes*60/step)*step/60:actualMinutes;
      const costEur=money(billableMinutes*afterFree);
      components.connectedTimeAfterFree={freeMinutes,actualMinutes,billableMinutes,stepSeconds:step>0?step:null,eurPerMinute:afterFree,costEur};total+=costEur;
    }
    const initialMinutes=num(rule?.connectedTimeInitialMinutes),initialFlat=num(rule?.connectedTimeInitialFlatEur),afterInitial=num(rule?.connectedTimeAfterInitialPerMinuteEur);
    if(initialMinutes>0&&initialFlat!=null&&afterInitial!=null&&duration>0){
      const excessMinutes=Math.max(0,duration-initialMinutes),costEur=money(initialFlat+excessMinutes*afterInitial);
      components.connectedTimeInitialTier={initialMinutes,initialFlatEur:initialFlat,excessMinutes,eurPerMinuteAfterInitial:afterInitial,costEur};total+=costEur;
    }
    const fixed=num(rule?.connectedTimeComponentEur);if(includeOneTimeFees&&fixed!=null&&fixed!==0){components.connectedTimeComponent=money(fixed);total+=components.connectedTimeComponent;}
    const sessionFee=num(rule?.sessionFeeEur);if(includeOneTimeFees&&sessionFee!=null&&sessionFee!==0){components.sessionFee=money(sessionFee);total+=components.sessionFee;}
    if((num(rule?.congestionTimePerMinute)??0)>0||(rule?.ocpiCongestionDurationBands||[]).some(b=>(num(b?.[2])??0)>0)){
      const congestion=congestionFee(rule,session);
      if(congestion.complete===false)return{complete:false,reason:congestion.reason,components};
      components.congestionTime=congestion;total+=congestion.totalEur;
    }
    const minimum=num(rule?.minimumSessionEur);if(minimum!=null&&total<minimum){components.minimumSession={minimumEur:minimum,preMinimumTotalEur:money(total),topUpEur:money(minimum-total)};total=minimum;}
    return{totalEur:money(total),components};
  }
  function segmentableRule(rule,wholeSessionMinutes=null){
    if(!rule)return false;
    // Weekday-dependent OCPI time windows are segmentable: the evaluator
    // already splits at local midnight and calls ruleDayMatches again.
    // A weekday list (including seven days) must not make a valid
    // time-of-use tariff incalculable when the session crosses a boundary.
    if(rule.mustEndSameLocalDay===true||rule.holidayOnly===true||rule.excludeHolidays===true)return false;
    // Zero-priced dimensions are not affected by their OCPI rounding step.
    // Keep every *billable* step fail-closed across tariff boundaries: rounding
    // each segment independently would otherwise risk double charging.
    // OCPI duration bands are selected on the WHOLE session duration.
    // A future paid TIME step cannot charge a session below its threshold.
    // Unknown duration or malformed bounds fail closed.
    const hasBands=dimension=>{
      const bands=Array.isArray(rule.ocpiDurationBands)?
        rule.ocpiDurationBands.filter(b=>String(b?.[0]||'').toUpperCase()===dimension):[];
      if(!bands.length)return false;
      const minutes=num(wholeSessionMinutes);
      if(minutes==null||minutes<0)return true;
      const seconds=minutes*60;
      return bands.some(b=>{
        const from=num(b?.[1]),to=b?.[2]==null?Infinity:num(b[2]);
        if(from==null||from<0||to==null||to<=from)return true;
        return seconds>=from&&seconds<to;
      });
    };
    const energyCharge=num(rule.pricePerKwh);
    const timeCharge=num(rule.chargePerMinute)??num(rule.chargingTimePerMinuteEur);
    const billableEnergyStep=num(rule.energyStepWh)>0&&
      ((energyCharge??0)!==0||hasBands('ENERGY'));
    const billableChargingStep=num(rule.chargingTimeStepSeconds)>0&&
      ((timeCharge??0)!==0||hasBands('TIME'));
    const billableParkingStep=num(rule.parkingTimeStepSeconds)>0&&
      ((num(rule.idlePerMinute)??0)!==0||hasBands('PARKING_TIME'));
    if(rule.energyRounding==='started_kwh'||billableEnergyStep||
       num(rule.connectedTimeStepSeconds)>0||billableChargingStep||billableParkingStep)return false;
    if(num(rule.connectedTimeBlockMinutes)>0||num(rule.connectedTimeBlockEur)!=null)return false;
    if(num(rule.connectedTimeFreeMinutes)!=null||num(rule.connectedTimePerMinuteAfterFreeEur)!=null)return false;
    if(num(rule.connectedTimeInitialMinutes)!=null||num(rule.connectedTimeInitialFlatEur)!=null||num(rule.connectedTimeAfterInitialPerMinuteEur)!=null)return false;
    if(num(rule.connectedTimeComponentEur)!=null&&num(rule.connectedTimeComponentEur)!==0)return false;
    if(num(rule.sessionFeeEur)!=null&&num(rule.sessionFeeEur)!==0)return false;
    if(num(rule.minimumSessionEur)!=null)return false;
    return true;
  }
  function addMinutes(value,minutes){
    const d=value instanceof Date?new Date(value.getTime()):new Date(value);if(Number.isNaN(d.getTime()))return null;
    return new Date(d.getTime()+Number(minutes||0)*60000);
  }
  function invariantBillableStepRule(pricing,session,timeZone){
    // One all-day, seven-day rule cannot change price at the clock boundary.
    // In that narrow case, evaluate all rounded dimensions once on the FULL
    // charging session rather than independently rounding midnight slices.
    const rules=Array.isArray(pricing?.rules)?pricing.rules:[];
    if(rules.length!==1)return null;
    const rule=rules[0];
    if(!rule)return null;
    const wholeClock=rule.scope==='allDay'||
      (rule.scope==='timeWindow'&&hm(rule.start,0)===0&&hm(rule.end,1440)===1440);
    if(!wholeClock||rule.mustEndSameLocalDay===true||rule.holidayOnly===true||
       rule.excludeHolidays===true||rule.validFromDate!=null||rule.validThroughDate!=null)return null;
    const days=rule.daysOfWeek??rule.days;
    if(Array.isArray(days)&&days.length>0&&
       !(days.length===7&&new Set(days.map(Number)).size===7&&
         days.every(day=>Number.isInteger(Number(day))&&Number(day)>=0&&Number(day)<=6)))return null;
    const hasBands=dimension=>Array.isArray(rule.ocpiDurationBands)&&
      rule.ocpiDurationBands.some(b=>String(b?.[0]||'').toUpperCase()===dimension);
    const paidTime=num(rule.chargingTimeStepSeconds)>0&&
      ((num(rule.chargePerMinute)??num(rule.chargingTimePerMinuteEur)??0)!==0||hasBands('TIME'));
    const paidEnergy=num(rule.energyStepWh)>0&&
      ((num(rule.pricePerKwh)??0)!==0||hasBands('ENERGY'));
    if(!paidTime&&!paidEnergy)return null;
    return matchingRule(pricing,session.startAt,timeZone,session)===rule?rule:null;
  }
  function evaluateSegmentedRules(pricing,session={},timeZone=null){
    const duration=Math.max(0,num(session.durationMinutes)??0),energy=Math.max(0,num(session.energyKwh)??0),charging=Math.max(0,Math.min(duration,num(session.chargingMinutes)??duration)),postCharge=Math.max(0,num(session.postChargeMinutes)??0);
    if(!session.startAt)return{complete:false,reason:'segmentation_requires_start_time'};
    const invariant=duration>0?invariantBillableStepRule(pricing,session,timeZone):null;
    if(invariant){
      const evaluated=evaluateRule(invariant,{...session,tariffDurationMinutes:duration,includeOneTimeFees:true});
      if(evaluated.complete===false)return evaluated;
      return{complete:true,totalEur:evaluated.totalEur,components:{segmentedPricing:{
        wholeSessionSingleRule:true,totalEur:evaluated.totalEur,
        segments:[{startAt:new Date(session.startAt).toISOString(),durationMinutes:duration,
          chargingMinutes:charging,energyKwh:energy,totalEur:evaluated.totalEur,
          components:evaluated.components,rule:invariant}]
      }}};
    }
    if(duration<=0){
      const rule=matchingRule(pricing,session.startAt,timeZone,session);if(!rule)return{complete:false,reason:'no_matching_time_rule'};
      if(!segmentableRule(rule,duration))return{complete:false,reason:'tariff_window_crossing_unsupported_components'};
      const evaluated=evaluateRule(rule,{...session,energyKwh:energy,durationMinutes:0,tariffDurationMinutes:duration,postChargeMinutes:session.postChargeMinutes});
      if(evaluated.complete===false)return evaluated;
      return{complete:true,totalEur:evaluated.totalEur,components:{segmentedPricing:{segments:[{startAt:new Date(session.startAt).toISOString(),durationMinutes:0,energyKwh:energy,totalEur:evaluated.totalEur,rule}]}}};
    }
    if(postCharge>duration-charging+1e-9)return{complete:false,reason:'post_charge_duration_exceeds_session'};
    let elapsed=0,total=0;const segments=[];
    while(elapsed<duration-1e-9){
      const at=addMinutes(session.startAt,elapsed);if(!at)return{complete:false,reason:'invalid_segmentation_start_time'};
      const rule=matchingRule(pricing,at,timeZone,session);if(!rule)return{complete:false,reason:'no_matching_time_rule',segmentStartAt:at.toISOString()};
      let boundary=minutesUntilRuleBoundary(rule,at,timeZone);if(boundary==null)return{complete:false,reason:'unresolved_tariff_boundary'};
      if(!Number.isFinite(boundary))boundary=duration-elapsed;
      const slice=Math.min(duration-elapsed,Math.max(boundary,1e-6));
      const blockMinutes=num(rule.connectedTimeBlockMinutes),blockAmount=num(rule.connectedTimeBlockEur);
      const hasConnectedBlocks=blockMinutes>0&&blockAmount!=null;
      const baseRule=hasConnectedBlocks?{...rule,connectedTimeBlockMinutes:null,connectedTimeBlockEur:null}:rule;
      if(!segmentableRule(baseRule,duration))return{complete:false,reason:'tariff_window_crossing_unsupported_components',segmentStartAt:at.toISOString(),matchedRule:rule};
      if(hasConnectedBlocks&&rule.connectedTimeBlockRounding!=='started_block')
        return{complete:false,reason:'connected_block_rounding_unverified',segmentStartAt:at.toISOString()};
      // A tariff change inside a started block has no proved allocation rule.
      // Exact block-aligned slices can be evaluated without resetting a block.
      if(hasConnectedBlocks&&
          Math.abs(slice/blockMinutes-Math.round(slice/blockMinutes))>1e-9)
        return{complete:false,reason:'connected_block_crosses_tariff_boundary_ambiguous',segmentStartAt:at.toISOString()};
      const chargeOverlap=Math.max(0,Math.min(charging,elapsed+slice)-elapsed),segmentEnergy=charging>0?energy*(chargeOverlap/charging):0;
      const postChargeOverlap=Math.max(0,Math.min(elapsed+slice,charging+postCharge)-Math.max(elapsed,charging));
      const evaluated=evaluateRule(rule,{...session,energyKwh:segmentEnergy,durationMinutes:slice,chargingMinutes:chargeOverlap,tariffDurationMinutes:duration,postChargeMinutes:postChargeOverlap,includeOneTimeFees:elapsed===0,elapsedMinutes:elapsed,congestionSegmentOffsetMinutes:elapsed,congestionSegmentDurationMinutes:slice});
       if(evaluated.complete===false)return evaluated;
      total+=evaluated.totalEur;
      segments.push({startAt:at.toISOString(),durationMinutes:money(slice),chargingMinutes:money(chargeOverlap),energyKwh:money(segmentEnergy),totalEur:evaluated.totalEur,components:evaluated.components,rule});
      elapsed+=slice;
      if(segments.length>96)return{complete:false,reason:'tariff_segmentation_guard'};
    }
    return{complete:true,totalEur:money(total),components:{segmentedPricing:{segments,totalEur:money(total)}}};
  }
  function evaluateConditionalSessionFees(fees,session={}){
    if(fees==null)return{complete:true,totalEur:0,component:null};
    if(!Array.isArray(fees))return{complete:false,totalEur:0,component:null,reason:'invalid_conditional_session_fees'};
    const energy=Math.max(0,num(session.energyKwh)??0),duration=Math.max(0,num(session.durationMinutes)??0),items=[];let total=0;
    for(const fee of fees){
      const amount=num(fee?.amountEur),conditions=fee?.conditions;
      if(amount==null||amount<0||!Array.isArray(conditions)||!conditions.length)return{complete:false,totalEur:0,component:null,reason:'invalid_conditional_session_fee'};
      let applies=true;const evaluated=[];
      for(const condition of conditions){
        const threshold=num(condition?.value);if(threshold==null||threshold<0)return{complete:false,totalEur:0,component:null,reason:'invalid_conditional_fee_threshold'};
        let matched=false,detail=null;
        if(condition?.kind==='energy_above_kwh'){
          if(num(session.energyKwh)==null)
            return{complete:false,totalEur:0,component:null,reason:'conditional_fee_energy_required'};
          matched=energy>threshold;detail={kind:'energy_above_kwh',value:threshold,actualEnergyKwh:energy,matched};
        }else if(condition?.kind==='session_duration_after_minutes'){
          if(num(session.durationMinutes)==null)
            return{complete:false,totalEur:0,component:null,reason:'conditional_fee_duration_required'};
          matched=duration>threshold;detail={kind:'session_duration_after_minutes',value:threshold,actualDurationMinutes:duration,matched};
        }else return{complete:false,totalEur:0,component:null,reason:'unsupported_conditional_fee_condition',conditionKind:condition?.kind||null};
        evaluated.push(detail);if(!matched)applies=false;
      }
      const costEur=applies?money(amount):0;if(applies)total+=costEur;
      items.push({amountEur:amount,applied:applies,costEur,conditions:evaluated});
    }
    return{complete:true,totalEur:money(total),component:{fees:items,costEur:money(total)}};
  }
  function exemptWindowContains(window,minute){
    const start=hm(window?.start,null),end=hm(window?.end,null);if(start==null||end==null)return false;
    if(start===end)return true;
    if(end>start)return minute>=start&&minute<end;
    return minute>=start||minute<end;
  }
  function postChargeBillableMinutes(fee,{postChargeMinutes=0,postChargeStartAt=null}={},timeZone=null){
    const duration=Math.max(0,num(postChargeMinutes)??0),grace=Math.max(0,num(fee?.graceMinutes)??0),afterGrace=Math.max(0,duration-grace);
    if(fee?.exemptLocalWindows!=null&&!Array.isArray(fee.exemptLocalWindows))
      return{complete:false,reason:'invalid_post_charge_exemption_window',duration,grace,afterGrace};
    const windows=Array.isArray(fee?.exemptLocalWindows)?fee.exemptLocalWindows:[];
    if(windows.some(window=>hm(window?.start,null)==null||hm(window?.end,null)==null))
      return{complete:false,reason:'invalid_post_charge_exemption_window',duration,grace,afterGrace};
    if(afterGrace<=0)return{complete:true,duration,grace,afterGrace,billableMinutes:0,exemptMinutes:0};
    if(!windows.length)return{complete:true,duration,grace,afterGrace,billableMinutes:afterGrace,exemptMinutes:0};
    if(!timeZone)return{complete:false,reason:'post_charge_exemption_requires_time_zone',duration,grace,afterGrace};
    if(!postChargeStartAt)return{complete:false,reason:'post_charge_exemption_requires_start_time',duration,grace,afterGrace};
    const start=new Date(postChargeStartAt);if(Number.isNaN(start.getTime()))return{complete:false,reason:'invalid_post_charge_start_time',duration,grace,afterGrace};
    const billableStartMs=start.getTime()+grace*60000;let remaining=afterGrace,offset=0,billable=0,exempt=0;
    while(remaining>1e-9){
      const slice=Math.min(1,remaining),mid=new Date(billableStartMs+(offset+slice/2)*60000),minute=minuteOfDay(mid,timeZone);
      if(minute==null)return{complete:false,reason:'post_charge_exemption_timezone_unresolved',duration,grace,afterGrace};
      if(windows.some(w=>exemptWindowContains(w,minute)))exempt+=slice;else billable+=slice;
      remaining-=slice;offset+=slice;
    }
    return{complete:true,duration,grace,afterGrace,billableMinutes:money(billable),exemptMinutes:money(exempt)};
  }
  function evaluatePostChargeFee(fee,session={},timeZone=null){
    if(!fee)return{totalEur:0,component:null};
    if(fee.localRateWindows!=null&&!Array.isArray(fee.localRateWindows))
      return{complete:false,totalEur:0,component:null,reason:'invalid_post_charge_rate_windows'};
    if(num(session.postChargeMinutes)==null)
      return{complete:false,totalEur:0,component:null,reason:'post_charge_duration_required'};
    const charging=num(session.chargingMinutes),started=new Date(session.startAt||'');
    const derivedStart=!session.postChargeStartAt&&charging!=null&&charging>=0&&
      !Number.isNaN(started.getTime())?new Date(started.getTime()+charging*60000).toISOString():null;
    const span=postChargeBillableMinutes(fee,{...session,
      postChargeStartAt:session.postChargeStartAt||derivedStart},timeZone);
    if(span.complete===false)return{totalEur:0,component:null,complete:false,reason:span.reason};
    const duration=span.duration,grace=span.grace,billable=span.billableMinutes,exemptMinutes=span.exemptMinutes;
    const baseComponent={postChargeMinutes:duration,graceMinutes:grace,billableMinutes:billable,exemptMinutes,costEur:0};
    if(billable<=0)return{totalEur:0,component:baseComponent};
    if(Array.isArray(fee.localRateWindows)){
      if(!timeZone)
        return{complete:false,totalEur:0,component:null,reason:'post_charge_rate_windows_require_time_zone'};
      if(Array.isArray(fee.exemptLocalWindows)&&fee.exemptLocalWindows.length)
        return{complete:false,totalEur:0,component:null,reason:'post_charge_rate_and_exemption_windows_conflict'};
      const windows=fee.localRateWindows;
      if(!windows.length||windows.some(w=>hm(w?.start,null)==null||hm(w?.end,null)==null||
        num(w?.eurPerMinute)==null||num(w.eurPerMinute)<0))
        return{complete:false,totalEur:0,component:null,reason:'invalid_post_charge_rate_windows'};
      const explicit=session.postChargeStartAt;
      const charging=num(session.chargingMinutes),start=new Date(session.startAt||'');
      const derived=!explicit&&charging!=null&&charging>=0&&!Number.isNaN(start.getTime())
        ?new Date(start.getTime()+charging*60000):null;
      const postStart=new Date(explicit||derived||'');
      if(Number.isNaN(postStart.getTime()))
        return{complete:false,totalEur:0,component:null,reason:'post_charge_rate_windows_require_start_time'};
      const minuteCount=Math.ceil(billable-1e-9);
      if(minuteCount>10080)
        return{complete:false,totalEur:0,component:null,reason:'post_charge_duration_out_of_range'};
      const billableStart=postStart.getTime()+grace*60000,used=new Map();let total=0;
      const matchingRate=instant=>{
        const minute=minuteOfDay(new Date(instant),timeZone);
        if(minute==null)return null;
        const matches=windows.filter(w=>exemptWindowContains(w,minute));
        return matches.length===1?matches[0]:null;
      };
      for(let i=0;i<minuteCount;i++){
        const from=billableStart+i*60000,to=from+Math.min(1,billable-i)*60000;
        const first=matchingRate(from),last=matchingRate(Math.max(from,to-1));
        if(!first||!last||first!==last)
          return{complete:false,totalEur:0,component:null,reason:'post_charge_rate_boundary_within_started_minute'};
        const rate=num(first.eurPerMinute);
        total+=rate;
        const key=`${first.start}|${first.end}|${rate}`;
        const item=used.get(key)||{start:first.start,end:first.end,eurPerMinute:rate,billedMinutes:0,costEur:0};
        item.billedMinutes+=1;item.costEur=money(item.billedMinutes*rate);used.set(key,item);
      }
      const costEur=money(total);
      return{totalEur:costEur,component:{...baseComponent,billedStartedMinutes:minuteCount,
        appliedRateWindows:[...used.values()],costEur}};
    }
    const blockMinutes=num(fee.blockMinutes),blockEur=num(fee.blockEur);
    if(blockMinutes>0&&blockEur!=null){
      const blocks=fee.rounding==='started_block'?Math.ceil(billable/blockMinutes):billable/blockMinutes,costEur=money(blocks*blockEur);
      return{totalEur:costEur,component:{...baseComponent,blocks,blockMinutes,unitPriceEur:blockEur,costEur}};
    }
    const perMinute=num(fee.eurPerMinute);if(perMinute!=null){const costEur=money(billable*perMinute);return{totalEur:costEur,component:{...baseComponent,eurPerMinute:perMinute,costEur}};}
    return{totalEur:0,component:null,complete:false,reason:'unsupported_post_charge_fee'};
  }
  function applyMinimumTotal(pricing,total,components){
    const minimum=num(pricing?.minimumTotalEur);if(minimum==null||total>=minimum)return{totalEur:money(total),components};
    const topUp=money(minimum-total);return{totalEur:money(minimum),components:{...components,minimumTotal:{minimumEur:minimum,preMinimumTotalEur:money(total),topUpEur:topUp}}};
  }
  function evaluateComponentGroups(pricing,session={},timeZone=null){
    const groups=Array.isArray(pricing?.componentGroups)?pricing.componentGroups:[];if(!groups.length)return{complete:false,reason:'missing_component_groups'};
    let total=0,matchedGroups=0;const components={componentGroups:[]};
    for(const group of groups){
      const rules=Array.isArray(group?.rules)?group.rules:[];if(!rules.length)continue;
      const localPricing={...pricing,rules};const match=matchingRuleDetailed(localPricing,session.startAt,timeZone,session);if(match.unknown)return{complete:false,reason:match.reason,componentKind:group.kind||null};const rule=match.rule;
      if(!rule){components.componentGroups.push({kind:group.kind||null,matched:false,costEur:0});continue;}
      matchedGroups++;
      // OCPI first-match time windows must be evaluated across the ENTIRE
      // charging session. A session-start-only price is never sufficient
      // when the tariff changes mid-session.
      const duration=Math.max(0,num(session.durationMinutes)??0);
      const boundary=pricing?.ocpiFirstMatch===true&&session.startAt?
        minutesUntilRuleBoundary(rule,session.startAt,timeZone):Infinity;
      const mustSegment=boundary!=null&&Number.isFinite(boundary)&&duration>boundary+1e-9;
      if(mustSegment&&(num(session.postChargeMinutes)??0)>0)
        return{complete:false,reason:'ocpi_post_charge_cross_window_requires_independent_segmentation',componentKind:group.kind||null};
      const evaluated=mustSegment?evaluateSegmentedRules(localPricing,session,timeZone):evaluateRule(rule,session);
      if(evaluated.complete===false)return{...evaluated,componentKind:group.kind||null};
      total+=evaluated.totalEur;
      components.componentGroups.push({kind:group.kind||null,matched:true,costEur:evaluated.totalEur,components:evaluated.components,rule,segmented:mustSegment});
    }
    if(matchedGroups===0)return{complete:false,reason:'no_matching_tariff_component',components};
    return{complete:true,totalEur:money(total),components};
  }
  // Verified Connected Kerb Midhope guest tariff: parking is a single
  // continuous occupancy charge whether the connector is charging or idle.
  // An independent idle supplement is added ONLY for not-charging minutes.
  // This isolated type must not alter OCPI first-match semantics elsewhere.
  function evaluateVerifiedMidhope(offer,session={}){
    const p=offer?.pricing||{},meta=offer?.metadata||{},timeZone='Europe/London';
    const fail=reason=>({complete:false,reason,offerId:offer?.id||null,currency:'GBP',timeZone});
    if(p.type!=='connected_kerb_midhope_guest_verified'||meta.pricingScope!=='cpo_direct_guest_exact_connector')return fail('unverified_midhope_source');
    const verifiedSockets={
      'GB*CK0*E19825':'a46c9e98-5d68-4025-989a-ab416d7ab670',
      'GB*CK0*E19865':'d19e0ae8-1424-40d8-ae9a-b13fe6704484',
      'GB*CK0*E19716':'f02dbb6d-7fcb-4dd0-8f51-1a27111ab5b0',
      'GB*CK0*E19707':'9a1d7557-d59c-4e95-a929-b667d73843f0'
    };
    if(offer.currency!=='GBP'||meta.sourceEvidence!=='midhope-guest-2026-10-10'||
       !Array.isArray(offer.evseIds)||offer.evseIds.length!==1||
       meta.connectorId!==verifiedSockets[offer.evseIds[0]]||
       !Array.isArray(offer.stationIds)||offer.stationIds.length!==1||
       offer.stationIds[0]!=='cd20ba89-4241-4b39-b738-514f49093e8d')
      return fail('midhope_connector_provenance_missing');
    if(!session.startAt||typeof session.startAt!=='string'||!(/Z$|[+-]\d\d:\d\d$/.test(session.startAt)))return fail('midhope_requires_absolute_start');
    const start=new Date(session.startAt),startMs=start.getTime();
    if(!Number.isFinite(startMs)||start.getUTCSeconds()!==0||start.getUTCMilliseconds()!==0)return fail('midhope_requires_minute_aligned_start');
    const energy=num(session.energyKwh),duration=num(session.durationMinutes);
    const charging=num(session.chargingMinutes)??duration;
    const after=num(session.postChargeMinutes)??0;
    if([energy,duration,charging,after].some(v=>v==null||v<0||!Number.isInteger(v))||charging>duration||
       (energy>0&&charging===0))return fail('midhope_requires_explicit_valid_session_durations');
    // The pinned historical oracle uses total occupancy for durationMinutes;
    // the current UI uses charging occupancy plus a separate post-charge span.
    // Accept either only when the explicit parts make the basis unambiguous.
    if(after>0&&duration!==charging&&duration!==charging+after)
      return fail('midhope_ambiguous_session_duration');
    const occupied=duration===charging?duration+after:duration,idle=occupied-charging;
    if(occupied>1440)return fail('midhope_session_exceeds_verified_max_duration');
    const per30=num(p.parkingPerStarted30minGbp),rate=num(p.energyPerKwhGbp),idleRate=num(p.idleSupplementPerMinuteGbp);
    if(p.verifiedSourceVersion!=='2026-10-10-midhope-exact-4'||!p.includesVat||
       per30==null||Math.abs(per30-0.80004)>1e-8||
       rate==null||Math.abs(rate-0.39996)>1e-8||
       idleRate==null||Math.abs(idleRate-0.01)>1e-8)return fail('midhope_unverified_tariff_values');
    // Guest-app 09:30-19:00 Europe/Paris is 08:30-18:00 Europe/London
    // both before and after DST. Revalidate changes in tariffs separately.
    if(startMs<Date.parse('2026-10-10T00:00:00Z'))return fail('midhope_before_observed_tariff');
    const fmt=dateFormatter('en-GB',{timeZone,weekday:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
    const weekdays=new Set(['Mon','Tue','Wed','Thu','Fri','Sat']);
    let paidRun=0,parkingBlocks=0,paidMinutes=0;
    const segments=[];
    for(let i=0;i<occupied;i++){
      const at=new Date(startMs+i*60000),fields=fmt.formatToParts(at);
      const get=t=>fields.find(x=>x.type===t)?.value;
      const minute=Number(get('hour'))*60+Number(get('minute'));
      const active=weekdays.has(get('weekday'))&&minute>=8*60+30&&minute<18*60;
      if(active){paidRun++;paidMinutes++;}
      if(!active||i===occupied-1){
        if(paidRun){
          const blocks=Math.ceil(paidRun/30);parkingBlocks+=blocks;
          segments.push({billableMinutes:paidRun,startedHalfHourBlocks:blocks,costGbp:money(blocks*per30)});
          paidRun=0;
        }
      }
    }
    const energyGbp=money(energy*rate),parkingGbp=money(parkingBlocks*per30),
      idleGbp=money(idle*idleRate),total=money(energyGbp+parkingGbp+idleGbp);
    return{complete:true,totalEur:total,currency:'GBP',offerId:offer?.id||null,timeZone,
      segmented:segments.length>1,components:{
        energy:energyGbp,parkingTime:{costGbp:parkingGbp,paidMinutes,startedHalfHourBlocks:parkingBlocks,segments},
        idleSupplement:{costGbp:idleGbp,idleMinutes:idle,rateGbpPerMinute:idleRate},
        guestPreAuthorisation:{amountGbp:25,includedInTotal:false},
        sourcePriceBasis:'GBP including VAT, user screenshot and exact guest socket tariff'
      }};
  }
  // Apply a verified duration surcharge cap to the full session, not per tariff
  // segment. No inferred cap schedule, currency conversion or source contract.
  function evaluateAfterMinutesCap(rule,session={},timeZone=null){
    const rate=num(rule?.afterMinutesRate),threshold=num(rule?.afterMinutesThreshold);
    const cap=num(rule?.afterMinutesCap),mode=rule?.afterMinutesCapMode;
    const duration=num(session?.durationMinutes);
    if(rate==null||rate<=0||threshold==null||threshold<0||cap==null||cap<=0||
        duration==null||duration<0||duration>10080)
      return{complete:false,reason:'after_minutes_invalid_cap_context'};
    if(String(rule?.currency||'EUR').toUpperCase()!=='EUR')
      return{complete:false,reason:'after_minutes_cap_currency_unverified'};
    if(rule.afterMinutesComponent!=='CONNECTED_TIME')
      return{complete:false,reason:'after_minutes_cap_component_requires_source_review'};
    if(mode==='whole_session'&&
       (!rule.afterMinutesCapStart||rule.afterMinutesCapStart==='00:00')&&
       (!rule.afterMinutesCapEnd||rule.afterMinutesCapEnd==='24:00')){
      const cost=money(Math.min(cap,Math.max(0,duration-threshold)*rate));
      return{complete:true,costEur:cost,mode,chargedMinutes:money(Math.max(0,duration-threshold))};
    }
    if(mode!=='night_window_local_per_night')
      return{complete:false,reason:'after_minutes_cap_window_requires_source_confirmation'};
    if(!timeZone||!session.startAt)
      return{complete:false,reason:'after_minutes_cap_requires_timezone_and_start'};
    const from=hm(rule.afterMinutesCapStart,null),to=hm(rule.afterMinutesCapEnd,null);
    if(from==null||to==null||from<=to||from===to)
      return{complete:false,reason:'after_minutes_cap_invalid_night_window'};
    const start=new Date(session.startAt);
    if(Number.isNaN(start.getTime()))return{complete:false,reason:'after_minutes_invalid_start_date'};
    const fmt=dateFormatter('en-CA',{timeZone,year:'numeric',month:'2-digit',day:'2-digit'});
    let daytime=0,chargedMinutes=0,nightMinutes=0;
    const nightTotals=new Map();
    for(let elapsed=threshold;elapsed<duration-1e-9;){
      const atMs=start.getTime()+elapsed*60000;
      const untilMinute=(60000-((atMs%60000)+60000)%60000)/60000;
      const slice=Math.min(untilMinute,duration-elapsed);
      const at=new Date(start.getTime()+(elapsed+slice/2)*60000);
      const minute=minuteOfDay(at,timeZone);
      if(minute==null)return{complete:false,reason:'after_minutes_invalid_timezone'};
      const cost=slice*rate;chargedMinutes+=slice;
      if(minute>=from||minute<to){
        const dateParts=fmt.formatToParts(at);
        const get=n=>Number(dateParts.find(p=>p.type===n)?.value);
        const date=new Date(Date.UTC(get('year'),get('month')-1,get('day')-(minute<to?1:0))).toISOString().slice(0,10);
        nightTotals.set(date,(nightTotals.get(date)||0)+cost);
        nightMinutes+=slice;
      }else daytime+=cost;
      elapsed+=slice;
    }
    const nights=[...nightTotals.values()].reduce((a,v)=>a+Math.min(cap,v),0);
    return{complete:true,costEur:money(daytime+nights),mode,chargedMinutes:money(chargedMinutes),
      nightMinutes:money(nightMinutes),nightWindowCount:nightTotals.size,
      uncappedCostEur:money(chargedMinutes*rate)};
  }
  // Restored from the archived 2026-10-10 Tesla extension. Split at exact
  // delivered-power and tariff boundaries, not at sampled minute midpoints.
  function evaluatePowerMinute(offer,session,timeZone){
    const pricing=offer.pricing,rules=pricing.rules;
    const fail=reason=>({complete:false,reason,offerId:offer.id||null,timeZone});
    if(rules.some(r=>r.billing!=='powerMinute'))return fail('mixed_power_minute_billing_modes');
    const duration=num(session.chargingMinutes),start=new Date(session.startAt||'');
    if(duration==null||duration<0||duration>10080||Number.isNaN(start.getTime())||!timeZone)
      return fail('power_minute_requires_duration_start_timezone');
    const source=session.powerSegments??session.chargeTimeline;
    if(duration>0&&(!Array.isArray(source)||!source.length))return fail('delivered_power_curve_required');
    const rows=(source||[]).map(row=>{
      const a=num(row.startMin??row.offsetMinutes),d=num(row.durationMinutes);
      return{start:a,end:num(row.endMin)??(a!=null&&d!=null?a+d:null),power:num(row.powerKw)};
    }).sort((a,b)=>a.start-b.start);
    // The archived charge model rounds every offset and duration to 1e-6 min.
    // Reconcile only that serialization noise; material gaps still fail closed.
    const curvePrecision=2e-6;
    let cursor=0;
    for(const row of rows){
      if(row.start==null||row.end==null||row.power==null||row.power<0||row.end<=row.start||Math.abs(row.start-cursor)>curvePrecision)
        return fail('delivered_power_curve_gap_or_overlap');
      row.start=cursor;
      cursor=row.end;
    }
    if(Math.abs(cursor-duration)>curvePrecision)return fail('delivered_power_curve_duration_mismatch');
    for(const rule of rules){
      if(!Array.isArray(rule.powerBands)||!rule.powerBands.length||rule.powerBands.some(b=>
        num(b.minKw)==null||num(b.maxKw)==null||num(b.ratePerMinute)==null||b.minKw<0||b.maxKw<=b.minKw||b.ratePerMinute<0))
        return fail('invalid_power_minute_bands');
    }
    const minimums=[...new Set(rules.map(r=>num(r.minimumSessionEur)))];
    if(minimums.length>1)return fail('power_minute_varying_minimum_unverified');
    const clean=rules.map(rule=>{
      const r={...rule,billing:'kwh',minimumSessionEur:null};
      for(const key of ['powerBands','pricePerMinute','chargePerMinute','chargingTimePerMinuteEur','connectedTimePerMinuteEur'])delete r[key];
      return r;
    });
    const base=evaluateOffer({...offer,pricing:{...pricing,rules:clean,minimumTotalEur:null}},session);
    if(!base.complete)return base;
    let total=0;const segments=[];
    for(const row of rows){
      let offset=row.start;
      while(offset<row.end-1e-9){
        const at=new Date(start.getTime()+offset*60000);
        const selected=pricing.priceSelectionBasis==='session_start_local_time'?start:at;
        const match=matchingRuleDetailed(pricing,selected,timeZone,session);
        if(match.unknown||!match.rule)return fail(match.reason||'power_minute_tariff_missing');
        const rule=match.rule,maximum=Math.max(...rule.powerBands.map(b=>Number(b.maxKw)));
        const bands=rule.powerBands.filter(b=>row.power>=b.minKw&&(row.power<b.maxKw||(row.power===maximum&&b.maxKw===maximum)));
        if(bands.length!==1)return fail('delivered_power_outside_or_overlapping_bands');
        const boundary=pricing.priceSelectionBasis==='session_start_local_time'?Infinity:minutesUntilRuleBoundary(rule,at,timeZone);
        if(boundary==null||boundary<=0)return fail('power_minute_tariff_boundary_unresolved');
        const slice=Math.min(row.end-offset,boundary),rate=Number(bands[0].ratePerMinute);
        total+=slice*rate;
        segments.push({offsetMinutes:offset,durationMinutes:slice,powerKw:row.power,ratePerMinute:rate,costNative:money(slice*rate)});
        offset+=slice;if(segments.length>4096)return fail('power_minute_segmentation_guard');
      }
    }
    const amount=money(total),components={...base.components,powerMinute:{costEur:amount,costNative:amount,
      currency:offer.currency,chargingMinutes:duration,segments,estimatedFromChargeCurve:!session.powerSegments}};
    let combined=money(base.totalEur+amount);
    if(minimums[0]!=null&&combined<minimums[0]){
      components.minimumSession={minimumEur:minimums[0],preMinimumTotalEur:combined,topUpEur:money(minimums[0]-combined)};combined=minimums[0];
    }
    const finalized=applyMinimumTotal(pricing,combined,components);
    return{...base,totalEur:finalized.totalEur,components:finalized.components,currency:offer.currency};
  }
  function offerCurrencyStatus(offer){
    const pricing=offer?.pricing||{};
    const currencyParts=[offer?.currency,pricing.currency,
      ...(Array.isArray(pricing.rules)?pricing.rules:[]).map(rule=>rule?.currency),
      ...(Array.isArray(pricing.componentGroups)?pricing.componentGroups:[])
        .flatMap(group=>Array.isArray(group?.rules)?group.rules.map(rule=>rule?.currency):[])];
    const currencies=[...new Set(currencyParts.filter(value=>value!=null&&String(value).trim())
      .map(value=>String(value).trim().toUpperCase()))];
    if(!currencies.length)return{complete:false,reason:'currency_missing'};
    if(currencies.length!==1||!/^[A-Z]{3}$/.test(currencies[0]))
      return{complete:false,reason:'currency_conflict_or_invalid'};
    return{complete:true,currency:currencies[0]};
  }
  function evaluateOffer(offer,session={}){
    const pricing=offer?.pricing||{},timeZone=offerTimeZone(offer,session);
    const currencyStatus=offerCurrencyStatus(offer);
    if(!currencyStatus.complete)return{...currencyStatus,offerId:offer?.id||null,timeZone};
    offer={...offer,currency:currencyStatus.currency};
    const warning=offer?.metadata?.incompletePricingReason||pricing.incompletePricingReason;
    if(warning)return{complete:false,reason:'incomplete_pricing',detail:String(warning),
      offerId:offer?.id||null,timeZone};
    for(const field of ['energyKwh','durationMinutes','chargingMinutes','postChargeMinutes']){
      const value=session[field];
      if(value!==null&&value!==undefined&&value!==''&&
         (num(value)==null||num(value)<0))
        return{complete:false,reason:'invalid_session_measurement',field,
          offerId:offer?.id||null,timeZone};
    }
    const pricingParts=[pricing,...(Array.isArray(pricing.rules)?pricing.rules:[]),
      ...(Array.isArray(pricing.componentGroups)?pricing.componentGroups:[])
        .flatMap(group=>Array.isArray(group?.rules)?group.rules:[])];
    if(pricingParts.some(part=>(num(part?.pricePerKwh)??0)>0||
       (Array.isArray(part?.ocpiDurationBands)&&part.ocpiDurationBands.some(b=>
         Array.isArray(b)&&String(b[0]).toUpperCase()==='ENERGY'&&(num(b[3])??0)>0)))&&
       num(session.energyKwh)==null)
      return{complete:false,reason:'energy_required',offerId:offer?.id||null,timeZone};
    if(pricingParts.some(part=>part?.minPrice!=null||part?.maxPrice!=null||
       part?.min_price!=null||part?.max_price!=null))
      return{complete:false,reason:'unverified_ocpi_price_bound',offerId:offer?.id||null,timeZone};
    // This historical rule already exists below, but the monetary-field guard
    // had made even sessions below its threshold incalculable. Admit only its
    // complete known shape; above-threshold hourly rounding remains unproved.
    if(pricing.longConnectionFee!=null){
      const fee=pricing.longConnectionFee;
      if(pricing.type!=='rules'||pricing.componentGroups!=null||offer.currency!=='EUR'||
         !fee||typeof fee!=='object'||Array.isArray(fee)||
         Object.keys(fee).some(k=>!['thresholdMinutes','eurPerHourAfterThreshold','basis'].includes(k))||
         !Number.isFinite(fee.thresholdMinutes)||fee.thresholdMinutes<0||
         !Number.isFinite(fee.eurPerHourAfterThreshold)||fee.eurPerHourAfterThreshold<0||
         (fee.basis!=null&&fee.basis!=='connection_time'))
        return{complete:false,reason:'unsupported_long_connection_fee',offerId:offer?.id||null,timeZone};
      if(num(session.durationMinutes)==null)
        return{complete:false,reason:'duration_required',offerId:offer?.id||null,timeZone};
    }
    const unhandled=unhandledBillableField(pricing);
    if(unhandled)return{complete:false,reason:'unsupported_pricing_component',
      field:unhandled,offerId:offer?.id||null,timeZone};
    const rules=[...(Array.isArray(pricing.rules)?pricing.rules:[]),
      ...(Array.isArray(pricing.componentGroups)?pricing.componentGroups:[])
        .flatMap(group=>Array.isArray(group?.rules)?group.rules:[])];
    const paidBand=(rule,kind)=>Array.isArray(rule?.ocpiDurationBands)&&
      rule.ocpiDurationBands.some(b=>Array.isArray(b)&&String(b[0]).toUpperCase()===kind&&
        (num(b[3])??0)>0);
    if(rules.some(rule=>(num(rule?.pricePerMinute)??num(rule?.connectedTimePerMinuteEur)??0)>0||
       (num(rule?.connectedTimeBlockEur)??0)>0||
       (num(rule?.connectedTimePerMinuteAfterFreeEur)??0)>0||
       (num(rule?.connectedTimeInitialFlatEur)??0)>0)&&num(session.durationMinutes)==null)
      return{complete:false,reason:'duration_required',offerId:offer?.id||null,timeZone};
    if(rules.some(rule=>(num(rule?.chargePerMinute)??num(rule?.chargingTimePerMinuteEur)??0)>0||
       paidBand(rule,'TIME'))&&
       (num(session.durationMinutes)==null||num(session.chargingMinutes)==null))
      return{complete:false,reason:'charging_duration_required',offerId:offer?.id||null,timeZone};
    if(rules.some(rule=>(num(rule?.idlePerMinute)??0)>0||paidBand(rule,'PARKING_TIME'))&&
       num(session.postChargeMinutes)==null)
      return{complete:false,reason:'post_charge_duration_required',offerId:offer?.id||null,timeZone};
    if(pricing.type==='connected_kerb_midhope_guest_verified')return evaluateVerifiedMidhope(offer,session);
    const needsLocalTime=rules.some(rule=>rule.scope==='timeWindow'||rule.daysOfWeek!=null||rule.days!=null||rule.holidayOnly===true||rule.excludeHolidays===true||rule.validFromDate!=null||rule.validThroughDate!=null);
    if(needsLocalTime&&!timeZone)return{complete:false,reason:'missing_tariff_time_zone',offerId:offer?.id||null};
    if(timeZone){
      try{dateFormatter('en-GB',{timeZone});}
      catch(_){return{complete:false,reason:'invalid_tariff_time_zone',offerId:offer?.id||null,timeZone};}
    }
    if(pricing.type==='rules'&&rules.some(r=>r.billing==='powerMinute'))return evaluatePowerMinute(offer,session,timeZone);
    if(pricing.type==='component_groups'){
      const base=evaluateComponentGroups(pricing,session,timeZone);if(base.complete===false)return{...base,offerId:offer?.id||null,timeZone};
      const finalized=applyMinimumTotal(pricing,base.totalEur,base.components);return{complete:true,totalEur:finalized.totalEur,components:finalized.components,offerId:offer?.id||null,currency:offer?.currency||'EUR',timeZone};
    }
    if(pricing.type!=='rules'){
      const simpleFields=new Set(['type','currency','timeZone','pricePerKwh',
        'conditionalSessionFees','postChargeFee','minimumTotalEur',
        'incompletePricingReason']);
      if(!['kwh','simple'].includes(pricing.type)||
         Object.keys(pricing).some(key=>!simpleFields.has(key)))
        return{complete:false,reason:'unsupported_pricing_component',offerId:offer?.id||null};
      const rate=num(pricing.pricePerKwh);if(rate==null)return{complete:false,reason:'unsupported_pricing',offerId:offer?.id||null};
      const energy=Math.max(0,num(session.energyKwh)??0),base=money(rate*energy),conditional=evaluateConditionalSessionFees(pricing.conditionalSessionFees,session);
      if(conditional.complete===false)return{complete:false,reason:conditional.reason,offerId:offer?.id||null,conditionKind:conditional.conditionKind||null};
      const post=evaluatePostChargeFee(pricing.postChargeFee,session,timeZone);if(post.complete===false)return{complete:false,reason:post.reason,offerId:offer?.id||null};
      const components={energy:base,...(conditional.component?{conditionalSessionFees:conditional.component}:{}),...(post.component?{postCharge:post.component}:{})};
      const finalized=applyMinimumTotal(pricing,base+conditional.totalEur+post.totalEur,components);
      return{complete:true,totalEur:finalized.totalEur,components:finalized.components,offerId:offer?.id||null,currency:offer?.currency||'EUR'};
    }
    const match=matchingRuleDetailed(pricing,session.startAt,timeZone,session);if(match.unknown)return{complete:false,reason:match.reason,offerId:offer?.id||null,timeZone};const rule=match.rule;if(!rule)return{complete:false,reason:'no_matching_time_rule',offerId:offer?.id||null,timeZone};
    const duration=Math.max(0,num(session.durationMinutes)??0),boundary=minutesUntilRuleBoundary(rule,session.startAt,timeZone);
    const cappedAfterMinutes=(num(rule?.afterMinutesRate)??0)>0&&(num(rule?.afterMinutesCap)??0)>0;
    if(cappedAfterMinutes&&boundary!=null&&Number.isFinite(boundary)&&duration>boundary+1e-9&&pricing.priceSelectionBasis!=='session_start_local_time')
      return{complete:false,reason:'after_minutes_cap_crosses_rule_boundary',offerId:offer?.id||null};
    const ruleSession=cappedAfterMinutes?{...session,allowUncappedAfterMinutesForOffer:true}:session;
    const evaluatedRule=cappedAfterMinutes?{...rule,minimumSessionEur:null}:rule;
    let base,segmented=false;
    // An explicit session-start tariff remains fixed for the whole connection;
    // do not segment across clock-time window boundaries.
    if(pricing.priceSelectionBasis==='session_start_local_time'){
      base=evaluateRule(evaluatedRule,{...ruleSession,tariffDurationMinutes:duration});
    }else if(boundary!=null&&Number.isFinite(boundary)&&duration>boundary+1e-9){
      base=evaluateSegmentedRules(pricing,session,timeZone);if(base.complete===false)return{...base,offerId:offer?.id||null,timeZone,boundaryMinutes:boundary};segmented=true;
    }else base=evaluateRule(evaluatedRule,{...ruleSession,tariffDurationMinutes:duration});
    if(base.complete===false)return{...base,offerId:offer?.id||null,timeZone};
    if(cappedAfterMinutes){
      const capped=evaluateAfterMinutesCap({...rule,currency:offer.currency||rule.currency},session,timeZone);
      if(!capped.complete)return{complete:false,reason:capped.reason,offerId:offer?.id||null};
      const gross=num(base.components?.afterMinutes?.costEur);
      if(gross==null)return{complete:false,reason:'after_minutes_uncapped_component_missing',offerId:offer?.id||null};
      base={...base,totalEur:money(base.totalEur-gross+capped.costEur),
        components:{...base.components,afterMinutes:{...base.components.afterMinutes,
          costEur:capped.costEur,uncappedCostEur:gross,capEur:rule.afterMinutesCap,
          capMode:capped.mode,chargedMinutes:capped.chargedMinutes,
          nightMinutes:capped.nightMinutes,nightWindowCount:capped.nightWindowCount}}};
      const minimum=num(rule.minimumSessionEur);
      if(minimum!=null&&base.totalEur<minimum){
        base.components.minimumSession={minimumEur:minimum,preMinimumTotalEur:base.totalEur,topUpEur:money(minimum-base.totalEur)};
        base.totalEur=minimum;
      }
    }
    const longFee=pricing.longConnectionFee;let longConnection=null,total=base.totalEur;
    if(longFee&&duration>(num(longFee.thresholdMinutes)??Infinity)){
      const rate=num(longFee.eurPerHourAfterThreshold);if(rate!=null){const excess=duration-Number(longFee.thresholdMinutes);longConnection={complete:false,reason:'hourly_rounding_unspecified',excessMinutes:excess,rateEurPerHour:rate};}
    }
    const conditional=evaluateConditionalSessionFees(pricing.conditionalSessionFees,session);if(conditional.complete===false)return{complete:false,reason:conditional.reason,offerId:offer?.id||null,timeZone,conditionKind:conditional.conditionKind||null};
    total+=conditional.totalEur;
    const post=evaluatePostChargeFee(pricing.postChargeFee,session,timeZone);if(post.complete===false)return{complete:false,reason:post.reason,offerId:offer?.id||null,timeZone};
    total+=post.totalEur;
    const components={...base.components,...(conditional.component?{conditionalSessionFees:conditional.component}:{}),...(post.component?{postCharge:post.component}:{})};
    const finalized=applyMinimumTotal(pricing,total,components);
    return{complete:!longConnection,totalEur:finalized.totalEur,components:finalized.components,longConnection,offerId:offer?.id||null,currency:offer?.currency||'EUR',matchedRule:rule,segmented,timeZone};
  }
  return{evaluateAfterMinutesCap,congestionBillableMinutes,congestionFee,evaluateOffer,offerCurrencyStatus,offerTimeZone,evaluateRule,evaluateSegmentedRules,evaluateComponentGroups,segmentableRule,ruleThresholdStatus,ruleThresholdMatches,matchingRuleDetailed,evaluateConditionalSessionFees,evaluatePostChargeFee,postChargeBillableMinutes,exemptWindowContains,matchingRule,ruleContains,ruleDayMatches,localDateParts,isHoliday,italianHolidayKeys,minuteOfDay,minutesUntilRuleBoundary,applyMinimumTotal};
});
