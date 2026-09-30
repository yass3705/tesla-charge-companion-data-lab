import fs from 'node:fs/promises';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import path from 'node:path';

const CACHE='data/electroverse/tariff_cache';
const MANIFEST=CACHE+'/manifest.json';
const MAP='data/electroverse/irve_location_mapping.json';
const OUT=process.argv[2]||'data/platforms/electroverse/france-evse';
const TILE=.5;
await fs.rm(OUT,{recursive:true,force:true});
await fs.mkdir(OUT,{recursive:true});

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const text=x=>String(x??'').trim();
const round=(x,d=6)=>Number(Number(x).toFixed(d));
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const weekdays={SUNDAY:0,MONDAY:1,TUESDAY:2,WEDNESDAY:3,THURSDAY:4,FRIDAY:5,SATURDAY:6};
const TODAY_FR=new Intl.DateTimeFormat('en-CA',{
  timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit'
}).format(new Date());
function activeDateRestriction(d){
  if(!d||( !d.startDate && !d.endDate))return true;
  const start=d.startDate?String(d.startDate).slice(0,10):null;
  const end=d.endDate?String(d.endDate).slice(0,10):null;
  if(start&&TODAY_FR<start)return false;
  // Treat end as exclusive: adjacent tariff versions commonly use the same
  // boundary date for old.endDate and new.startDate.
  if(end&&TODAY_FR>=end)return false;
  return true;
}

function parseMoney(v){
  const s=text(v).replace(/\u00a0/g,' ').replace(',','.');
  const m=s.match(/(?:€|EUR|CHF|£|GBP|MAD|USD|\$)?\s*(-?\d+(?:\.\d+)?)/i);
  return m?Number(m[1]):null;
}
function componentKind(type){
  const t=String(type||'');
  if(t==='ConsumptionRate')return 'energy';
  if(t==='TimeRate')return 'time';
  if(t==='ParkingTimeRate')return 'parking';
  if(t==='ConnectionFee')return 'flat';
  if(t==='VAT')return 'vat';
  return '';
}
function emptyRate(){return{energy:0,time:0,parking:0,flat:0};}
function parseComponents(comps){
  const rate=emptyRate(),present=new Set();
  for(const c of comps||[]){
    const k=componentKind(c?.__typename);
    if(k==='vat')continue;
    if(!k)return{ok:false,reason:'unsupported_component_'+String(c?.__typename||'unknown')};
    const v=parseMoney(c?.formattedValue);
    if(!Number.isFinite(v))return{ok:false,reason:'unparseable_'+k};
    rate[k]+=v;present.add(k);
  }
  return{ok:true,rate,present};
}
function hasDateRestriction(r){
  const d=r?.dateRestrictions;
  return !!(d&&(d.startDate||d.endDate));
}
function windowKey(r){
  const tr=r?.timeRestrictions||{};
  const wr=r?.weekdayRestrictions?.daysOfWeek;
  const days=Array.isArray(wr)&&wr.length?wr.map(x=>weekdays[x]).filter(Number.isInteger).sort((a,b)=>a-b):null;
  return{
    start:tr.startTime?String(tr.startTime).slice(0,5):'00:00',
    end:tr.endTime?String(tr.endTime).slice(0,5):'24:00',
    days,
    key:`${tr.startTime?String(tr.startTime).slice(0,5):'00:00'}|${tr.endTime?String(tr.endTime).slice(0,5):'24:00'}|${(days||[]).join(',')}`
  };
}
function rateEqual(a,b){
  return ['energy','time','parking','flat'].every(k=>Math.abs(Number(a[k]||0)-Number(b[k]||0))<1e-9);
}
function makeRule(scope,start,end,currency,rate,days=null,after=null){
  return{
    scope,start,end,billing:rate.energy>0?'kwh':rate.time>0?'minute':'kwh',currency,
    pricePerKwh:round(rate.energy),chargePerMinute:round(rate.time),
    connectionFee:round(rate.flat),idlePerMinute:round(rate.parking),
    afterMinutesRate:after?round(after.rate):0,
    afterMinutesThreshold:after?Math.round(after.threshold):0,
    days:days?.length?days:null,ocpiDurationBands:[]
  };
}
function compileConnector(c){
  const currency=text(c?.complexPricingDetail?.currency||'EUR').toUpperCase()||'EUR';
  const simple=parseComponents(c?.priceComponents||[]);
  if(!simple.ok)return simple;
  let base={...simple.rate};
  if(c?.isChargingFree===true)base=emptyRate();

  const rawRestrictions=c?.complexPricingDetail?.restrictions||[];
  const restrictions=rawRestrictions.filter(r=>!hasDateRestriction(r)||activeDateRestriction(r?.dateRestrictions));
  const hadDateRestrictions=rawRestrictions.some(hasDateRestriction);
  if(!restrictions.length){
    if(c?.isChargingFree!==true && !(c?.priceComponents||[]).length)
      return{ok:false,reason:hadDateRestrictions?'no_active_pricing':'no_pricing'};
    return{ok:true,pricing:{type:'rules',rules:[makeRule('allDay','00:00','24:00',currency,base)]}};
  }

  const groups=new Map();
  for(const r of restrictions){
    const parsed=parseComponents(r?.priceComponents||[]);
    if(!parsed.ok)return parsed;
    const w=windowKey(r);
    const dr=r?.durationRestrictions||{};
    const min=Number(dr.minDurationSeconds),max=Number(dr.maxDurationSeconds);
    const hasMin=Number.isFinite(min)&&min>0,hasMax=Number.isFinite(max)&&max>0;
    if(hasMin&&hasMax)return{ok:false,reason:'bounded_duration_range'};
    let g=groups.get(w.key);
    if(!g){g={...w,plain:[],upper:[],lower:[]};groups.set(w.key,g);}
    const item={rate:parsed.rate,present:parsed.present,threshold:hasMin?min/60:hasMax?max/60:0};
    if(hasMin)g.lower.push(item);
    else if(hasMax)g.upper.push(item);
    else g.plain.push(item);
  }

  // Unrestricted complex rule overrides simple base when present.
  const unrestricted=groups.get('00:00|24:00|');
  if(unrestricted?.plain?.length){
    if(unrestricted.plain.length!==1)return{ok:false,reason:'multiple_unrestricted_rules'};
    const p=unrestricted.plain[0];
    for(const k of p.present)base[k]=p.rate[k];
    unrestricted.plain=[];
  }

  const rules=[makeRule('allDay','00:00','24:00',currency,base)];
  for(const g of groups.values()){
    if(g.key==='00:00|24:00|'&&!g.plain.length&&!g.upper.length&&!g.lower.length)continue;
    let rate={...base};

    if(g.plain.length>1)return{ok:false,reason:'multiple_plain_window_rules'};
    if(g.plain.length===1)for(const k of g.plain[0].present)rate[k]=g.plain[0].rate[k];

    if(g.upper.length>1||g.lower.length>1)return{ok:false,reason:'multiple_duration_thresholds'};
    let after=null;
    if(g.upper.length){
      const up=g.upper[0];
      // A max-duration rule defines the rate up to threshold.
      for(const k of up.present)rate[k]=up.rate[k];
    }
    if(g.lower.length){
      const lo=g.lower[0];
      const threshold=lo.threshold;
      if(g.upper.length && Math.abs(g.upper[0].threshold-threshold)>1e-9)
        return{ok:false,reason:'duration_threshold_mismatch'};
      // Engine supports time/parking surcharge after threshold, but not an
      // energy/flat tariff switch by duration.
      if(lo.present.has('energy') && Math.abs(lo.rate.energy-rate.energy)>1e-9)
        return{ok:false,reason:'energy_changes_after_duration'};
      if(lo.present.has('flat') && Math.abs(lo.rate.flat-rate.flat)>1e-9)
        return{ok:false,reason:'flat_changes_after_duration'};
      const surcharge=Math.max(0,lo.rate.time-rate.time)+Math.max(0,lo.rate.parking-rate.parking);
      if((lo.present.has('time')&&lo.rate.time<rate.time)||(lo.present.has('parking')&&lo.rate.parking<rate.parking))
        return{ok:false,reason:'rate_decreases_after_duration'};
      if(surcharge>0)after={threshold,rate:surcharge};
    }
    const isAll=g.start==='00:00'&&g.end==='24:00';
    if(isAll&&!g.days?.length){
      // merge duration-only semantics into base rule when possible
      if(g.plain.length||g.upper.length){
        rules[0]=makeRule('allDay','00:00','24:00',currency,rate,null,after);
      }else if(after){
        rules[0]={...rules[0],afterMinutesRate:round(after.rate),afterMinutesThreshold:Math.round(after.threshold)};
      }
    }else{
      rules.push(makeRule('timeWindow',g.start,g.end,currency,rate,g.days,after));
    }
  }
  return{ok:true,pricing:{type:'rules',rules}};
}
function pricingSig(p){return JSON.stringify(p);}
function tileId(lat,lon){return `t_${Math.floor(lat/TILE)}_${Math.floor(lon/TILE)}`;}

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const manifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const globalPdcOwners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;
  const set=globalPdcOwners.get(k)||new Set();set.add(m.irveStationId);globalPdcOwners.set(k,set);
}

const tiles=new Map(),rejected={},parentGroups=new Map();
const pricingDiagnostics={
  dateRestriction:{evses:0,restrictions:0,withStart:0,withEnd:0,withBoth:0,ranges:{},samples:[]},
  boundedDuration:{evses:0,restrictions:0,bands:{},componentTypes:{},samples:[]}
};
const stats={
  cacheLocations:0,cacheEvses:0,physicalRefs:0,exactUniqueNationalEvses:0,
  parentConnectorRefs:0,parentCandidateGroups:0,parentPublishedEvses:0,parentPublishedChildRefs:0,
  ordinalCandidateRefs:0,ordinalPublishedEvses:0,
  genericTailCandidateRefs:0,genericTailPublishedEvses:0,
  suffixIdentityCandidateRefs:0,suffixIdentityPublishedEvses:0,
  duplicatePublishedEvseTargetsBeforeDedup:0,conflictingPublishedEvseTargetsBeforeDedup:0,
  dedupedIdenticalOffers:0,conflictingTargetsDropped:0,
  pricedExactEvses:0,publishedEvses:0,publishedOffers:0,publishedConnectorCount:0
};
function rej(k){rejected[k]=(rejected[k]||0)+1;}

for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    stats.cacheLocations++;
    const m=byPk.get(String(row.electroverseLocationPk));
    if(!m){rej('missing_location_mapping');continue;}
    const localRaw=(m.irvePdcIds||row.irvePdcIds||[]).filter(Boolean);
    const localByNorm=new Map(localRaw.map(p=>[norm(p),p]).filter(([k])=>k));
    const local=new Set(localByNorm.keys());
    const lat=Number(m.electroverse?.lat??m.irve?.lat),lon=Number(m.electroverse?.lon??m.irve?.lon);
    if(!Number.isFinite(lat)||!Number.isFinite(lon)){rej('missing_coordinates');continue;}

    // Strict station-local ordinal mapping for providers that expose physicalReference
    // only as "1", "2", ... while the national PDCs share one prefix and indexed suffixes.
    const ordinalTargets=new Map(),usedForOrdinal=new Set(),hardNumeric=[];
    for(const e0 of row.tariff?.evses||[]){
      const pr0=text(e0?.physicalReference); if(!pr0)continue;
      const k0=norm(pr0);
      if(local.has(k0)){usedForOrdinal.add(k0);continue;}
      const p0=[...local].filter(p=>{
        if(!k0.startsWith(p)||k0.length<=p.length)return false;
        return /^\d{1,2}$/.test(k0.slice(p.length));
      });
      if(p0.length===1){usedForOrdinal.add(p0[0]);continue;}
      if(/^\d{1,2}$/.test(k0))hardNumeric.push({e:e0,n:Number(k0)});
    }
    if(hardNumeric.length && new Set(hardNumeric.map(x=>x.n)).size===hardNumeric.length){
      const available=[...local].filter(p=>!usedForOrdinal.has(p));
      let chosen=null;
      for(const width of [1,2]){
        if(available.some(p=>p.length<=width))continue;
        const prefixes=new Set(available.map(p=>p.slice(0,-width)));
        if(prefixes.size!==1)continue;
        const nums=available.map(p=>/^\d+$/.test(p.slice(-width))?Number(p.slice(-width)):NaN);
        if(nums.some(x=>!Number.isFinite(x)))continue;
        const wanted=new Set(hardNumeric.map(x=>x.n));
        const byNum=new Map(); let ok=true;
        for(let i=0;i<available.length;i++){
          const n=nums[i]; if(!wanted.has(n))continue;
          if(byNum.has(n)){ok=false;break;}
          byNum.set(n,available[i]);
        }
        if(!ok||byNum.size!==hardNumeric.length)continue;
        if([...byNum.values()].some(p=>(globalPdcOwners.get(p)?.size||0)!==1))continue;
        chosen=byNum;break;
      }
      if(chosen) for(const x of hardNumeric) ordinalTargets.set(x.e,chosen.get(x.n));
    }

    const genericTargets=new Map(),usedForGeneric=new Set(),genericHard=[];
    for(const e0 of row.tariff?.evses||[]){
      const pr0=text(e0?.physicalReference); if(!pr0)continue;
      const k0=norm(pr0);
      if(local.has(k0)){usedForGeneric.add(k0);continue;}
      const p0=[...local].filter(p=>{
        if(!k0.startsWith(p)||k0.length<=p.length)return false;
        return /^\d{1,2}$/.test(k0.slice(p.length));
      });
      if(p0.length===1){usedForGeneric.add(p0[0]);continue;}
      genericHard.push({e:e0,k:k0});
    }
    if(genericHard.length && new Set(genericHard.map(x=>x.k)).size===genericHard.length){
      const available=[...local].filter(p=>!usedForGeneric.has(p));
      if(available.length){
        let commonPrefix=available[0];
        for(const p of available.slice(1)){
          let i=0;while(i<commonPrefix.length&&i<p.length&&commonPrefix[i]===p[i])i++;
          commonPrefix=commonPrefix.slice(0,i);
          if(!commonPrefix)break;
        }
        if(commonPrefix.length>=4){
          const tailToPdc=new Map(); let ok=true;
          for(const p of available){
            const tail=p.slice(commonPrefix.length);
            if(!tail||tailToPdc.has(tail)){ok=false;break;}
            tailToPdc.set(tail,p);
          }
          if(ok && genericHard.every(x=>tailToPdc.has(x.k))){
            const targets=genericHard.map(x=>tailToPdc.get(x.k));
            if(new Set(targets).size===genericHard.length &&
               targets.every(p=>(globalPdcOwners.get(p)?.size||0)===1)){
              for(const x of genericHard)genericTargets.set(x.e,tailToPdc.get(x.k));
            }
          }
        }
      }
    }

    const suffixTargets=new Map();
    const reservedTargets=new Set();
    for(const e0 of row.tariff?.evses||[]){
      const pr0=text(e0?.physicalReference); if(!pr0)continue;
      const k0=norm(pr0);
      if(local.has(k0)){reservedTargets.add(k0);continue;}
      const p0=[...local].filter(p=>{
        if(!k0.startsWith(p)||k0.length<=p.length)return false;
        return /^\d{1,2}$/.test(k0.slice(p.length));
      });
      if(p0.length===1){reservedTargets.add(p0[0]);continue;}
      if(ordinalTargets.has(e0)){reservedTargets.add(ordinalTargets.get(e0));continue;}
      if(genericTargets.has(e0)){reservedTargets.add(genericTargets.get(e0));continue;}
    }
    const claimedSuffixTargets=new Set();
    for(const e0 of row.tariff?.evses||[]){
      const pr0=text(e0?.physicalReference); if(!pr0)continue;
      const k0=norm(pr0);
      if(k0.length<4)continue;
      if(local.has(k0))continue;
      if(ordinalTargets.has(e0)||genericTargets.has(e0))continue;
      const p0=[...local].filter(p=>{
        if(!k0.startsWith(p)||k0.length<=p.length)return false;
        return /^\d{1,2}$/.test(k0.slice(p.length));
      });
      if(p0.length===1)continue;
      const matches=[...local].filter(p=>p.endsWith(k0));
      if(matches.length!==1)continue;
      const target=matches[0];
      if(reservedTargets.has(target)||claimedSuffixTargets.has(target))continue;
      if((globalPdcOwners.get(target)?.size||0)!==1)continue;
      suffixTargets.set(e0,target);
      claimedSuffixTargets.add(target);
    }

    for(const e of row.tariff?.evses||[]){
      stats.cacheEvses++;
      const pr=text(e?.physicalReference);
      if(!pr){rej('evse_missing_physical_reference');continue;}
      stats.physicalRefs++;
      const k=norm(pr);
      let targetPdc=pr,identityMode='exact_unique_national_irve_pdc',parentMode=false,parentNorm='',ordinalMode=false;
      if(local.has(k)){
        const owners=globalPdcOwners.get(k);
        if(!owners||owners.size!==1){rej('physical_reference_not_globally_unique');continue;}
        stats.exactUniqueNationalEvses++;
      }else{
        const candidates=[...local].filter(p=>{
          if(!k.startsWith(p)||k.length<=p.length)return false;
          const suffix=k.slice(p.length);
          return /^\d{1,2}$/.test(suffix);
        });
        if(candidates.length===1){
          parentNorm=candidates[0];
          const owners=globalPdcOwners.get(parentNorm);
          if(!owners||owners.size!==1){rej('parent_pdc_not_globally_unique');continue;}
          targetPdc=localByNorm.get(parentNorm);
          identityMode='exact_unique_national_irve_pdc_parent_connector_suffix';
          parentMode=true;
          stats.parentConnectorRefs++;
        }else if(ordinalTargets.has(e)){
          const targetNorm=ordinalTargets.get(e);
          const owners=globalPdcOwners.get(targetNorm);
          if(!owners||owners.size!==1){rej('ordinal_pdc_not_globally_unique');continue;}
          targetPdc=localByNorm.get(targetNorm);
          identityMode='strict_station_ordinal_suffix_bijection';
          ordinalMode=true;
          stats.ordinalCandidateRefs++;
        }else if(genericTargets.has(e)){
          const targetNorm=genericTargets.get(e);
          const owners=globalPdcOwners.get(targetNorm);
          if(!owners||owners.size!==1){rej('generic_tail_pdc_not_globally_unique');continue;}
          targetPdc=localByNorm.get(targetNorm);
          identityMode='strict_station_common_prefix_tail_bijection';
          stats.genericTailCandidateRefs++;
        }else if(suffixTargets.has(e)){
          const targetNorm=suffixTargets.get(e);
          const owners=globalPdcOwners.get(targetNorm);
          if(!owners||owners.size!==1){rej('suffix_identity_pdc_not_globally_unique');continue;}
          targetPdc=localByNorm.get(targetNorm);
          identityMode='strict_unique_local_suffix_identity';
          stats.suffixIdentityCandidateRefs++;
        }else{
          rej(candidates.length?'parent_pdc_ambiguous':'physical_reference_not_in_local_national_pdcs');continue;
        }
      }

      const connectors=e?.connectors||[];
      if(!connectors.length){rej('evse_no_connectors');continue;}
      const compiled=[];
      let bad=null;
      for(const c of connectors){
        const x=compileConnector(c);
        if(!x.ok){bad=x.reason;break;}
        compiled.push({pricing:x.pricing,connectorPk:c.pk??null,powerKw:c.kilowatts??null,standard:c.standard??null});
      }
      if(bad){
        rej('pricing_'+bad);
        if(bad==='date_restriction'){
          pricingDiagnostics.dateRestriction.evses++;
          for(const c0 of connectors){
            for(const r0 of c0?.complexPricingDetail?.restrictions||[]){
              const d=r0?.dateRestrictions;
              if(!d||( !d.startDate && !d.endDate))continue;
              pricingDiagnostics.dateRestriction.restrictions++;
              if(d.startDate)pricingDiagnostics.dateRestriction.withStart++;
              if(d.endDate)pricingDiagnostics.dateRestriction.withEnd++;
              if(d.startDate&&d.endDate)pricingDiagnostics.dateRestriction.withBoth++;
              const rk=`${d.startDate||''}..${d.endDate||''}`;
              pricingDiagnostics.dateRestriction.ranges[rk]=(pricingDiagnostics.dateRestriction.ranges[rk]||0)+1;
              if(pricingDiagnostics.dateRestriction.samples.length<40)pricingDiagnostics.dateRestriction.samples.push({
                locationPk:String(row.electroverseLocationPk),physicalReference:pr,evsePk:e.pk??null,
                connectorPk:c0.pk??null,startDate:d.startDate||null,endDate:d.endDate||null,
                timeRestrictions:r0?.timeRestrictions||null,weekdayRestrictions:r0?.weekdayRestrictions||null,
                durationRestrictions:r0?.durationRestrictions||null,
                priceComponents:r0?.priceComponents||[]
              });
            }
          }
        }else if(bad==='bounded_duration_range'){
          pricingDiagnostics.boundedDuration.evses++;
          for(const c0 of connectors){
            for(const r0 of c0?.complexPricingDetail?.restrictions||[]){
              const dr=r0?.durationRestrictions||{};
              const min=Number(dr.minDurationSeconds),max=Number(dr.maxDurationSeconds);
              if(!(Number.isFinite(min)&&min>0&&Number.isFinite(max)&&max>0))continue;
              pricingDiagnostics.boundedDuration.restrictions++;
              const bk=`${min}..${max}`;
              pricingDiagnostics.boundedDuration.bands[bk]=(pricingDiagnostics.boundedDuration.bands[bk]||0)+1;
              for(const pc of r0?.priceComponents||[]){
                const t=String(pc?.__typename||'unknown');
                pricingDiagnostics.boundedDuration.componentTypes[t]=(pricingDiagnostics.boundedDuration.componentTypes[t]||0)+1;
              }
              if(pricingDiagnostics.boundedDuration.samples.length<40)pricingDiagnostics.boundedDuration.samples.push({
                locationPk:String(row.electroverseLocationPk),physicalReference:pr,evsePk:e.pk??null,
                connectorPk:c0.pk??null,minDurationSeconds:min,maxDurationSeconds:max,
                priceComponents:r0?.priceComponents||[],currency:c0?.complexPricingDetail?.currency||null
              });
            }
          }
        }
        continue;
      }
      stats.pricedExactEvses++;
      const unique=[...new Map(compiled.map(x=>[pricingSig(x.pricing),x.pricing])).values()];
      if(unique.length!==1){rej('heterogeneous_connectors_within_evse');continue;}

      const pricing=unique[0],currency=pricing.rules?.[0]?.currency||'EUR';
      if(parentMode){
        const gk=`${row.electroverseLocationPk}|${parentNorm}`;
        const g=parentGroups.get(gk)||{
          locationPk:String(row.electroverseLocationPk),parentPdc:targetPdc,parentNorm,
          lat,lon,entries:[],pricingBySig:new Map(),tariffHashes:new Set(),fetchedAts:new Set()
        };
        g.entries.push({physicalReference:pr,evsePk:e.pk??null,connectorPks:compiled.map(x=>x.connectorPk),connectorCount:compiled.length});
        g.pricingBySig.set(pricingSig(pricing),pricing);
        if(row.tariffHash)g.tariffHashes.add(row.tariffHash);
        if(row.fetchedAt)g.fetchedAts.add(row.fetchedAt);
        parentGroups.set(gk,g);
        continue;
      }

      const offer={
        id:`electroverse-evse:${row.electroverseLocationPk}:${e.pk??k}`,
        provider:'Electroverse',
        countries:['FR'],
        currency,
        priority:80,
        verifiedScope:'exact_evse',
        evseIds:[targetPdc],
        pricing,
        metadata:{
          verified:true,
          identityMode,
          electroverseLocationPk:String(row.electroverseLocationPk),
          electroverseEvsePk:e.pk??null,
          physicalReference:pr,
          connectorPks:compiled.map(x=>x.connectorPk),
          connectorCount:compiled.length,
          tariffHash:row.tariffHash||null,
          fetchedAt:row.fetchedAt||null,
          source:'Electroverse tariff cache'
        }
      };
      const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);
      tiles.get(id).push(offer);
      if(ordinalMode)stats.ordinalPublishedEvses++;
      if(identityMode==='strict_station_common_prefix_tail_bijection')stats.genericTailPublishedEvses++;
      if(identityMode==='strict_unique_local_suffix_identity')stats.suffixIdentityPublishedEvses++;
      stats.publishedEvses++;stats.publishedOffers++;stats.publishedConnectorCount+=compiled.length;
    }
  }
}

stats.parentCandidateGroups=parentGroups.size;
for(const g of parentGroups.values()){
  if(g.pricingBySig.size!==1){rej('parent_pdc_heterogeneous_child_pricing');continue;}
  const pricing=[...g.pricingBySig.values()][0];
  const currency=pricing.rules?.[0]?.currency||'EUR';
  const connectorPks=g.entries.flatMap(x=>x.connectorPks);
  const offer={
    id:`electroverse-evse-parent:${g.locationPk}:${g.parentNorm}`,
    provider:'Electroverse',
    countries:['FR'],
    currency,
    priority:80,
    verifiedScope:'exact_evse',
    evseIds:[g.parentPdc],
    pricing,
    metadata:{
      verified:true,
      identityMode:'exact_unique_national_irve_pdc_parent_connector_suffix',
      electroverseLocationPk:g.locationPk,
      physicalReferences:g.entries.map(x=>x.physicalReference),
      electroverseEvsePks:g.entries.map(x=>x.evsePk),
      connectorPks,
      connectorCount:g.entries.reduce((n,x)=>n+x.connectorCount,0),
      childReferenceCount:g.entries.length,
      tariffHashes:[...g.tariffHashes],
      fetchedAts:[...g.fetchedAts],
      source:'Electroverse tariff cache'
    }
  };
  const id=tileId(g.lat,g.lon);if(!tiles.has(id))tiles.set(id,[]);
  tiles.get(id).push(offer);
  stats.parentPublishedEvses++;
  stats.parentPublishedChildRefs+=g.entries.length;
  stats.publishedEvses++;stats.publishedOffers++;stats.publishedConnectorCount+=offer.metadata.connectorCount;
}

const offersByTarget=new Map(),duplicateSamples=[];
for(const [tileIdKey,offers] of tiles.entries()) for(const offer of offers){
  const target=norm(offer.evseIds?.[0]);
  if(!target)continue;
  const arr=offersByTarget.get(target)||[];
  arr.push({tileIdKey,offer,pricingSig:pricingSig(offer.pricing)});
  offersByTarget.set(target,arr);
}
const dropOfferIds=new Set();
for(const [target,items] of offersByTarget.entries()){
  if(items.length<2)continue;
  stats.duplicatePublishedEvseTargetsBeforeDedup+=items.length-1;
  const sigs=new Set(items.map(x=>x.pricingSig));
  if(sigs.size===1){
    const sorted=[...items].sort((a,b)=>String(a.offer.id).localeCompare(String(b.offer.id)));
    for(const x of sorted.slice(1))dropOfferIds.add(x.offer.id);
    stats.dedupedIdenticalOffers+=items.length-1;
  }else{
    for(const x of items)dropOfferIds.add(x.offer.id);
    stats.conflictingPublishedEvseTargetsBeforeDedup+=items.length-1;
    stats.conflictingTargetsDropped++;
    rej('duplicate_evse_conflicting_pricing');
  }
  if(duplicateSamples.length<25)duplicateSamples.push({
    evseId:items[0].offer.evseIds?.[0],
    offerIds:items.map(x=>x.offer.id),
    pricingConflict:sigs.size>1
  });
}
for(const [tileIdKey,offers] of tiles.entries()){
  tiles.set(tileIdKey,offers.filter(o=>!dropOfferIds.has(o.id)));
}

// Recompute final published KPIs after dedupe/fail-closed conflict removal.
const finalOffers=[...tiles.values()].flat();
stats.publishedEvses=finalOffers.length;
stats.publishedOffers=finalOffers.length;
stats.publishedConnectorCount=finalOffers.reduce((n,o)=>n+Number(o.metadata?.connectorCount||0),0);
stats.parentPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='exact_unique_national_irve_pdc_parent_connector_suffix').length;
stats.parentPublishedChildRefs=finalOffers
  .filter(o=>o.metadata?.identityMode==='exact_unique_national_irve_pdc_parent_connector_suffix')
  .reduce((n,o)=>n+Number(o.metadata?.childReferenceCount||0),0);
stats.ordinalPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_station_ordinal_suffix_bijection').length;
stats.genericTailPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_station_common_prefix_tail_bijection').length;
stats.suffixIdentityPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_unique_local_suffix_identity').length;

const manifestTiles=[];
for(const [id,offers] of [...tiles.entries()].sort((a,b)=>a[0].localeCompare(b[0]))){
  const payload={schemaVersion:1,country:'FR',generatedAt:new Date().toISOString(),emspOffers:offers};
  const gz=zlib.gzipSync(Buffer.from(JSON.stringify(payload)),{level:9});
  const file=id+'.json.gz';await fs.writeFile(path.join(OUT,file),gz);
  const [a,b]=id.slice(2).split('_').map(Number);
  manifestTiles.push({id,file,minLat:a*TILE,maxLat:(a+1)*TILE,minLon:b*TILE,maxLon:(b+1)*TILE,count:offers.length,bytes:gz.length,sha256:sha(gz)});
}
const out={
  schemaVersion:1,
  dataset:'electroverse-france-evse-national-overlay',
  generatedAt:new Date().toISOString(),
  country:'FR',
  tileSizeDegrees:TILE,
  tileCount:manifestTiles.length,
  stats,rejected,
  pricingDiagnostics,
  duplicateSamples,
  policy:{
    nationalFranceIsIdentityHub:true,
    exactUniqueNationalPdcOnly:true,
    exactParentPdcConnectorSuffix:true,
    parentPdcRequiresUniqueLocalPrefix:true,
    parentPdcRequiresNumericSuffixMax2:true,
    parentPdcRequiresHomogeneousChildPricing:true,
    strictStationOrdinalSuffixBijection:true,
    ordinalPdcRequiresGlobalUniqueness:true,
    strictStationCommonPrefixTailBijection:true,
    genericTailRequiresGlobalUniqueness:true,
    strictUniqueLocalSuffixIdentityMinLength:4,
    suffixIdentityRequiresGlobalUniqueness:true,
    suffixIdentityRequiresUnclaimedTarget:true,
    evseLevelPricing:true,
    stationLevelFlattening:false,
    electraDependency:false,
    proximityInference:false,
    heterogeneousConnectorsWithinEvseFailClosed:true,
    unsupportedPricingFailClosed:true,
    duplicateSamePriceDeduplicated:true,
    duplicateConflictingPriceFailClosed:true,
    dateRestrictedPricingUsesActiveFranceLocalDate:true,
    dateRestrictionEndExclusive:true
  },
  source:{
    tariffCacheGeneratedAt:manifest.generatedAt,
    tariffCacheStations:manifest.totalStations,
    mappingGeneratedAt:mapping.generatedAt,
    pricingEffectiveDateFrance:TODAY_FR
  },
  tiles:manifestTiles
};
await fs.writeFile(path.join(OUT,'manifest.json'),JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
if(stats.publishedOffers<5000)throw new Error('too few safe Electroverse EVSE offers: '+stats.publishedOffers);
