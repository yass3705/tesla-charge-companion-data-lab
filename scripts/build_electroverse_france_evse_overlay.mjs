import fs from 'node:fs/promises';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import path from 'node:path';

const CACHE='data/electroverse/tariff_cache';
const MANIFEST=CACHE+'/manifest.json';
const MAP='data/electroverse/irve_location_mapping.json';
const DRIVECO='data/operator_direct/driveco_evse_tariffs.json';
const POWERDOT_TECH='data/operator_direct/powerdot_evse_technical_inventory.json';
const VIANEO_IDENTITY='data/operator_direct/vianeo_official_identity_map.json';
const VALIDATED_NUMERIC_MAP='data/platforms/electroverse/validated-mappings/numeric-residual.json';
const VALIDATED_S82_MAP='data/platforms/electroverse/validated-mappings/s82-residual.json';
const VALIDATED_MGP_MAP='data/platforms/electroverse/validated-mappings/mgp-residual.json';
const VALIDATED_LE2_MAP='data/platforms/electroverse/validated-mappings/le2-residual.json';
const VALIDATED_P01_MAP='data/platforms/electroverse/validated-mappings/p01-structured-residual.json';
const VALIDATED_B_MAP='data/platforms/electroverse/validated-mappings/b-residual.json';
const VALIDATED_SAE_MAP='data/platforms/electroverse/validated-mappings/sae-structured-residual.json';
const VALIDATED_H01_MAP='data/platforms/electroverse/validated-mappings/h01-structured-residual.json';
const VALIDATED_ADP_MAP='data/platforms/electroverse/validated-mappings/adp-structured-residual.json';
const VALIDATED_GENERIC_SMALL_MAP='data/platforms/electroverse/validated-mappings/generic-small-buckets.json';
const VALIDATED_CUSTOMGY_PAIR_MAP='data/platforms/electroverse/validated-mappings/customgyevse-pair-groups.json';
const VALIDATED_CUSTOMGY_PDC_EXTENSIONS='data/platforms/electroverse/validated-mappings/customgyevse-pdc-extensions.json';
const FINAL_RESIDUAL_PLAN='data/platforms/electroverse/validated-mappings/final-residual-recovery-plan.json';
const OUT=process.argv[2]||'data/platforms/electroverse/france-evse';
const TILE=.5;
// Rebuild marker: validate protected PD1 technical grouping on main.
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
function makeRule(scope,start,end,currency,rate,days=null,after=null,bands=[]){
  return{
    scope,start,end,billing:rate.energy>0?'kwh':rate.time>0?'minute':'kwh',currency,
    pricePerKwh:round(rate.energy),chargePerMinute:round(rate.time),
    connectionFee:round(rate.flat),idlePerMinute:round(rate.parking),
    afterMinutesRate:after?round(after.rate):0,
    afterMinutesThreshold:after?Math.round(after.threshold):0,
    days:days?.length?days:null,ocpiDurationBands:bands
  };
}
const ocpiDimension={energy:'ENERGY',time:'TIME',parking:'PARKING_TIME',flat:'FLAT'};
function durationBandsFor(group){
  const bands=[];
  for(const item of group.duration||[]){
    for(const kind of item.present){
      const dim=ocpiDimension[kind];if(!dim)continue;
      bands.push([dim,item.minSeconds,item.maxSeconds,round(item.rate[kind])]);
    }
  }
  // Fail closed on overlapping bands for the same priced dimension.
  for(const dim of ['ENERGY','TIME','PARKING_TIME','FLAT']){
    const rows=bands.filter(b=>b[0]===dim).sort((a,b)=>a[1]-b[1]||(a[2]??Infinity)-(b[2]??Infinity));
    for(let i=0;i<rows.length;i++)for(let j=i+1;j<rows.length;j++){
      const a=rows[i],b=rows[j],aMax=a[2]??Infinity,bMax=b[2]??Infinity;
      if(Math.max(a[1],b[1])<Math.min(aMax,bMax)-1e-9)return{ok:false,reason:'overlapping_duration_bands'};
    }
  }
  return{ok:true,bands};
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
    let g=groups.get(w.key);
    if(!g){g={...w,plain:[],duration:[]};groups.set(w.key,g);}
    const item={
      rate:parsed.rate,present:parsed.present,
      minSeconds:hasMin?min:0,maxSeconds:hasMax?max:null
    };
    if(hasMin||hasMax)g.duration.push(item);
    else g.plain.push(item);
  }

  // Unrestricted complex rule overrides simple base when present.
  const mergePlainRates=(items,seed,conflictReason)=>{
    const rate={...seed},seen=new Map();
    for(const item of items||[]){
      for(const k of item.present||[]){
        const v=Number(item.rate?.[k]||0);
        if(seen.has(k) && Math.abs(seen.get(k)-v)>1e-9)return{ok:false,reason:conflictReason};
        seen.set(k,v);
        rate[k]=v;
      }
    }
    return{ok:true,rate};
  };

  const unrestricted=groups.get('00:00|24:00|');
  if(unrestricted?.plain?.length){
    const merged=mergePlainRates(unrestricted.plain,base,'conflicting_unrestricted_rules');
    if(!merged.ok)return merged;
    base=merged.rate;
    unrestricted.plain=[];
  }

  const rules=[makeRule('allDay','00:00','24:00',currency,base)];
  for(const g of groups.values()){
    if(g.key==='00:00|24:00|'&&!g.plain.length&&!g.duration.length)continue;
    let rate={...base};
    const db=durationBandsFor(g);
    if(!db.ok)return db;
    const durationBands=db.bands;

    if(g.plain.length){
      const merged=mergePlainRates(g.plain,rate,'conflicting_plain_window_rules');
      if(!merged.ok)return merged;
      rate=merged.rate;
    }

    const isAll=g.start==='00:00'&&g.end==='24:00';
    if(isAll&&!g.days?.length){
      rules[0]=makeRule('allDay','00:00','24:00',currency,rate,null,null,durationBands);
    }else{
      rules.push(makeRule('timeWindow',g.start,g.end,currency,rate,g.days,null,durationBands));
    }
  }
  return{ok:true,pricing:{type:'rules',rules}};
}
function pricingSig(p){return JSON.stringify(p);}
function tileId(lat,lon){return `t_${Math.floor(lat/TILE)}_${Math.floor(lon/TILE)}`;}

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const manifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const driveco=JSON.parse(await fs.readFile(DRIVECO,'utf8'));
const powerdotTech=JSON.parse(await fs.readFile(POWERDOT_TECH,'utf8'));
const vianeoIdentityRaw=(await fs.readFile(VIANEO_IDENTITY,'utf8')).trim();
const vianeoIdentity=vianeoIdentityRaw?JSON.parse(vianeoIdentityRaw):{rows:[]};
const validatedNumericMap=JSON.parse(await fs.readFile(VALIDATED_NUMERIC_MAP,'utf8'));
const validatedS82Map=JSON.parse(await fs.readFile(VALIDATED_S82_MAP,'utf8'));
const validatedMgpMap=JSON.parse(await fs.readFile(VALIDATED_MGP_MAP,'utf8'));
const validatedLe2Map=JSON.parse(await fs.readFile(VALIDATED_LE2_MAP,'utf8'));
let validatedP01Map={mappings:[]};
try{validatedP01Map=JSON.parse(await fs.readFile(VALIDATED_P01_MAP,'utf8'));}catch(e){if(e?.code!=='ENOENT')throw e;}
let validatedBMap={mappings:[]};
try{validatedBMap=JSON.parse(await fs.readFile(VALIDATED_B_MAP,'utf8'));}catch(e){if(e?.code!=='ENOENT')throw e;}
let validatedSaeMap={mappings:[]};
try{validatedSaeMap=JSON.parse(await fs.readFile(VALIDATED_SAE_MAP,'utf8'));}catch(e){if(e?.code!=='ENOENT')throw e;}
let validatedH01Map={mappings:[]};
try{validatedH01Map=JSON.parse(await fs.readFile(VALIDATED_H01_MAP,'utf8'));}catch(e){if(e?.code!=='ENOENT')throw e;}
let validatedAdpMap={mappings:[]};
try{validatedAdpMap=JSON.parse(await fs.readFile(VALIDATED_ADP_MAP,'utf8'));}catch(e){if(e?.code!=='ENOENT')throw e;}
let validatedGenericSmallMap={mappings:[]};
try{validatedGenericSmallMap=JSON.parse(await fs.readFile(VALIDATED_GENERIC_SMALL_MAP,'utf8'));}catch(e){if(e?.code!=='ENOENT')throw e;}
let validatedCustomGyPairMap={groups:[]};
try{validatedCustomGyPairMap=JSON.parse(await fs.readFile(VALIDATED_CUSTOMGY_PAIR_MAP,'utf8'));}catch(e){if(e?.code!=='ENOENT')throw e;}
let validatedCustomGyPdcExtensions={extensions:[]};
try{validatedCustomGyPdcExtensions=JSON.parse(await fs.readFile(VALIDATED_CUSTOMGY_PDC_EXTENSIONS,'utf8'));}catch(e){if(e?.code!=='ENOENT')throw e;}
for(const x of validatedCustomGyPdcExtensions.extensions||[]){
  const m=(mapping.mappings||[]).find(r=>String(r.electroverseLocationPk)===String(x.electroverseLocationPk));
  if(!m)continue;
  if(x.irveStationId&&String(m.irveStationId)!==String(x.irveStationId))continue;
  const set=new Set((m.irvePdcIds||[]).map(String));
  for(const pdc of x.addedPdcs||[]) if(pdc?.pdc)set.add(String(pdc.pdc));
  m.irvePdcIds=[...set];
}
const finalResidualPlan=JSON.parse(await fs.readFile(FINAL_RESIDUAL_PLAN,'utf8'));
const powerdotByEvse=new Map((powerdotTech.evses||[]).map(x=>[norm(x.evseId),x]));
const drivecoNative=[...(driveco.resolved||[]),...(driveco.unresolved||[])];
const drivecoByEvse=new Map(drivecoNative.map(x=>[norm(x.evseId),x]));
const vianeoBySource=new Map((vianeoIdentity.rows||[]).map(x=>[norm(x.sourceRef),x]));
const kwClass=n=>{
  n=Number(n);if(!Number.isFinite(n))return null;
  if(Math.abs(n-22.08)<=1.0||Math.abs(n-22)<=1.0)return 22;
  if(Math.abs(n-50)<=2)return 50;
  if(Math.abs(n-100)<=3)return 100;
  if(Math.abs(n-150)<=4)return 150;
  if(Math.abs(n-180)<=5)return 180;
  if(Math.abs(n-200)<=5)return 200;
  return Math.round(n);
};
const pd1KwClass=n=>{
  n=Number(n);if(!Number.isFinite(n))return null;
  const buckets=[3.7,7.4,11,22,43,50,60,75,100,120,150,160,180,200,240,300,320,360,400];
  let best=null,delta=Infinity;
  for(const b of buckets){const d=Math.abs(n-b);if(d<delta){best=b;delta=d;}}
  return delta<=Math.max(1,best*0.03)?best:Math.round(n*10)/10;
};
const pd1PlugFromStandard=s=>{
  const n=String(s?.name||'');
  if(n==='IEC_62196_T2')return 'T2';
  if(n==='IEC_62196_T2_COMBO')return 'CCS';
  if(n==='CHADEMO')return 'CHA';
  if(n==='DOMESTIC_E')return 'EF';
  return n||'OTHER';
};
const pd1TechKeyFromNative=x=>{
  const kw=pd1KwClass(x?.powerKw);if(kw==null)return null;
  const plugs=[...new Set((x?.plugs||[]).map(String).filter(Boolean))].sort();
  return JSON.stringify({kw,plugs});
};
const pd1TechKeyFromEvse=e=>{
  const cs=e?.connectors||[];if(!cs.length)return null;
  const kw=pd1KwClass(Math.max(...cs.map(c0=>Number(c0.kilowatts)||0)));if(kw==null)return null;
  const plugs=[...new Set(cs.map(c0=>pd1PlugFromStandard(c0.standard)))].sort();
  return JSON.stringify({kw,plugs});
};
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
// Proven post-overlay numeric residuals from the strict residual audit.
// Keys are Electroverse location PK + source EVSE PK. These are accepted only
// when the target remains local and globally unique at build time.
const validatedNumericResidualTargets=new Map(
  (validatedNumericMap.mappings||[]).map(x=>[
    String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk),
    norm(x.targetPdc)
  ])
);
const validatedS82ResidualTargets=new Map(
  (validatedS82Map.mappings||[]).map(x=>[
    String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk),
    norm(x.targetPdc)
  ])
);
const validatedMgpResidualTargets=new Map(
  (validatedMgpMap.mappings||[]).map(x=>[
    String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk),
    norm(x.targetPdc)
  ])
);
const validatedLe2ResidualTargets=new Map(
  (validatedLe2Map.mappings||[]).map(x=>[
    String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk),
    norm(x.targetPdc)
  ])
);
const validatedP01ResidualTargets=new Map(
  (validatedP01Map.mappings||[]).map(x=>[
    String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk),
    norm(x.targetPdc)
  ])
);
const validatedBResidualTargets=new Map(
  (validatedBMap.mappings||[]).map(x=>[
    String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk),
    norm(x.targetPdc)
  ])
);
const validatedSaeResidualTargets=new Map(
  (validatedSaeMap.mappings||[]).map(x=>[
    String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk),
    norm(x.targetPdc)
  ])
);
const validatedH01ResidualTargets=new Map(
  (validatedH01Map.mappings||[]).map(x=>[
    String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk),
    norm(x.targetPdc)
  ])
);
const validatedAdpResidualTargets=new Map(
  (validatedAdpMap.mappings||[]).map(x=>[
    String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk),
    norm(x.targetPdc)
  ])
);
const validatedGenericSmallTargets=new Map(
  (validatedGenericSmallMap.mappings||[]).map(x=>[
    String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk),
    norm(x.targetPdc)
  ])
);
const validatedP01ResidualMetadata=new Map(
  (validatedP01Map.mappings||[]).map(x=>[
    String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk),
    x
  ])
);
const validatedP01AliasesByTarget=new Map();
for(const x of validatedP01Map.aliasMappings||[]){
  const k=norm(x.targetPdc);
  if(!k)continue;
  const a=validatedP01AliasesByTarget.get(k)||[];
  a.push(x);validatedP01AliasesByTarget.set(k,a);
}
const finalResidualIndividualTargets=new Map(
  (finalResidualPlan.individualMappings||[]).map(x=>[
    String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk),
    {target:norm(x.targetPdc),mode:String(x.mode||''),operator:String(x.operator||'UNKNOWN')}
  ])
);
const customGyPairGroupsByLocation=new Map();
for(const g of validatedCustomGyPairMap.groups||[]){
  const k=String(g.electroverseLocationPk);
  const a=customGyPairGroupsByLocation.get(k)||[];
  a.push(g);customGyPairGroupsByLocation.set(k,a);
}
const finalResidualGroupsByLocation=new Map();
for(const g of finalResidualPlan.groupMappings||[]){
  const k=String(g.electroverseLocationPk);
  const a=finalResidualGroupsByLocation.get(k)||[];
  a.push(g);finalResidualGroupsByLocation.set(k,a);
}
const validatedResidualTargets=new Map([
  ...validatedNumericResidualTargets,
  ...validatedS82ResidualTargets,
  ...validatedMgpResidualTargets,
  ...validatedLe2ResidualTargets,
  ...validatedP01ResidualTargets,
  ...validatedBResidualTargets,
  ...validatedSaeResidualTargets,
  ...validatedH01ResidualTargets,
  ...validatedAdpResidualTargets,
  ...validatedGenericSmallTargets,
  ...[...finalResidualIndividualTargets].map(([k,v])=>[k,v.target])
]);
const isValidatedResidualSource=(row,e)=>validatedResidualTargets.has(String(row.electroverseLocationPk)+':'+String(e?.pk??''));
const p01DonorPkSet=new Set((validatedP01Map.mappings||[]).map(x=>String(x.donorElectroverseEvsePk??'')).filter(Boolean));
const p01DonorEvseByPk=new Map();
if(p01DonorPkSet.size){
  for(const sh of manifest.shards||[]){
    const d=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
    for(const row of Object.values(d.stations||{})){
      for(const e of row?.tariff?.evses||[]){
        const pk=String(e?.pk??'');
        if(p01DonorPkSet.has(pk))p01DonorEvseByPk.set(pk,e);
      }
    }
  }
}
const globalPdcOwners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;
  const set=globalPdcOwners.get(k)||new Set();set.add(m.irveStationId);globalPdcOwners.set(k,set);
}

const tiles=new Map(),rejected={},parentGroups=new Map(),p01PriceOnlyGroups=new Map();
const debugNumericSourcePks=new Set(['4179421','4179445','4132457','4132473']);
const debugNumericProfiles=new Map();
const pricingDiagnostics={
  dateRestriction:{evses:0,restrictions:0,withStart:0,withEnd:0,withBoth:0,ranges:{},samples:[]},
  boundedDuration:{evses:0,restrictions:0,bands:{},componentTypes:{},samples:[]},
  thresholdMismatch:{evses:0,pairs:{},samples:[]}
};
const stats={
  cacheLocations:0,cacheEvses:0,physicalRefs:0,exactUniqueNationalEvses:0,
  parentConnectorRefs:0,parentCandidateGroups:0,parentPublishedEvses:0,parentPublishedChildRefs:0,
  ordinalCandidateRefs:0,ordinalPublishedEvses:0,
  genericTailCandidateRefs:0,genericTailPublishedEvses:0,
  suffixIdentityCandidateRefs:0,suffixIdentityPublishedEvses:0,
  trimmedSuffixCandidateRefs:0,trimmedSuffixPublishedEvses:0,
  pd1FinalOrdinalCandidateRefs:0,pd1FinalOrdinalPublishedEvses:0,
  izfHomogeneousGroupCandidateEvses:0,izfHomogeneousGroupPublishedEvses:0,
  viaFinalOrdinalCandidateRefs:0,viaFinalOrdinalPublishedEvses:0,
  viaHomogeneousGroupCandidateEvses:0,viaHomogeneousGroupPublishedEvses:0,
  viaStructuredBasePairCandidateEvses:0,viaStructuredBasePairPublishedEvses:0,
  viaOfficialIdentityCandidateEvses:0,viaOfficialIdentityPublishedEvses:0,
  c55HomogeneousGroupCandidateEvses:0,c55HomogeneousGroupPublishedEvses:0,
  hpcOrdinalGroupCandidateEvses:0,hpcOrdinalGroupPublishedEvses:0,
  s30StructuredChildCandidateEvses:0,s30StructuredChildPublishedEvses:0,
  c55BIndexCandidateEvses:0,c55BIndexPublishedEvses:0,
  validatedNumericResidualCandidateEvses:0,validatedNumericResidualPublishedEvses:0,
  validatedS82ResidualCandidateEvses:0,validatedS82ResidualPublishedEvses:0,
  validatedMgpResidualCandidateEvses:0,validatedMgpResidualPublishedEvses:0,
  validatedLe2ResidualCandidateEvses:0,validatedLe2ResidualPublishedEvses:0,
  validatedP01ResidualCandidateEvses:0,validatedP01ResidualPublishedEvses:0,
  validatedP01PriceOnlyCandidateEvses:0,validatedP01PriceOnlyPublishedEvses:0,
  validatedP01AliasSourceEvses:0,
  finalResidualUniqueSuffixCandidateEvses:0,finalResidualUniqueSuffixPublishedEvses:0,
  finalResidualCommonTailCandidateEvses:0,finalResidualCommonTailPublishedEvses:0,
  finalResidualHomogeneousGroupCandidateEvses:0,finalResidualHomogeneousGroupPublishedEvses:0,
  validatedResidualCompileFailures:{},validatedResidualHeterogeneousConnectors:0,validatedResidualOffersCreated:0,
  connectorPowerVariantEvses:0,connectorPowerVariantOffers:0,connectorPowerVariantConnectors:0,
  drvPowerGroupCandidateEvses:0,drvPowerGroupPublishedEvses:0,drvPowerGroupByKw:{},
  pd1TechnicalGroupCandidateEvses:0,pd1TechnicalGroupPublishedEvses:0,pd1TechnicalGroupByKey:{},
  drvHomogeneousGroupCandidateEvses:0,drvHomogeneousGroupPublishedEvses:0,
  bHomogeneousGroupCandidateEvses:0,bHomogeneousGroupPublishedEvses:0,
  sigHomogeneousGroupCandidateEvses:0,sigHomogeneousGroupPublishedEvses:0,
  qovHomogeneousGroupCandidateEvses:0,qovHomogeneousGroupPublishedEvses:0,
  genericHomogeneousGroupCandidateEvses:0,genericHomogeneousGroupPublishedEvses:0,
  genericHomogeneousGroupByOperator:{},
  genericPriceOnlyGroupCandidateEvses:0,genericPriceOnlyGroupPublishedEvses:0,
  genericPriceOnlyGroupByOperator:{},
  stationHomogeneousBroadcastAuditLocations:0,stationHomogeneousBroadcastAuditTargets:0,stationHomogeneousBroadcastAuditSources:0,
  stationHomogeneousBroadcastAuditByOperator:{},
  stationHomogeneousBroadcastMismatchLocations:0,stationHomogeneousBroadcastMismatchTargets:0,stationHomogeneousBroadcastMismatchSources:0,
  stationHomogeneousBroadcastMismatchByOperator:{},
  stationHomogeneousBroadcastStrictMismatchLocations:0,stationHomogeneousBroadcastStrictMismatchTargets:0,stationHomogeneousBroadcastStrictMismatchSources:0,
  stationHomogeneousBroadcastStrictMismatchByOperator:{},
  stationHomogeneousBroadcastPublishedLocations:0,stationHomogeneousBroadcastPublishedTargets:0,stationHomogeneousBroadcastCoveredSources:0,
  stationHomogeneousBroadcastPublishedByOperator:{},
  durationBandCandidateEvses:0,durationBandPublishedEvses:0,
  duplicatePublishedEvseTargetsBeforeDedup:0,conflictingPublishedEvseTargetsBeforeDedup:0,
  dedupedIdenticalOffers:0,conflictingTargetsDropped:0,
  pricedExactEvses:0,publishedEvses:0,publishedOffers:0,publishedConnectorCount:0
};
function rej(k){rejected[k]=(rejected[k]||0)+1;}

for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    stats.cacheLocations++;
    for(const e0 of row.tariff?.evses||[]){
      if(debugNumericSourcePks.has(String(e0?.pk??''))){
        debugNumericProfiles.set(String(e0.pk),{
          physicalReference:text(e0?.physicalReference),
          connectors:(e0?.connectors||[]).map(c0=>({
            pk:c0?.pk??null,
            powerKw:c0?.kilowatts??null,
            standard:c0?.standard?.name||c0?.standard||null
          }))
        });
      }
    }
    const m=byPk.get(String(row.electroverseLocationPk));
    if(!m){rej('missing_location_mapping');continue;}
    const localRaw=(m.irvePdcIds||row.irvePdcIds||[]).filter(Boolean);
    const localByNorm=new Map(localRaw.map(p=>[norm(p),p]).filter(([k])=>k));
    const local=new Set(localByNorm.keys());
    const lat=Number(m.electroverse?.lat??m.irve?.lat),lon=Number(m.electroverse?.lon??m.irve?.lon);
    if(!Number.isFinite(lat)||!Number.isFinite(lon)){rej('missing_coordinates');continue;}

    // Per-location PD1 technical-group state is declared before earlier identity passes
    // because those passes may safely consult the (initially empty) handled-source set.
    const pd1TechnicalTargets=new Map();
    const pd1TechnicalSourceEvses=new Set();

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

    const trimmedSuffixProposals=[];
    for(const e0 of row.tariff?.evses||[]){
      const pr0=text(e0?.physicalReference);if(!pr0)continue;
      const k0=norm(pr0);
      if(local.has(k0)||ordinalTargets.has(e0)||genericTargets.has(e0)||suffixTargets.has(e0))continue;
      const p0=[...local].filter(p=>{
        if(!k0.startsWith(p)||k0.length<=p.length)return false;
        return /^\d{1,2}$/.test(k0.slice(p.length));
      });
      if(p0.length)continue;
      let hit=null;
      for(let len=Math.min(k0.length-1,20);len>=7;len--){
        const s=k0.slice(-len);
        const matches=[...local].filter(p=>p.endsWith(s));
        if(matches.length!==1)continue;
        const target=matches[0];
        if(reservedTargets.has(target)||claimedSuffixTargets.has(target))continue;
        if((globalPdcOwners.get(target)?.size||0)!==1)continue;
        hit={target,suffix:s};break;
      }
      if(hit)trimmedSuffixProposals.push({e:e0,...hit});
    }
    const trimmedTargetUse=new Map();
    for(const x of trimmedSuffixProposals)trimmedTargetUse.set(x.target,(trimmedTargetUse.get(x.target)||0)+1);
    const trimmedSuffixTargets=new Map();
    for(const x of trimmedSuffixProposals){
      if((trimmedTargetUse.get(x.target)||0)!==1)continue;
      trimmedSuffixTargets.set(x.e,x.target);
    }

    // PD1 lab: strict subgroup ordinal bijection.
    // Some PD1 Electroverse physical references use an unrelated subgroup stem but preserve
    // the final ordinal present on the national PDCs. Promote only when one subgroup maps to
    // exactly one unclaimed PDC prefix with the exact same ordinal set.
    const pd1FinalOrdinalTargets=new Map();
    const localList=[...local];
    const isPd1=localList.some(p=>/^FRPD1E/.test(p));
    if(isPd1){
      const alreadyClaimed=new Set();
      for(const e0 of row.tariff?.evses||[]){
        if(isValidatedResidualSource(row,e0))continue;
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        if(local.has(k0)){alreadyClaimed.add(k0);continue;}
        const p0=localList.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
        if(p0.length===1){alreadyClaimed.add(p0[0]);continue;}
        if(ordinalTargets.has(e0)){alreadyClaimed.add(ordinalTargets.get(e0));continue;}
        if(genericTargets.has(e0)){alreadyClaimed.add(genericTargets.get(e0));continue;}
        if(suffixTargets.has(e0)){alreadyClaimed.add(suffixTargets.get(e0));continue;}
        if(trimmedSuffixTargets.has(e0)){alreadyClaimed.add(trimmedSuffixTargets.get(e0));continue;}
      }
      const unresolved=[];
      for(const e0 of row.tariff?.evses||[]){
        if(isValidatedResidualSource(row,e0))continue;
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        if(local.has(k0)||ordinalTargets.has(e0)||genericTargets.has(e0)||suffixTargets.has(e0)||trimmedSuffixTargets.has(e0))continue;
        const p0=localList.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
        if(p0.length)continue;
        const mm=pr0.match(/^(.*?)[\s_\-\/]*([0-9]{1,2})$/);
        if(!mm||!mm[1])continue;
        unresolved.push({e:e0,stem:norm(mm[1]),ord:Number(mm[2])});
      }
      const groups=new Map();
      for(const x of unresolved){
        const arr=groups.get(x.stem)||[];
        arr.push(x);groups.set(x.stem,arr);
      }
      const available=localList.filter(p=>!alreadyClaimed.has(p));
      const claimedLabTargets=new Set();
      for(const items of groups.values()){
        if(!items.length||new Set(items.map(x=>x.ord)).size!==items.length)continue;
        const wanted=new Set(items.map(x=>x.ord)),matches=[];
        for(const width of [1,2]){
          const byPrefix=new Map();
          for(const p of available){
            if(claimedLabTargets.has(p)||p.length<=width)continue;
            const tail=p.slice(-width);if(!/^\d+$/.test(tail))continue;
            const prefix=p.slice(0,-width),ord=Number(tail);
            const arr=byPrefix.get(prefix)||[];
            arr.push({p,ord});byPrefix.set(prefix,arr);
          }
          for(const rows of byPrefix.values()){
            if(rows.length!==items.length)continue;
            if(new Set(rows.map(r=>r.ord)).size!==rows.length)continue;
            if(rows.some(r=>!wanted.has(r.ord)))continue;
            if(rows.some(r=>(globalPdcOwners.get(r.p)?.size||0)!==1))continue;
            matches.push(rows);
          }
        }
        if(matches.length!==1)continue;
        const byOrd=new Map(matches[0].map(r=>[r.ord,r.p]));
        for(const x of items){
          const target=byOrd.get(x.ord);if(!target)continue;
          pd1FinalOrdinalTargets.set(x.e,target);
          claimedLabTargets.add(target);
        }
      }
    }

    // VIA lab: strict final-ordinal subgroup bijection for unresolved references.
    const viaFinalOrdinalTargets=new Map();
    const localListForVia=[...local];
    if(localListForVia.some(p=>/^FRVIAE/.test(p))){
      const alreadyClaimed=new Set();
      for(const e0 of row.tariff?.evses||[]){
        if(isValidatedResidualSource(row,e0))continue;
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        if(local.has(k0)){alreadyClaimed.add(k0);continue;}
        const p0=localListForVia.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
        if(p0.length===1){alreadyClaimed.add(p0[0]);continue;}
        if(ordinalTargets.has(e0)){alreadyClaimed.add(ordinalTargets.get(e0));continue;}
        if(genericTargets.has(e0)){alreadyClaimed.add(genericTargets.get(e0));continue;}
        if(suffixTargets.has(e0)){alreadyClaimed.add(suffixTargets.get(e0));continue;}
        if(trimmedSuffixTargets.has(e0)){alreadyClaimed.add(trimmedSuffixTargets.get(e0));continue;}
        if(pd1FinalOrdinalTargets.has(e0)){alreadyClaimed.add(pd1FinalOrdinalTargets.get(e0));continue;}
      }
      const unresolved=[];
      for(const e0 of row.tariff?.evses||[]){
        if(isValidatedResidualSource(row,e0))continue;
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        if(local.has(k0)||ordinalTargets.has(e0)||genericTargets.has(e0)||suffixTargets.has(e0)||trimmedSuffixTargets.has(e0)||pd1FinalOrdinalTargets.has(e0))continue;
        const p0=localListForVia.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
        if(p0.length)continue;
        const mm=pr0.match(/^(.*?)[\s_\-\/]*([0-9]{1,2})$/);
        if(!mm||!mm[1])continue;
        unresolved.push({e:e0,stem:norm(mm[1]),ord:Number(mm[2])});
      }
      const groups=new Map();
      for(const x of unresolved){
        const arr=groups.get(x.stem)||[];
        arr.push(x);groups.set(x.stem,arr);
      }
      const available=localListForVia.filter(p=>!alreadyClaimed.has(p));
      const claimedViaTargets=new Set();
      for(const items of groups.values()){
        if(!items.length||new Set(items.map(x=>x.ord)).size!==items.length)continue;
        const wanted=new Set(items.map(x=>x.ord)),matches=[];
        for(const width of [1,2]){
          const byPrefix=new Map();
          for(const p of available){
            if(claimedViaTargets.has(p)||p.length<=width)continue;
            const tail=p.slice(-width);if(!/^\d+$/.test(tail))continue;
            const prefix=p.slice(0,-width),ord=Number(tail);
            const arr=byPrefix.get(prefix)||[];
            arr.push({p,ord});byPrefix.set(prefix,arr);
          }
          for(const rows of byPrefix.values()){
            if(rows.length!==items.length)continue;
            if(new Set(rows.map(r=>r.ord)).size!==rows.length)continue;
            if(rows.some(r=>!wanted.has(r.ord)))continue;
            if(rows.some(r=>(globalPdcOwners.get(r.p)?.size||0)!==1))continue;
            matches.push(rows);
          }
        }
        if(matches.length!==1)continue;
        const byOrd=new Map(matches[0].map(r=>[r.ord,r.p]));
        for(const x of items){
          const target=byOrd.get(x.ord);if(!target)continue;
          viaFinalOrdinalTargets.set(x.e,target);
          claimedViaTargets.add(target);
        }
      }
    }

    // IZF lab: exact unresolved-set mapping when individual MAT references are non-identifying.
    // Accept only when the unresolved EVSE set and unclaimed national PDC set have identical
    // cardinality, every PDC is globally unique, and every unresolved EVSE has identical
    // compiled pricing and connector count. The tariff is therefore valid for every target
    // regardless of the unknown 1:1 ordering inside the exact set.
    const izfGroupTargets=new Map();
    const localListForIzf=[...local];
    if(localListForIzf.some(p=>/^FRIZFE/.test(p))){
      const alreadyClaimed=new Set();
      const unresolved=[];
      for(const e0 of row.tariff?.evses||[]){
        if(isValidatedResidualSource(row,e0))continue;
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        if(local.has(k0)){alreadyClaimed.add(k0);continue;}
        const p0=localListForIzf.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
        if(p0.length===1){alreadyClaimed.add(p0[0]);continue;}
        if(ordinalTargets.has(e0)){alreadyClaimed.add(ordinalTargets.get(e0));continue;}
        if(genericTargets.has(e0)){alreadyClaimed.add(genericTargets.get(e0));continue;}
        if(suffixTargets.has(e0)){alreadyClaimed.add(suffixTargets.get(e0));continue;}
        if(trimmedSuffixTargets.has(e0)){alreadyClaimed.add(trimmedSuffixTargets.get(e0));continue;}
        if(pd1FinalOrdinalTargets.has(e0)){alreadyClaimed.add(pd1FinalOrdinalTargets.get(e0));continue;}
        if(viaFinalOrdinalTargets.has(e0)){alreadyClaimed.add(viaFinalOrdinalTargets.get(e0));continue;}
        unresolved.push(e0);
      }
      const unclaimed=localListForIzf.filter(p=>!alreadyClaimed.has(p));
      if(unresolved.length>=2 && unresolved.length===unclaimed.length &&
         unclaimed.every(p=>(globalPdcOwners.get(p)?.size||0)===1)){
        const compiledRows=[];
        let valid=true;
        for(const e0 of unresolved){
          const connectors=e0?.connectors||[];
          if(!connectors.length){valid=false;break;}
          const compiled=[];
          for(const c0 of connectors){
            const x=compileConnector(c0);if(!x.ok){valid=false;break;}
            compiled.push({pricing:x.pricing,connectorPk:c0.pk??null});
          }
          if(!valid)break;
          const unique=[...new Map(compiled.map(x=>[pricingSig(x.pricing),x.pricing])).values()];
          if(unique.length!==1){valid=false;break;}
          compiledRows.push({e:e0,pricing:unique[0],connectorCount:connectors.length});
        }
        if(valid && compiledRows.length===unresolved.length){
          const pricingSigs=new Set(compiledRows.map(x=>pricingSig(x.pricing)));
          const connectorCounts=new Set(compiledRows.map(x=>x.connectorCount));
          if(pricingSigs.size===1 && connectorCounts.size===1){
            const sharedPricing=compiledRows[0].pricing;
            const connectorCount=compiledRows[0].connectorCount;
            for(const p of unclaimed)izfGroupTargets.set(p,{pricing:sharedPricing,connectorCount,sourceEvses:unresolved});
          }
        }
      }
    }

    if(izfGroupTargets.size){
      const sourceEvses=[...new Set([...izfGroupTargets.values()].flatMap(x=>x.sourceEvses))];
      const shared=[...izfGroupTargets.values()][0];
      const currency=shared.pricing.rules?.[0]?.currency||'EUR';
      for(const targetNorm of izfGroupTargets.keys()){
        const targetPdc=localByNorm.get(targetNorm);
        const offer={
          id:`electroverse-evse-izf-group:${row.electroverseLocationPk}:${targetNorm}`,
          provider:'Electroverse',
          countries:['FR'],
          currency,
          priority:80,
          verifiedScope:'exact_evse_group',
          evseIds:[targetPdc],
          pricing:shared.pricing,
          metadata:{
            verified:true,
            identityMode:'strict_izf_homogeneous_exact_set',
            electroverseLocationPk:String(row.electroverseLocationPk),
            electroverseEvsePks:sourceEvses.map(e=>e.pk??null),
            physicalReferences:sourceEvses.map(e=>text(e?.physicalReference)),
            connectorCount:shared.connectorCount,
            sourceGroupSize:sourceEvses.length,
            targetGroupSize:izfGroupTargets.size,
            tariffHash:row.tariffHash||null,
            fetchedAt:row.fetchedAt||null,
            source:'Electroverse tariff cache'
          }
        };
        const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);
        tiles.get(id).push(offer);
        stats.izfHomogeneousGroupCandidateEvses++;
        stats.izfHomogeneousGroupPublishedEvses++;
        stats.pricedExactEvses++;
        stats.publishedEvses++;stats.publishedOffers++;stats.publishedConnectorCount+=shared.connectorCount;
      }
    }
    const izfGroupedSourceEvses=new Set(
      izfGroupTargets.size ? [...izfGroupTargets.values()][0].sourceEvses : []
    );

    // VIA lab: homogeneous exact-set fallback after strict ordinal mappings.
    const viaGroupTargets=new Map();
    if(localListForVia.some(p=>/^FRVIAE/.test(p))){
      const alreadyClaimed=new Set();
      const unresolved=[];
      for(const e0 of row.tariff?.evses||[]){
        if(isValidatedResidualSource(row,e0))continue;
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        if(local.has(k0)){alreadyClaimed.add(k0);continue;}
        const p0=localListForVia.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
        if(p0.length===1){alreadyClaimed.add(p0[0]);continue;}
        if(ordinalTargets.has(e0)){alreadyClaimed.add(ordinalTargets.get(e0));continue;}
        if(genericTargets.has(e0)){alreadyClaimed.add(genericTargets.get(e0));continue;}
        if(suffixTargets.has(e0)){alreadyClaimed.add(suffixTargets.get(e0));continue;}
        if(trimmedSuffixTargets.has(e0)){alreadyClaimed.add(trimmedSuffixTargets.get(e0));continue;}
        if(pd1FinalOrdinalTargets.has(e0)){alreadyClaimed.add(pd1FinalOrdinalTargets.get(e0));continue;}
        if(viaFinalOrdinalTargets.has(e0)){alreadyClaimed.add(viaFinalOrdinalTargets.get(e0));continue;}
        unresolved.push(e0);
      }
      const unclaimed=localListForVia.filter(p=>!alreadyClaimed.has(p));
      if(unresolved.length>=2 && unresolved.length===unclaimed.length &&
         unclaimed.every(p=>(globalPdcOwners.get(p)?.size||0)===1)){
        const compiledRows=[];
        let valid=true;
        for(const e0 of unresolved){
          const connectors=e0?.connectors||[];
          if(!connectors.length){valid=false;break;}
          const compiled=[];
          for(const c0 of connectors){
            const x=compileConnector(c0);if(!x.ok){valid=false;break;}
            compiled.push({pricing:x.pricing,connectorPk:c0.pk??null});
          }
          if(!valid)break;
          const unique=[...new Map(compiled.map(x=>[pricingSig(x.pricing),x.pricing])).values()];
          if(unique.length!==1){valid=false;break;}
          compiledRows.push({e:e0,pricing:unique[0],connectorCount:connectors.length});
        }
        if(valid&&compiledRows.length===unresolved.length){
          const pricingSigs=new Set(compiledRows.map(x=>pricingSig(x.pricing)));
          const connectorCounts=new Set(compiledRows.map(x=>x.connectorCount));
          if(pricingSigs.size===1&&connectorCounts.size===1){
            const sharedPricing=compiledRows[0].pricing;
            const connectorCount=compiledRows[0].connectorCount;
            for(const p of unclaimed)viaGroupTargets.set(p,{pricing:sharedPricing,connectorCount,sourceEvses:unresolved});
          }
        }
      }
    }

    if(viaGroupTargets.size){
      const sourceEvses=[...new Set([...viaGroupTargets.values()].flatMap(x=>x.sourceEvses))];
      const shared=[...viaGroupTargets.values()][0];
      const currency=shared.pricing.rules?.[0]?.currency||'EUR';
      for(const targetNorm of viaGroupTargets.keys()){
        const targetPdc=localByNorm.get(targetNorm);
        const offer={
          id:`electroverse-evse-via-group:${row.electroverseLocationPk}:${targetNorm}`,
          provider:'Electroverse',
          countries:['FR'],
          currency,
          priority:80,
          verifiedScope:'exact_evse_group',
          evseIds:[targetPdc],
          pricing:shared.pricing,
          metadata:{
            verified:true,
            identityMode:'strict_via_homogeneous_exact_set',
            electroverseLocationPk:String(row.electroverseLocationPk),
            electroverseEvsePks:sourceEvses.map(e=>e.pk??null),
            physicalReferences:sourceEvses.map(e=>text(e?.physicalReference)),
            connectorCount:shared.connectorCount,
            sourceGroupSize:sourceEvses.length,
            targetGroupSize:viaGroupTargets.size,
            tariffHash:row.tariffHash||null,
            fetchedAt:row.fetchedAt||null,
            source:'Electroverse tariff cache'
          }
        };
        const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);
        tiles.get(id).push(offer);
        stats.viaHomogeneousGroupCandidateEvses++;
        stats.viaHomogeneousGroupPublishedEvses++;
        stats.pricedExactEvses++;
        stats.publishedEvses++;stats.publishedOffers++;stats.publishedConnectorCount+=shared.connectorCount;
      }
    }
    const viaGroupedSourceEvses=new Set(
      viaGroupTargets.size ? [...viaGroupTargets.values()][0].sourceEvses : []
    );

    // 55C lab: homogeneous exact-set fallback after all existing identity families.
    const c55GroupTargets=new Map();
    const localListFor55C=[...local];
    if(localListFor55C.some(p=>/^FR55CE/.test(p))){
      const alreadyClaimed=new Set();
      const unresolved=[];
      for(const e0 of row.tariff?.evses||[]){
        if(isValidatedResidualSource(row,e0))continue;
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        if(local.has(k0)){alreadyClaimed.add(k0);continue;}
        const p0=localListFor55C.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
        if(p0.length===1){alreadyClaimed.add(p0[0]);continue;}
        if(ordinalTargets.has(e0)){alreadyClaimed.add(ordinalTargets.get(e0));continue;}
        if(genericTargets.has(e0)){alreadyClaimed.add(genericTargets.get(e0));continue;}
        if(suffixTargets.has(e0)){alreadyClaimed.add(suffixTargets.get(e0));continue;}
        if(trimmedSuffixTargets.has(e0)){alreadyClaimed.add(trimmedSuffixTargets.get(e0));continue;}
        if(pd1FinalOrdinalTargets.has(e0)){alreadyClaimed.add(pd1FinalOrdinalTargets.get(e0));continue;}
        if(viaFinalOrdinalTargets.has(e0)){alreadyClaimed.add(viaFinalOrdinalTargets.get(e0));continue;}
        if(izfGroupedSourceEvses.has(e0)||viaGroupedSourceEvses.has(e0))continue;
        unresolved.push(e0);
      }
      const allUnclaimed=localListFor55C.filter(p=>!alreadyClaimed.has(p));
      const unclaimed55=allUnclaimed.filter(p=>/^FR55CE/.test(p));
      if(unresolved.length>=1 && unresolved.length===unclaimed55.length &&
         allUnclaimed.length===unclaimed55.length &&
         unclaimed55.every(p=>(globalPdcOwners.get(p)?.size||0)===1)){
        const compiledRows=[];
        let valid=true;
        for(const e0 of unresolved){
          const connectors=e0?.connectors||[];
          if(!connectors.length){valid=false;break;}
          const compiled=[];
          for(const c0 of connectors){
            const x=compileConnector(c0);if(!x.ok){valid=false;break;}
            compiled.push({pricing:x.pricing,connectorPk:c0.pk??null});
          }
          if(!valid)break;
          const unique=[...new Map(compiled.map(x=>[pricingSig(x.pricing),x.pricing])).values()];
          if(unique.length!==1){valid=false;break;}
          compiledRows.push({e:e0,pricing:unique[0],connectorCount:connectors.length});
        }
        if(valid&&compiledRows.length===unresolved.length){
          const pricingSigs=new Set(compiledRows.map(x=>pricingSig(x.pricing)));
          const connectorCounts=new Set(compiledRows.map(x=>x.connectorCount));
          if(pricingSigs.size===1&&connectorCounts.size===1){
            const sharedPricing=compiledRows[0].pricing;
            const connectorCount=compiledRows[0].connectorCount;
            for(const p of unclaimed55)c55GroupTargets.set(p,{pricing:sharedPricing,connectorCount,sourceEvses:unresolved});
          }
        }
      }
    }

    if(c55GroupTargets.size){
      const sourceEvses=[...new Set([...c55GroupTargets.values()].flatMap(x=>x.sourceEvses))];
      const shared=[...c55GroupTargets.values()][0];
      const currency=shared.pricing.rules?.[0]?.currency||'EUR';
      for(const targetNorm of c55GroupTargets.keys()){
        const targetPdc=localByNorm.get(targetNorm);
        const offer={
          id:`electroverse-evse-55c-group:${row.electroverseLocationPk}:${targetNorm}`,
          provider:'Electroverse',
          countries:['FR'],
          currency,
          priority:80,
          verifiedScope:'exact_evse_group',
          evseIds:[targetPdc],
          pricing:shared.pricing,
          metadata:{
            verified:true,
            identityMode:'strict_55c_homogeneous_exact_set',
            electroverseLocationPk:String(row.electroverseLocationPk),
            electroverseEvsePks:sourceEvses.map(e=>e.pk??null),
            physicalReferences:sourceEvses.map(e=>text(e?.physicalReference)),
            connectorCount:shared.connectorCount,
            sourceGroupSize:sourceEvses.length,
            targetGroupSize:c55GroupTargets.size,
            tariffHash:row.tariffHash||null,
            fetchedAt:row.fetchedAt||null,
            source:'Electroverse tariff cache'
          }
        };
        const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);
        tiles.get(id).push(offer);
        stats.c55HomogeneousGroupCandidateEvses++;
        stats.c55HomogeneousGroupPublishedEvses++;
        stats.pricedExactEvses++;
        stats.publishedEvses++;stats.publishedOffers++;stats.publishedConnectorCount+=shared.connectorCount;
      }
    }
    const c55GroupedSourceEvses=new Set(
      c55GroupTargets.size ? [...c55GroupTargets.values()][0].sourceEvses : []
    );

    // HPC lab: group duplicate numeric physical references by ordinal and map them
    // to globally unique HPC PDCs whose final three digits encode the same ordinal.
    // Multiple Electroverse entries sharing an ordinal are accepted only when every
    // connector compiles and all pricing is homogeneous; their connector sets are aggregated.
    const hpcGroupTargets=new Map();
    const hpcGroupedSourceEvses=new Set();
    const localListForHpc=[...local];
    if(localListForHpc.some(p=>/^FRHPCE/.test(p))){
      const alreadyClaimed=new Set();
      const unresolved=[];
      for(const e0 of row.tariff?.evses||[]){
        if(isValidatedResidualSource(row,e0))continue;
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        if(local.has(k0)){alreadyClaimed.add(k0);continue;}
        const p0=localListForHpc.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
        if(p0.length===1){alreadyClaimed.add(p0[0]);continue;}
        if(ordinalTargets.has(e0)){alreadyClaimed.add(ordinalTargets.get(e0));continue;}
        if(genericTargets.has(e0)){alreadyClaimed.add(genericTargets.get(e0));continue;}
        if(suffixTargets.has(e0)){alreadyClaimed.add(suffixTargets.get(e0));continue;}
        if(trimmedSuffixTargets.has(e0)){alreadyClaimed.add(trimmedSuffixTargets.get(e0));continue;}
        if(pd1FinalOrdinalTargets.has(e0)){alreadyClaimed.add(pd1FinalOrdinalTargets.get(e0));continue;}
        if(viaFinalOrdinalTargets.has(e0)){alreadyClaimed.add(viaFinalOrdinalTargets.get(e0));continue;}
        if(izfGroupedSourceEvses.has(e0)||viaGroupedSourceEvses.has(e0)||c55GroupedSourceEvses.has(e0))continue;
        if(!/^\d{1,2}$/.test(pr0.trim()))continue;
        unresolved.push({e:e0,ord:Number(pr0.trim())});
      }
      const unclaimed=localListForHpc.filter(p=>!alreadyClaimed.has(p)&&/^FRHPCE/.test(p));
      const byOrd=new Map();
      for(const x of unresolved){
        const arr=byOrd.get(x.ord)||[];arr.push(x.e);byOrd.set(x.ord,arr);
      }
      const pdcByOrd=new Map();
      let pdcValid=true;
      for(const p of unclaimed){
        const m=p.match(/(\d{3})$/);
        if(!m){pdcValid=false;break;}
        const ord=Number(m[1]);
        if(!Number.isFinite(ord)||pdcByOrd.has(ord)){pdcValid=false;break;}
        if((globalPdcOwners.get(p)?.size||0)!==1){pdcValid=false;break;}
        pdcByOrd.set(ord,p);
      }
      const sourceOrds=[...byOrd.keys()].sort((a,b)=>a-b);
      const targetOrds=[...pdcByOrd.keys()].sort((a,b)=>a-b);
      const exactOrdSet=pdcValid && sourceOrds.length===targetOrds.length &&
        sourceOrds.every((v,i)=>v===targetOrds[i]);
      if(exactOrdSet&&sourceOrds.length){
        for(const ord of sourceOrds){
          const es=byOrd.get(ord)||[];
          const compiledAll=[];
          let valid=true;
          for(const e0 of es){
            const connectors=e0?.connectors||[];
            if(!connectors.length){valid=false;break;}
            for(const c0 of connectors){
              const x=compileConnector(c0);if(!x.ok){valid=false;break;}
              compiledAll.push({pricing:x.pricing,connectorPk:c0.pk??null});
            }
            if(!valid)break;
          }
          if(!valid||!compiledAll.length)continue;
          const unique=[...new Map(compiledAll.map(x=>[pricingSig(x.pricing),x.pricing])).values()];
          if(unique.length!==1)continue;
          const targetNorm=pdcByOrd.get(ord);
          hpcGroupTargets.set(targetNorm,{
            pricing:unique[0],
            connectorPks:compiledAll.map(x=>x.connectorPk),
            sourceEvses:es
          });
          for(const e0 of es)hpcGroupedSourceEvses.add(e0);
        }
      }
    }

    if(hpcGroupTargets.size){
      for(const [targetNorm,g] of hpcGroupTargets.entries()){
        const targetPdc=localByNorm.get(targetNorm);
        const currency=g.pricing.rules?.[0]?.currency||'EUR';
        const offer={
          id:`electroverse-evse-hpc-ordinal:${row.electroverseLocationPk}:${targetNorm}`,
          provider:'Electroverse',
          countries:['FR'],
          currency,
          priority:80,
          verifiedScope:'exact_evse_group',
          evseIds:[targetPdc],
          pricing:g.pricing,
          metadata:{
            verified:true,
            identityMode:'strict_hpc_duplicate_ordinal_to_three_digit_pdc',
            electroverseLocationPk:String(row.electroverseLocationPk),
            electroverseEvsePks:g.sourceEvses.map(e=>e.pk??null),
            physicalReferences:g.sourceEvses.map(e=>text(e?.physicalReference)),
            connectorPks:g.connectorPks,
            connectorCount:g.connectorPks.length,
            sourceEntryCount:g.sourceEvses.length,
            tariffHash:row.tariffHash||null,
            fetchedAt:row.fetchedAt||null,
            source:'Electroverse tariff cache'
          }
        };
        const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);
        tiles.get(id).push(offer);
        stats.hpcOrdinalGroupCandidateEvses++;
        stats.hpcOrdinalGroupPublishedEvses++;
        stats.pricedExactEvses++;
        stats.publishedEvses++;stats.publishedOffers++;stats.publishedConnectorCount+=g.connectorPks.length;
      }
    }

    // S30 structured child identity.
    // FR*S30*E30008*001*1*2 and *2*2 -> FRS30E300080012:
    // remove the penultimate source segment (connector branch) and keep the final child ordinal.
    // Multiple source EVSEs may collapse to one national PDC only when all compiled connector
    // pricing is homogeneous. Targets must be local and globally unique.
    const s30StructuredTargets=new Map();
    const s30StructuredSourceEvses=new Set();
    {
      const byTarget=new Map();
      for(const e0 of row.tariff?.evses||[]){
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        if(isValidatedResidualSource(row,e0))continue;
        if(local.has(k0))continue;
        const parentCandidates=[...local].filter(p=>{
          if(!k0.startsWith(p)||k0.length<=p.length)return false;
          return /^\d{1,2}$/.test(k0.slice(p.length));
        });
        if(parentCandidates.length===1)continue;
        if(ordinalTargets.has(e0)||genericTargets.has(e0)||suffixTargets.has(e0)||trimmedSuffixTargets.has(e0)||
           pd1FinalOrdinalTargets.has(e0)||viaFinalOrdinalTargets.has(e0)||hpcGroupedSourceEvses.has(e0))continue;
        const mm=pr0.match(/^FR\*S30\*(E[0-9A-Z]+)\*([0-9A-Z]+)\*([0-9]+)\*([0-9]+)$/i);
        if(!mm)continue;
        const target=norm('FRS30'+mm[1]+mm[2]+mm[4]);
        if(!local.has(target))continue;
        if((globalPdcOwners.get(target)?.size||0)!==1)continue;
        const arr=byTarget.get(target)||[];arr.push(e0);byTarget.set(target,arr);
      }
      for(const [target,es] of byTarget){
        if(!es.length)continue;
        const compiledAll=[];let valid=true;
        for(const e0 of es){
          const connectors=e0?.connectors||[];
          if(!connectors.length){valid=false;break;}
          for(const c0 of connectors){
            const x=compileConnector(c0);if(!x.ok){valid=false;break;}
            compiledAll.push({pricing:x.pricing,connectorPk:c0.pk??null});
          }
          if(!valid)break;
        }
        if(!valid||!compiledAll.length)continue;
        const unique=[...new Map(compiledAll.map(x=>[pricingSig(x.pricing),x.pricing])).values()];
        if(unique.length!==1)continue;
        s30StructuredTargets.set(target,{
          pricing:unique[0],
          connectorPks:compiledAll.map(x=>x.connectorPk),
          sourceEvses:es
        });
        for(const e0 of es)s30StructuredSourceEvses.add(e0);
      }
    }
    if(s30StructuredTargets.size){
      for(const [targetNorm,g] of s30StructuredTargets){
        const targetPdc=localByNorm.get(targetNorm);
        const currency=g.pricing.rules?.[0]?.currency||'EUR';
        const offer={
          id:`electroverse-evse-s30-child:${row.electroverseLocationPk}:${targetNorm}`,
          provider:'Electroverse',countries:['FR'],currency,priority:80,
          verifiedScope:'exact_evse_group',evseIds:[targetPdc],pricing:g.pricing,
          metadata:{
            verified:true,identityMode:'strict_s30_structured_child_collapse',
            electroverseLocationPk:String(row.electroverseLocationPk),
            electroverseEvsePks:g.sourceEvses.map(e=>e.pk??null),
            physicalReferences:g.sourceEvses.map(e=>text(e?.physicalReference)),
            connectorPks:g.connectorPks,connectorCount:g.connectorPks.length,
            sourceEntryCount:g.sourceEvses.length,
            tariffHash:row.tariffHash||null,fetchedAt:row.fetchedAt||null,
            source:'Electroverse tariff cache'
          }
        };
        const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);tiles.get(id).push(offer);
        stats.s30StructuredChildCandidateEvses++;
        stats.s30StructuredChildPublishedEvses++;
        stats.pricedExactEvses++;stats.publishedEvses++;stats.publishedOffers++;stats.publishedConnectorCount+=g.connectorPks.length;
      }
    }

    // VIA structured base-pair identity.
    // Example: 164006-01 -> FRVIAE20164006011, 164006-02 -> ...012,
    // 164006-03 -> ...021. The source station stem must be embedded verbatim in the
    // national PDC base (prefixed by VIA's leading "20"), every target must be globally
    // unique, and the national connector suffix must be exactly a 1/2 pair.
    const viaStructuredBasePairTargets=new Map();
    {
      const viaMissing=[...local].filter(p=>p.startsWith('FRVIAE'));
      if(viaMissing.length){
        const proposals=[];
        for(const e0 of row.tariff?.evses||[]){
          const pr0=text(e0?.physicalReference);if(!pr0)continue;
          const k0=norm(pr0);
          if(local.has(k0)||ordinalTargets.has(e0)||genericTargets.has(e0)||suffixTargets.has(e0)||trimmedSuffixTargets.has(e0)||pd1FinalOrdinalTargets.has(e0)||viaFinalOrdinalTargets.has(e0))continue;
          const mm=pr0.match(/^(\d{5,8})-(\d{2})$/);
          if(!mm)continue;
          const stem=mm[1],n=Number(mm[2]);
          if(!Number.isFinite(n)||n<1)continue;
          const g=Math.ceil(n/2),connector=((n-1)%2)+1;
          const suffix=String(g).padStart(2,'0')+String(connector);
          const expectedBase='FRVIAE20'+stem;
          const hits=viaMissing.filter(p=>p.startsWith(expectedBase)&&p.endsWith(suffix));
          if(hits.length!==1)continue;
          const target=hits[0];
          if((globalPdcOwners.get(target)?.size||0)!==1)continue;
          proposals.push({e:e0,target,stem});
        }
        const byStem=new Map();
        for(const x of proposals){const a=byStem.get(x.stem)||[];a.push(x);byStem.set(x.stem,a);}
        for(const [stem,items] of byStem){
          if(new Set(items.map(x=>x.e)).size!==items.length||new Set(items.map(x=>x.target)).size!==items.length)continue;
          const sameBase=viaMissing.filter(p=>p.startsWith('FRVIAE20'+stem));
          if(!sameBase.length)continue;
          // Partial strict mapping: additional national connectors (e.g. ...013)
          // do not invalidate exact source-derived targets ...011/...012.
          // Only the explicitly derivable targets are published; extras remain fail-closed.
          for(const x of items)viaStructuredBasePairTargets.set(x.e,x.target);
        }
      }
    }

    // Vianeo official identity map from the France canonical direct inventory.
    // The compact map is source-reference -> official national PDC, derived from
    // stationName + evseId connector ordinal. Apply only to sources still unresolved
    // by earlier identity families, with local and globally unique targets.
    const viaOfficialTargets=new Map();
    {
      const proposals=[];
      for(const e0 of row.tariff?.evses||[]){
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        if(local.has(k0)||ordinalTargets.has(e0)||genericTargets.has(e0)||suffixTargets.has(e0)||
           trimmedSuffixTargets.has(e0)||pd1FinalOrdinalTargets.has(e0)||viaFinalOrdinalTargets.has(e0)||
           viaStructuredBasePairTargets.has(e0))continue;
        const d=vianeoBySource.get(k0);if(!d)continue;
        const target=norm(d.targetPdc);if(!target||!local.has(target))continue;
        if((globalPdcOwners.get(target)?.size||0)!==1)continue;
        proposals.push({e:e0,target});
      }
      const targetUse=new Map();
      for(const x of proposals)targetUse.set(x.target,(targetUse.get(x.target)||0)+1);
      for(const x of proposals){
        if((targetUse.get(x.target)||0)!==1)continue;
        viaOfficialTargets.set(x.e,x.target);
      }
    }

    // 55C structured B-index identity: B01 -> suffix 0, B02 -> suffix 1, ...
    // Apply only when every unresolved Bxx reference is unique, the full remaining
    // 55C target set has the exact matching zero-based suffix set, and every target
    // PDC is globally unique. This supports heterogeneous per-EVSE pricing safely.
    const c55BIndexTargets=new Map();
    const c55BIndexSourceEvses=new Set();
    {
      const local55=[...local].filter(p=>p.startsWith('FR55CE'));
      if(local55.length){
        const claimed=new Set();
        const unresolved=[];
        for(const e0 of row.tariff?.evses||[]){
          const pr0=text(e0?.physicalReference);if(!pr0)continue;
          const k0=norm(pr0);
          if(local.has(k0)){claimed.add(k0);continue;}
          const p0=[...local].filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
          if(p0.length===1){claimed.add(p0[0]);continue;}
          if(ordinalTargets.has(e0)){claimed.add(ordinalTargets.get(e0));continue;}
          if(genericTargets.has(e0)){claimed.add(genericTargets.get(e0));continue;}
          if(suffixTargets.has(e0)){claimed.add(suffixTargets.get(e0));continue;}
          if(trimmedSuffixTargets.has(e0)){claimed.add(trimmedSuffixTargets.get(e0));continue;}
          if(pd1FinalOrdinalTargets.has(e0)){claimed.add(pd1FinalOrdinalTargets.get(e0));continue;}
          if(viaFinalOrdinalTargets.has(e0)){claimed.add(viaFinalOrdinalTargets.get(e0));continue;}
          if(izfGroupedSourceEvses.has(e0)||viaGroupedSourceEvses.has(e0)||c55GroupedSourceEvses.has(e0)||hpcGroupedSourceEvses.has(e0)||pd1TechnicalSourceEvses.has(e0))continue;
          const mm=pr0.match(/^B(\d{2})(?:\b|\s|-)/i)||pr0.match(/^B(\d{2})$/i);
          if(!mm)continue;
          unresolved.push({e:e0,n:Number(mm[1]),raw:pr0});
        }
        const unclaimed55=local55.filter(p=>!claimed.has(p));
        const uniqueNs=new Set(unresolved.map(x=>x.n));
        const alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
        const bySuffixIndex=new Map();
        let targetsOk=unclaimed55.length>0;
        for(const p of unclaimed55){
          const idx=alphabet.indexOf(p.slice(-1));
          if(idx<0||bySuffixIndex.has(idx)||(globalPdcOwners.get(p)?.size||0)!==1){targetsOk=false;break;}
          bySuffixIndex.set(idx,p);
        }
        const expected=[...uniqueNs].map(n=>n-1).sort((a,b)=>a-b);
        const targetIdx=[...bySuffixIndex.keys()].sort((a,b)=>a-b);
        const exactSet=targetsOk && unresolved.length===uniqueNs.size &&
          expected.length===targetIdx.length && expected.every((v,i)=>v===targetIdx[i]);
        if(exactSet){
          for(const x of unresolved){
            const targetNorm=bySuffixIndex.get(x.n-1);
            if(!targetNorm)continue;
            c55BIndexTargets.set(x.e,targetNorm);
            c55BIndexSourceEvses.add(x.e);
          }
        }
      }
    }

    // Preserve the existing generic single-operator exact-set fallback whenever it
    // is already fully valid on a PD1 location. The technical-group rule is additive:
    // it must not consume source EVSEs or targets from a baseline generic exact-set.
    let pd1BaselineGenericProtected=false;
    if([...local].some(p=>p.startsWith('FRPD1E'))){
      const claimed=new Set();
      const unresolved=[];
      for(const e0 of row.tariff?.evses||[]){
        if(isValidatedResidualSource(row,e0))continue;
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        if(local.has(k0)){claimed.add(k0);continue;}
        const p0=[...local].filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
        if(p0.length===1){claimed.add(p0[0]);continue;}
        if(ordinalTargets.has(e0)){claimed.add(ordinalTargets.get(e0));continue;}
        if(genericTargets.has(e0)){claimed.add(genericTargets.get(e0));continue;}
        if(suffixTargets.has(e0)){claimed.add(suffixTargets.get(e0));continue;}
        if(trimmedSuffixTargets.has(e0)){claimed.add(trimmedSuffixTargets.get(e0));continue;}
        if(pd1FinalOrdinalTargets.has(e0)){claimed.add(pd1FinalOrdinalTargets.get(e0));continue;}
        if(viaFinalOrdinalTargets.has(e0)){claimed.add(viaFinalOrdinalTargets.get(e0));continue;}
        if(c55BIndexTargets.has(e0)){claimed.add(c55BIndexTargets.get(e0));continue;}
        if(izfGroupedSourceEvses.has(e0)||viaGroupedSourceEvses.has(e0)||c55GroupedSourceEvses.has(e0)||hpcGroupedSourceEvses.has(e0))continue;
        unresolved.push(e0);
      }
      const unclaimed=[...local].filter(p=>!claimed.has(p));
      const opCode=p=>{
        const m=String(p||'').match(/^FR([A-Z0-9]{1,6})E/);
        return m?m[1]:null;
      };
      const opSet=new Set(unclaimed.map(opCode).filter(Boolean));
      const protectedOp=opSet.size===1?[...opSet][0]:null;
      const recognizedSingleOperator=unclaimed.length>0 && opSet.size===1 &&
        String(protectedOp||'').startsWith('PD1') && unclaimed.every(p=>opCode(p));
      if(recognizedSingleOperator && unresolved.length===unclaimed.length &&
         unclaimed.every(p=>(globalPdcOwners.get(p)?.size||0)===1)){
        const compiledRows=[];
        let valid=true;
        for(const e0 of unresolved){
          const connectors=e0?.connectors||[];
          if(!connectors.length){valid=false;break;}
          const compiled=[];
          for(const c0 of connectors){
            const x=compileConnector(c0);if(!x.ok){valid=false;break;}
            compiled.push({pricing:x.pricing,connectorPk:c0.pk??null});
          }
          if(!valid)break;
          const unique=[...new Map(compiled.map(x=>[pricingSig(x.pricing),x.pricing])).values()];
          if(unique.length!==1){valid=false;break;}
          compiledRows.push({e:e0,pricing:unique[0],connectorCount:connectors.length});
        }
        if(valid&&compiledRows.length===unresolved.length&&compiledRows.length){
          const pricingSigs=new Set(compiledRows.map(x=>pricingSig(x.pricing)));
          pd1BaselineGenericProtected=pricingSigs.size===1;
        }
      }
    }

    // PD1/Powerdot official technical-group identity.
    // Duplicate source physical references are not strong enough to let the
    // technical fallback consume an otherwise unresolved group. Keep them for
    // the later generic exact-set rule, which can publish only when the whole
    // source/target set has identical pricing and exact cardinality.
    const pd1PhysicalRefs=(row.tariff?.evses||[])
      .map(e0=>norm(text(e0?.physicalReference)))
      .filter(Boolean);
    const pd1HasDuplicatePhysicalRefs=new Set(pd1PhysicalRefs).size!==pd1PhysicalRefs.length;
    // Duplicate physical references are allowed only after the baseline generic
    // exact-set protection above has ruled out consuming an already-valid legacy group.
    // Technical groups still require exact source/target cardinality, global target
    // uniqueness and homogeneous compiled pricing.
    if(!pd1BaselineGenericProtected){
      const claimed=new Set();
      const unresolved=[];
      for(const e0 of row.tariff?.evses||[]){
        if(isValidatedResidualSource(row,e0))continue;
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        if(local.has(k0)){claimed.add(k0);continue;}
        const p0=[...local].filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
        if(p0.length===1){claimed.add(p0[0]);continue;}
        if(ordinalTargets.has(e0)){claimed.add(ordinalTargets.get(e0));continue;}
        if(genericTargets.has(e0)){claimed.add(genericTargets.get(e0));continue;}
        if(suffixTargets.has(e0)){claimed.add(suffixTargets.get(e0));continue;}
        if(trimmedSuffixTargets.has(e0)){claimed.add(trimmedSuffixTargets.get(e0));continue;}
        if(pd1FinalOrdinalTargets.has(e0)){claimed.add(pd1FinalOrdinalTargets.get(e0));continue;}
        if(viaFinalOrdinalTargets.has(e0)){claimed.add(viaFinalOrdinalTargets.get(e0));continue;}
        if(c55BIndexTargets.has(e0)){claimed.add(c55BIndexTargets.get(e0));continue;}
        if(izfGroupedSourceEvses.has(e0)||viaGroupedSourceEvses.has(e0)||c55GroupedSourceEvses.has(e0)||hpcGroupedSourceEvses.has(e0)||pd1TechnicalSourceEvses.has(e0))continue;
        const tech=pd1TechKeyFromEvse(e0);if(!tech)continue;
        unresolved.push({e:e0,tech});
      }
      const unclaimedPd1=[...local].filter(p=>!claimed.has(p)&&p.startsWith('FRPD1E'));
      if(unresolved.length&&unclaimedPd1.length){
        const targetsByTech=new Map();let validTargets=true;
        for(const p of unclaimedPd1){
          const native=powerdotByEvse.get(p),tech=native?pd1TechKeyFromNative(native):null;
          if(!tech||(globalPdcOwners.get(p)?.size||0)!==1){validTargets=false;break;}
          const arr=targetsByTech.get(tech)||[];arr.push(p);targetsByTech.set(tech,arr);
        }
        if(validTargets){
          const sourcesByTech=new Map();
          for(const x of unresolved){const arr=sourcesByTech.get(x.tech)||[];arr.push(x.e);sourcesByTech.set(x.tech,arr);}
          for(const [tech,targets] of targetsByTech){
            const es=sourcesByTech.get(tech)||[];
            if(!es.length||es.length!==targets.length)continue;
            const compiledRows=[];let valid=true;
            for(const e0 of es){
              const connectors=e0?.connectors||[];if(!connectors.length){valid=false;break;}
              const compiled=[];
              for(const c0 of connectors){
                const x=compileConnector(c0);if(!x.ok){valid=false;break;}
                compiled.push({pricing:x.pricing,connectorPk:c0.pk??null});
              }
              if(!valid)break;
              const unique=[...new Map(compiled.map(x=>[pricingSig(x.pricing),x.pricing])).values()];
              if(unique.length!==1){valid=false;break;}
              compiledRows.push({e:e0,pricing:unique[0],connectorCount:connectors.length});
            }
            if(!valid||compiledRows.length!==es.length)continue;
            const pricingSigs=new Set(compiledRows.map(x=>pricingSig(x.pricing)));
            if(pricingSigs.size!==1)continue;
            const sharedPricing=compiledRows[0].pricing;
            const sourceConnectorCountTotal=compiledRows.reduce((n,x)=>n+x.connectorCount,0);
            for(const p of targets)pd1TechnicalTargets.set(p,{tech,pricing:sharedPricing,sourceEvses:es,sourceConnectorCountTotal});
            for(const e0 of es)pd1TechnicalSourceEvses.add(e0);
          }
        }
      }
    }
    if(pd1TechnicalTargets.size){
      for(const [targetNorm,g] of pd1TechnicalTargets){
        const targetPdc=localByNorm.get(targetNorm),parsedTech=JSON.parse(g.tech);
        const currency=g.pricing.rules?.[0]?.currency||'EUR';
        const offer={
          id:`electroverse-evse-pd1-tech:${row.electroverseLocationPk}:${targetNorm}`,
          provider:'Electroverse',countries:['FR'],currency,priority:80,
          verifiedScope:'exact_evse_group',evseIds:[targetPdc],pricing:g.pricing,
          metadata:{
            verified:true,identityMode:'strict_pd1_official_technical_homogeneous_group',
            electroverseLocationPk:String(row.electroverseLocationPk),
            electroverseEvsePks:g.sourceEvses.map(e=>e.pk??null),
            physicalReferences:g.sourceEvses.map(e=>text(e?.physicalReference)),
            powerKwClass:parsedTech.kw,plugTypes:parsedTech.plugs,
            connectorCount:null,connectorCountKnown:false,
            sourceConnectorCountTotal:g.sourceConnectorCountTotal,
            sourceGroupSize:g.sourceEvses.length,targetGroupSize:g.sourceEvses.length,
            operator:'PD1',tariffHash:row.tariffHash||null,fetchedAt:row.fetchedAt||null,
            source:'Electroverse tariff cache + Powerdot official technical inventory'
          }
        };
        const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);tiles.get(id).push(offer);
        stats.pd1TechnicalGroupCandidateEvses++;stats.pd1TechnicalGroupPublishedEvses++;
        stats.pd1TechnicalGroupByKey[g.tech]=(stats.pd1TechnicalGroupByKey[g.tech]||0)+1;
        stats.pricedExactEvses++;stats.publishedEvses++;stats.publishedOffers++;
      }
    }

    // DRV native-power group identity. The national Driveco dataset provides a
    // machine-readable powerKw for each PDC. We may therefore group unresolved #xx
    // Electroverse EVSEs and unclaimed national PDCs by exact normalized power class.
    // No individual ordering is inferred within a power group: publication is allowed
    // only when source/target cardinality is identical, every PDC is globally unique,
    // and every source EVSE in the power group compiles to the same tariff.
    const drvPowerTargets=new Map();
    const drvPowerSourceEvses=new Set();
    {
      const claimed=new Set();
      const unresolved=[];
      for(const e0 of row.tariff?.evses||[]){
        if(isValidatedResidualSource(row,e0))continue;
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        if(local.has(k0)){claimed.add(k0);continue;}
        const p0=[...local].filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
        if(p0.length===1){claimed.add(p0[0]);continue;}
        if(ordinalTargets.has(e0)){claimed.add(ordinalTargets.get(e0));continue;}
        if(genericTargets.has(e0)){claimed.add(genericTargets.get(e0));continue;}
        if(suffixTargets.has(e0)){claimed.add(suffixTargets.get(e0));continue;}
        if(trimmedSuffixTargets.has(e0)){claimed.add(trimmedSuffixTargets.get(e0));continue;}
        if(pd1FinalOrdinalTargets.has(e0)){claimed.add(pd1FinalOrdinalTargets.get(e0));continue;}
        if(viaFinalOrdinalTargets.has(e0)){claimed.add(viaFinalOrdinalTargets.get(e0));continue;}
        if(c55BIndexTargets.has(e0)){claimed.add(c55BIndexTargets.get(e0));continue;}
        if(izfGroupedSourceEvses.has(e0)||viaGroupedSourceEvses.has(e0)||c55GroupedSourceEvses.has(e0)||hpcGroupedSourceEvses.has(e0)||pd1TechnicalSourceEvses.has(e0))continue;
        if(!/^#\d{2}$/.test(pr0))continue;
        const connectors=e0?.connectors||[];
        if(!connectors.length)continue;
        const sourceKw=kwClass(Math.max(...connectors.map(c0=>Number(c0.kilowatts)||0)));
        if(sourceKw==null)continue;
        unresolved.push({e:e0,kw:sourceKw});
      }
      const unclaimedDrv=[...local].filter(p=>!claimed.has(p)&&p.startsWith('FRDRVE'));
      if(unresolved.length&&unclaimedDrv.length){
        const targetsByKw=new Map();
        let targetValid=true;
        for(const p of unclaimedDrv){
          const native=drivecoByEvse.get(p);
          const k=native?kwClass(native.powerKw):null;
          if(k==null||(globalPdcOwners.get(p)?.size||0)!==1){targetValid=false;break;}
          const arr=targetsByKw.get(k)||[];arr.push(p);targetsByKw.set(k,arr);
        }
        if(targetValid){
          const sourceByKw=new Map();
          for(const x of unresolved){
            const arr=sourceByKw.get(x.kw)||[];arr.push(x.e);sourceByKw.set(x.kw,arr);
          }
          for(const [k,targets] of targetsByKw){
            const es=sourceByKw.get(k)||[];
            if(!es.length||es.length!==targets.length)continue;
            const compiledRows=[];
            let valid=true;
            for(const e0 of es){
              const connectors=e0?.connectors||[];
              const compiled=[];
              for(const c0 of connectors){
                const x=compileConnector(c0);if(!x.ok){valid=false;break;}
                compiled.push({pricing:x.pricing,connectorPk:c0.pk??null});
              }
              if(!valid||!compiled.length){valid=false;break;}
              const unique=[...new Map(compiled.map(x=>[pricingSig(x.pricing),x.pricing])).values()];
              if(unique.length!==1){valid=false;break;}
              compiledRows.push({e:e0,pricing:unique[0],connectorCount:connectors.length});
            }
            if(!valid||compiledRows.length!==es.length)continue;
            const pricingSigs=new Set(compiledRows.map(x=>pricingSig(x.pricing)));
            if(pricingSigs.size!==1)continue;
            const sharedPricing=compiledRows[0].pricing;
            const sourceConnectorCountTotal=compiledRows.reduce((n,x)=>n+x.connectorCount,0);
            for(const p of targets)drvPowerTargets.set(p,{
              kw:k,pricing:sharedPricing,sourceEvses:es,sourceConnectorCountTotal
            });
            for(const e0 of es)drvPowerSourceEvses.add(e0);
          }
        }
      }
    }

    if(drvPowerTargets.size){
      for(const [targetNorm,g] of drvPowerTargets.entries()){
        const targetPdc=localByNorm.get(targetNorm);
        const currency=g.pricing.rules?.[0]?.currency||'EUR';
        const offer={
          id:`electroverse-evse-drv-power:${row.electroverseLocationPk}:${targetNorm}`,
          provider:'Electroverse',
          countries:['FR'],
          currency,
          priority:80,
          verifiedScope:'exact_evse_group',
          evseIds:[targetPdc],
          pricing:g.pricing,
          metadata:{
            verified:true,
            identityMode:'strict_drv_native_power_homogeneous_group',
            electroverseLocationPk:String(row.electroverseLocationPk),
            electroverseEvsePks:g.sourceEvses.map(e=>e.pk??null),
            physicalReferences:g.sourceEvses.map(e=>text(e?.physicalReference)),
            powerKwClass:g.kw,
            connectorCount:null,
            connectorCountKnown:false,
            sourceConnectorCountTotal:g.sourceConnectorCountTotal,
            sourceGroupSize:g.sourceEvses.length,
            targetGroupSize:g.sourceEvses.length,
            operator:'DRV',
            tariffHash:row.tariffHash||null,
            fetchedAt:row.fetchedAt||null,
            source:'Electroverse tariff cache + Driveco native EVSE power'
          }
        };
        const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);
        tiles.get(id).push(offer);
        stats.drvPowerGroupCandidateEvses++;
        stats.drvPowerGroupPublishedEvses++;
        stats.drvPowerGroupByKw[String(g.kw)]=(stats.drvPowerGroupByKw[String(g.kw)]||0)+1;
        stats.pricedExactEvses++;
        stats.publishedEvses++;stats.publishedOffers++;
      }
    }

    // DRV/SIG/QOV lab: operator-locked homogeneous exact-set fallback.
    // This never assigns an individual source reference to an individual PDC. It is used
    // only when the entire unresolved source set has the same size as the entire unclaimed
    // national PDC set for exactly one operator, all PDCs are globally unique, and all
    // source EVSEs have identical compiled pricing and connector counts.
    const operatorExactSetTargets=new Map();
    const operatorGroupedSourceEvses=new Set();
    const exactSetOps=[
      {code:'DRV',prefix:'FRDRVE',mode:'strict_drv_homogeneous_exact_set',stat:'drvHomogeneousGroup'},
      {code:'SIG',prefix:'FRSIGE',mode:'strict_sig_homogeneous_exact_set',stat:'sigHomogeneousGroup'},
      {code:'QOV',prefix:'FRQOVE',mode:'strict_qov_homogeneous_exact_set',stat:'qovHomogeneousGroup'},
      {code:'B',prefix:'FR55CE',mode:'strict_b_location_homogeneous_exact_set',stat:'bHomogeneousGroup',locationPk:'559069',sourcePred:pr=>/^B0[12]$/i.test(pr)},
      {code:'B',prefix:'FRY55E',mode:'strict_b_location_homogeneous_exact_set',stat:'bHomogeneousGroup',locationPk:'4512230',sourcePred:pr=>/^B$/i.test(pr)}
    ];
    for(const cfg of exactSetOps){
      if(cfg.locationPk && String(row.electroverseLocationPk)!==cfg.locationPk)continue;
      const localListOp=[...local];
      if(!localListOp.some(p=>p.startsWith(cfg.prefix)))continue;
      const alreadyClaimed=new Set();
      const unresolved=[];
      for(const e0 of row.tariff?.evses||[]){
        if(isValidatedResidualSource(row,e0))continue;
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        if(local.has(k0)){alreadyClaimed.add(k0);continue;}
        const p0=localListOp.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
        if(p0.length===1){alreadyClaimed.add(p0[0]);continue;}
        if(ordinalTargets.has(e0)){alreadyClaimed.add(ordinalTargets.get(e0));continue;}
        if(genericTargets.has(e0)){alreadyClaimed.add(genericTargets.get(e0));continue;}
        if(suffixTargets.has(e0)){alreadyClaimed.add(suffixTargets.get(e0));continue;}
        if(trimmedSuffixTargets.has(e0)){alreadyClaimed.add(trimmedSuffixTargets.get(e0));continue;}
        if(pd1FinalOrdinalTargets.has(e0)){alreadyClaimed.add(pd1FinalOrdinalTargets.get(e0));continue;}
        if(viaFinalOrdinalTargets.has(e0)){alreadyClaimed.add(viaFinalOrdinalTargets.get(e0));continue;}
        if(izfGroupedSourceEvses.has(e0)||viaGroupedSourceEvses.has(e0)||c55GroupedSourceEvses.has(e0)||hpcGroupedSourceEvses.has(e0)||pd1TechnicalSourceEvses.has(e0)||drvPowerSourceEvses.has(e0))continue;
        if(cfg.sourcePred && !cfg.sourcePred(pr0))continue;
        unresolved.push(e0);
      }
      const allUnclaimed=localListOp.filter(p=>!alreadyClaimed.has(p));
      const unclaimedOp=allUnclaimed.filter(p=>p.startsWith(cfg.prefix));
      if(!unresolved.length||unresolved.length!==unclaimedOp.length||allUnclaimed.length!==unclaimedOp.length)continue;
      if(!unclaimedOp.every(p=>(globalPdcOwners.get(p)?.size||0)===1))continue;
      const compiledRows=[];
      let valid=true;
      for(const e0 of unresolved){
        const connectors=e0?.connectors||[];
        if(!connectors.length){valid=false;break;}
        const compiled=[];
        for(const c0 of connectors){
          const x=compileConnector(c0);if(!x.ok){valid=false;break;}
          compiled.push({pricing:x.pricing,connectorPk:c0.pk??null});
        }
        if(!valid)break;
        const unique=[...new Map(compiled.map(x=>[pricingSig(x.pricing),x.pricing])).values()];
        if(unique.length!==1){valid=false;break;}
        compiledRows.push({e:e0,pricing:unique[0],connectorCount:connectors.length});
      }
      if(!valid||compiledRows.length!==unresolved.length)continue;
      const pricingSigs=new Set(compiledRows.map(x=>pricingSig(x.pricing)));
      const connectorCounts=new Set(compiledRows.map(x=>x.connectorCount));
      if(pricingSigs.size!==1||connectorCounts.size!==1)continue;
      const sharedPricing=compiledRows[0].pricing;
      const connectorCount=compiledRows[0].connectorCount;
      for(const p of unclaimedOp){
        operatorExactSetTargets.set(p,{cfg,pricing:sharedPricing,connectorCount,sourceEvses:unresolved});
      }
      for(const e0 of unresolved)operatorGroupedSourceEvses.add(e0);
    }

    if(operatorExactSetTargets.size){
      for(const [targetNorm,g] of operatorExactSetTargets.entries()){
        const targetPdc=localByNorm.get(targetNorm);
        const sourceEvses=g.sourceEvses;
        const currency=g.pricing.rules?.[0]?.currency||'EUR';
        const offer={
          id:`electroverse-evse-${g.cfg.code.toLowerCase()}-group:${row.electroverseLocationPk}:${targetNorm}`,
          provider:'Electroverse',
          countries:['FR'],
          currency,
          priority:80,
          verifiedScope:'exact_evse_group',
          evseIds:[targetPdc],
          pricing:g.pricing,
          metadata:{
            verified:true,
            identityMode:g.cfg.mode,
            electroverseLocationPk:String(row.electroverseLocationPk),
            electroverseEvsePks:sourceEvses.map(e=>e.pk??null),
            physicalReferences:sourceEvses.map(e=>text(e?.physicalReference)),
            connectorCount:g.connectorCount,
            sourceGroupSize:sourceEvses.length,
            targetGroupSize:sourceEvses.length,
            operator:g.cfg.code,
            tariffHash:row.tariffHash||null,
            fetchedAt:row.fetchedAt||null,
            source:'Electroverse tariff cache'
          }
        };
        const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);
        tiles.get(id).push(offer);
        stats[g.cfg.stat+'CandidateEvses']++;
        stats[g.cfg.stat+'PublishedEvses']++;
        stats.pricedExactEvses++;
        stats.publishedEvses++;stats.publishedOffers++;stats.publishedConnectorCount+=g.connectorCount;
      }
    }

    // CUSTOMGYEVSE validated pair groups. Each source pair has identical technical
    // profile and pricing. The pair maps to the two GYM EC1/EC2 PDCs sharing one tail,
    // without inventing which source EVSE is branch 1 vs branch 2.
    const customGyPairGroupedSourceEvses=new Set();
    const customGyPairTargets=new Map();
    for(const g of customGyPairGroupsByLocation.get(String(row.electroverseLocationPk))||[]){
      const sourcePkSet=new Set((g.sourceEvsePks||[]).map(String));
      const es=(row.tariff?.evses||[]).filter(e0=>sourcePkSet.has(String(e0?.pk??'')));
      const targets=(g.targetPdcs||[]).map(norm).filter(Boolean);
      if(es.length!==2||sourcePkSet.size!==2||targets.length!==2||new Set(targets).size!==2)continue;
      if(targets.some(p=>!local.has(p)||(globalPdcOwners.get(p)?.size||0)!==1))continue;
      const compiledRows=[];let valid=true;
      for(const e0 of es){
        const connectors=e0?.connectors||[];if(!connectors.length){valid=false;break;}
        const compiled=[];
        for(const c0 of connectors){
          const x=compileConnector(c0);if(!x.ok){valid=false;break;}
          compiled.push({pricing:x.pricing,connectorPk:c0.pk??null});
        }
        if(!valid)break;
        const unique=[...new Map(compiled.map(x=>[pricingSig(x.pricing),x.pricing])).values()];
        if(unique.length!==1){valid=false;break;}
        compiledRows.push({e:e0,pricing:unique[0],connectorCount:connectors.length,tech:JSON.stringify(connectors.map(c0=>({kilowatts:c0?.kilowatts??null,standard:c0?.standard?.name??c0?.standard??null})).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b))))});
      }
      if(!valid||compiledRows.length!==2)continue;
      if(new Set(compiledRows.map(x=>pricingSig(x.pricing))).size!==1)continue;
      if(new Set(compiledRows.map(x=>x.connectorCount)).size!==1)continue;
      if(new Set(compiledRows.map(x=>x.tech)).size!==1)continue;
      const expectedKw=Number(g?.profile?.kilowatts);
      const expectedStd=String(g?.profile?.standard??'');
      if(Number.isFinite(expectedKw)||expectedStd){
        const cs=es.flatMap(e0=>e0?.connectors||[]);
        if(Number.isFinite(expectedKw)&&cs.some(c0=>Math.abs(Number(c0?.kilowatts)-expectedKw)>0.5))continue;
        if(expectedStd&&cs.some(c0=>String(c0?.standard?.name??c0?.standard??'')!==expectedStd))continue;
      }
      const sharedPricing=compiledRows[0].pricing,connectorCount=compiledRows[0].connectorCount;
      for(const t of targets)customGyPairTargets.set(t,{pricing:sharedPricing,connectorCount,sourceEvses:es,stationId:g.irveStationId??null});
      for(const e0 of es)customGyPairGroupedSourceEvses.add(e0);
    }
    if(customGyPairTargets.size){
      for(const [targetNorm,g] of customGyPairTargets){
        const targetPdc=localByNorm.get(targetNorm);
        const currency=g.pricing.rules?.[0]?.currency||'EUR';
        const offer={
          id:`electroverse-evse-customgy-pair:${row.electroverseLocationPk}:${targetNorm}`,
          provider:'Electroverse',countries:['FR'],currency,priority:80,
          verifiedScope:'exact_evse_group',evseIds:[targetPdc],pricing:g.pricing,
          metadata:{
            verified:true,identityMode:'validated_customgyevse_pair_group',
            electroverseLocationPk:String(row.electroverseLocationPk),
            electroverseEvsePks:g.sourceEvses.map(e=>e.pk??null),
            physicalReferences:g.sourceEvses.map(e=>text(e?.physicalReference)),
            connectorCount:g.connectorCount,sourceGroupSize:2,targetGroupSize:2,
            operator:'GYM',irveStationId:g.stationId,
            tariffHash:row.tariffHash||null,fetchedAt:row.fetchedAt||null,
            source:'Electroverse validated CUSTOMGYEVSE pair ledger'
          }
        };
        const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);tiles.get(id).push(offer);
        stats.customGyPairCandidateEvses=(stats.customGyPairCandidateEvses||0)+1;
        stats.customGyPairPublishedEvses=(stats.customGyPairPublishedEvses||0)+1;
        stats.pricedExactEvses++;stats.publishedEvses++;stats.publishedOffers++;stats.publishedConnectorCount+=g.connectorCount;
      }
    }

    // Final residual recovery plan: exact homogeneous groups proven against the
    // current canonical overlay. Revalidate every source and target at build time.
    const finalResidualGroupedSourceEvses=new Set();
    const finalResidualGroupTargets=new Map();
    for(const g of finalResidualGroupsByLocation.get(String(row.electroverseLocationPk))||[]){
      const recoveryMode=String(g.mode||'');
      if(!['homogeneous_exact_set','homogeneous_target_subset'].includes(recoveryMode))continue;
      const sourcePkSet=new Set((g.sourceEvsePks||[]).map(String));
      const es=(row.tariff?.evses||[]).filter(e0=>sourcePkSet.has(String(e0?.pk??'')));
      const targets=(g.targetPdcs||[]).map(norm).filter(Boolean);
      if(!es.length||es.length!==sourcePkSet.size||!targets.length)continue;
      if(recoveryMode==='homogeneous_exact_set' && targets.length!==es.length)continue;
      if(recoveryMode==='homogeneous_target_subset' && es.length<targets.length)continue;
      if(new Set(targets).size!==targets.length)continue;
      if(targets.some(p=>!local.has(p)||(globalPdcOwners.get(p)?.size||0)!==1))continue;

      // Refuse the planned group if any source is now already resolved by a stronger rule.
      let sourceConflict=false;
      for(const e0 of es){
        const pr0=text(e0?.physicalReference);const k0=norm(pr0);
        const parentNow=[...local].filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
        if(local.has(k0)||parentNow.length===1||ordinalTargets.has(e0)||genericTargets.has(e0)||suffixTargets.has(e0)||
           trimmedSuffixTargets.has(e0)||pd1FinalOrdinalTargets.has(e0)||viaFinalOrdinalTargets.has(e0)||
           c55BIndexTargets.has(e0)||viaStructuredBasePairTargets.has(e0)||viaOfficialTargets.has(e0)||
           izfGroupedSourceEvses.has(e0)||viaGroupedSourceEvses.has(e0)||c55GroupedSourceEvses.has(e0)||
           hpcGroupedSourceEvses.has(e0)||pd1TechnicalSourceEvses.has(e0)||drvPowerSourceEvses.has(e0)||
           operatorGroupedSourceEvses.has(e0)){sourceConflict=true;break;}
      }
      if(sourceConflict)continue;

      const compiledRows=[];let valid=true;
      for(const e0 of es){
        const connectors=e0?.connectors||[];if(!connectors.length){valid=false;break;}
        const compiled=[];
        for(const c0 of connectors){
          const x=compileConnector(c0);if(!x.ok){valid=false;break;}
          compiled.push({pricing:x.pricing,connectorPk:c0.pk??null});
        }
        if(!valid)break;
        const unique=[...new Map(compiled.map(x=>[pricingSig(x.pricing),x.pricing])).values()];
        if(unique.length!==1){valid=false;break;}
        compiledRows.push({e:e0,pricing:unique[0],connectorCount:connectors.length});
      }
      if(!valid||compiledRows.length!==es.length)continue;
      const pricingSigs=new Set(compiledRows.map(x=>pricingSig(x.pricing)));
      const connectorCounts=new Set(compiledRows.map(x=>x.connectorCount));
      const technicalProfiles=new Set(es.map(e0=>JSON.stringify((e0?.connectors||[]).map(c0=>({
        kilowatts:c0?.kilowatts??null,
        standard:c0?.standard?.name??c0?.standard??null
      })).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b))))));
      const allUnresolvedAtLocation=(row.tariff?.evses||[]).filter(e0=>{
        const key=String(row.electroverseLocationPk)+':'+String(e0?.pk??'');
        if(validatedResidualTargets.has(key))return false;
        const pr0=text(e0?.physicalReference);const k0=norm(pr0);
        const parentNow=[...local].filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\\d{1,2}$/.test(k0.slice(p.length)));
        if(local.has(k0)||parentNow.length===1||ordinalTargets.has(e0)||genericTargets.has(e0)||suffixTargets.has(e0)||
           trimmedSuffixTargets.has(e0)||pd1FinalOrdinalTargets.has(e0)||viaFinalOrdinalTargets.has(e0)||
           c55BIndexTargets.has(e0)||viaStructuredBasePairTargets.has(e0)||viaOfficialTargets.has(e0)||
           izfGroupedSourceEvses.has(e0)||viaGroupedSourceEvses.has(e0)||c55GroupedSourceEvses.has(e0)||
           hpcGroupedSourceEvses.has(e0)||pd1TechnicalSourceEvses.has(e0)||drvPowerSourceEvses.has(e0)||
           operatorGroupedSourceEvses.has(e0)||customGyPairGroupedSourceEvses.has(e0))return false;
        return true;
      });
      if(pricingSigs.size!==1||connectorCounts.size!==1||technicalProfiles.size!==1)continue;
      if(recoveryMode==='homogeneous_exact_set' && allUnresolvedAtLocation.length>es.length)continue;
      const expectedProfile=g.profile&&typeof g.profile==='object'?g.profile:null;
      if(expectedProfile){
        const actual=(es[0]?.connectors||[]).map(c0=>({
          kilowatts:c0?.kilowatts??null,
          standard:c0?.standard?.name??c0?.standard??null
        }));
        if(expectedProfile.kilowatts!=null && !actual.every(x=>Number(x.kilowatts)===Number(expectedProfile.kilowatts)))continue;
        if(expectedProfile.standard!=null && !actual.every(x=>String(x.standard||'')===String(expectedProfile.standard)))continue;
      }

      const sharedPricing=compiledRows[0].pricing;
      const connectorCount=compiledRows[0].connectorCount;
      for(const p of targets)finalResidualGroupTargets.set(p,{
        pricing:sharedPricing,connectorCount,sourceEvses:es,operator:String(g.operator||'UNKNOWN'),
        recoveryMode,targetGroupSize:targets.length
      });
      for(const e0 of es)finalResidualGroupedSourceEvses.add(e0);
    }

    if(finalResidualGroupTargets.size){
      for(const [targetNorm,g] of finalResidualGroupTargets){
        const targetPdc=localByNorm.get(targetNorm);
        const currency=g.pricing.rules?.[0]?.currency||'EUR';
        const offer={
          id:`electroverse-evse-final-residual-group:${row.electroverseLocationPk}:${targetNorm}`,
          provider:'Electroverse',countries:['FR'],currency,priority:80,
          verifiedScope:'exact_evse_group',evseIds:[targetPdc],pricing:g.pricing,
          metadata:{
            verified:true,identityMode:g.recoveryMode==='homogeneous_target_subset'
              ?'validated_final_residual_homogeneous_target_subset'
              :'validated_final_residual_homogeneous_exact_set',
            electroverseLocationPk:String(row.electroverseLocationPk),
            electroverseEvsePks:g.sourceEvses.map(e=>e.pk??null),
            physicalReferences:g.sourceEvses.map(e=>text(e?.physicalReference)),
            connectorCount:g.connectorCount,sourceGroupSize:g.sourceEvses.length,targetGroupSize:g.targetGroupSize,
            operator:g.operator,
            ...(g.operator==='B_FR55C_7KW_POWER_VARIANT'?{
              offerGranularity:'connector_power_alias',
              sourcePowerKw:7,
              sourceStandard:'IEC_62196_T2'
            }:{}),
            tariffHash:row.tariffHash||null,fetchedAt:row.fetchedAt||null,
            source:'Electroverse final residual recovery plan'
          }
        };
        const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);tiles.get(id).push(offer);
        stats.finalResidualHomogeneousGroupCandidateEvses++;
        stats.finalResidualHomogeneousGroupPublishedEvses++;
        stats.pricedExactEvses++;stats.publishedEvses++;stats.publishedOffers++;stats.publishedConnectorCount+=g.connectorCount;
      }
    }

    // Generic homogeneous exact-set fallback for all remaining single-operator families.
    // This is intentionally later than every operator-specific rule. It only applies to the
    // still-unresolved source set when ALL remaining national PDCs at the mapped location:
    // 1) belong to one recognized operator family, 2) have identical cardinality to source,
    // 3) are globally unique, and 4) all source EVSEs have identical pricing and connector count.
    const genericExactSetTargets=new Map();
    const stationBroadcastTargets=new Map();
    const genericGroupedSourceEvses=new Set();
    {
      const claimed=new Set();
      const unresolved=[];
      for(const e0 of row.tariff?.evses||[]){
        if(isValidatedResidualSource(row,e0))continue;
        const pr0=text(e0?.physicalReference);if(!pr0)continue;
        const k0=norm(pr0);
        const validatedNumericTarget=validatedResidualTargets.get(String(row.electroverseLocationPk)+':'+String(e0?.pk??''));
        if(validatedNumericTarget){
          const targetNorm=norm(validatedNumericTarget);
          if(local.has(targetNorm)&&(globalPdcOwners.get(targetNorm)?.size||0)===1)claimed.add(targetNorm);
          continue;
        }
        if(local.has(k0)){claimed.add(k0);continue;}
        const p0=[...local].filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
        if(p0.length===1){claimed.add(p0[0]);continue;}
        if(ordinalTargets.has(e0)){claimed.add(ordinalTargets.get(e0));continue;}
        if(genericTargets.has(e0)){claimed.add(genericTargets.get(e0));continue;}
        if(suffixTargets.has(e0)){claimed.add(suffixTargets.get(e0));continue;}
        if(trimmedSuffixTargets.has(e0)){claimed.add(trimmedSuffixTargets.get(e0));continue;}
        if(pd1FinalOrdinalTargets.has(e0)){claimed.add(pd1FinalOrdinalTargets.get(e0));continue;}
        if(viaFinalOrdinalTargets.has(e0)){claimed.add(viaFinalOrdinalTargets.get(e0));continue;}
        if(izfGroupedSourceEvses.has(e0)||viaGroupedSourceEvses.has(e0)||c55GroupedSourceEvses.has(e0)||hpcGroupedSourceEvses.has(e0)||pd1TechnicalSourceEvses.has(e0)||drvPowerSourceEvses.has(e0)||operatorGroupedSourceEvses.has(e0)||customGyPairGroupedSourceEvses.has(e0)||finalResidualGroupedSourceEvses.has(e0))continue;
        unresolved.push(e0);
      }
      const unclaimed=[...local].filter(p=>!claimed.has(p));
      const opCode=p=>{
        const m=String(p||'').match(/^FR([A-Z0-9]{1,6})E/);
        return m?m[1]:null;
      };
      const opSet=new Set(unclaimed.map(opCode).filter(Boolean));
      const recognizedSingleOperator=unclaimed.length>0 && opSet.size===1 && unclaimed.every(p=>opCode(p));

      // Audit only: evaluate a broader station-homogeneous price broadcast without publishing it.
      // This ignores source/target cardinality but still requires a single national operator family,
      // globally unique unclaimed PDCs, compilable pricing on every residual source, and exactly one
      // compiled pricing signature across the whole unresolved source set.
      if(recognizedSingleOperator && unresolved.length>0 &&
         unclaimed.every(p=>(globalPdcOwners.get(p)?.size||0)===1)){
        const auditCompiled=[];
        let auditValid=true;
        for(const e0 of unresolved){
          const connectors=e0?.connectors||[];
          if(!connectors.length){auditValid=false;break;}
          const compiled=[];
          for(const c0 of connectors){
            const x=compileConnector(c0);if(!x.ok){auditValid=false;break;}
            compiled.push(x.pricing);
          }
          if(!auditValid)break;
          const unique=[...new Map(compiled.map(p=>[pricingSig(p),p])).values()];
          if(unique.length!==1){auditValid=false;break;}
          auditCompiled.push(unique[0]);
        }
        if(auditValid&&auditCompiled.length===unresolved.length&&
           new Set(auditCompiled.map(pricingSig)).size===1){
          const operator=[...opSet][0];
          stats.stationHomogeneousBroadcastAuditLocations++;
          stats.stationHomogeneousBroadcastAuditTargets+=unclaimed.length;
          stats.stationHomogeneousBroadcastAuditSources+=unresolved.length;
          const a=stats.stationHomogeneousBroadcastAuditByOperator[operator]||{locations:0,targets:0,sources:0};
          a.locations++;a.targets+=unclaimed.length;a.sources+=unresolved.length;
          stats.stationHomogeneousBroadcastAuditByOperator[operator]=a;
          if(unresolved.length!==unclaimed.length){
            stats.stationHomogeneousBroadcastMismatchLocations++;
            stats.stationHomogeneousBroadcastMismatchTargets+=unclaimed.length;
            stats.stationHomogeneousBroadcastMismatchSources+=unresolved.length;
            const b=stats.stationHomogeneousBroadcastMismatchByOperator[operator]||{locations:0,targets:0,sources:0};
            b.locations++;b.targets+=unclaimed.length;b.sources+=unresolved.length;
            stats.stationHomogeneousBroadcastMismatchByOperator[operator]=b;

            // Strong form: every tariff-bearing Electroverse EVSE at this mapped location
            // must compile successfully to one EVSE-level price, and all such prices must match.
            const allStationPricings=[];
            let stationPriceValid=true;
            for(const eAll of row.tariff?.evses||[]){
              const cs=eAll?.connectors||[];
              if(!cs.length)continue;
              const ps=[];
              for(const cAll of cs){
                const xAll=compileConnector(cAll);if(!xAll.ok){stationPriceValid=false;break;}
                ps.push(xAll.pricing);
              }
              if(!stationPriceValid)break;
              const uniq=[...new Map(ps.map(p=>[pricingSig(p),p])).values()];
              if(uniq.length!==1){stationPriceValid=false;break;}
              allStationPricings.push(uniq[0]);
            }
            if(stationPriceValid&&allStationPricings.length&&
               new Set(allStationPricings.map(pricingSig)).size===1){
              stats.stationHomogeneousBroadcastStrictMismatchLocations++;
              stats.stationHomogeneousBroadcastStrictMismatchTargets+=unclaimed.length;
              stats.stationHomogeneousBroadcastStrictMismatchSources+=unresolved.length;
              const q=stats.stationHomogeneousBroadcastStrictMismatchByOperator[operator]||{locations:0,targets:0,sources:0};
              q.locations++;q.targets+=unclaimed.length;q.sources+=unresolved.length;
              stats.stationHomogeneousBroadcastStrictMismatchByOperator[operator]=q;

              // Publishable station-homogeneous price broadcast. Identity remains at the
              // mapped national station level: no source EVSE is paired to a specific PDC.
              // We only carry the one proven station-wide tariff to each still-unclaimed PDC.
              const sharedPricing=allStationPricings[0];
              for(const p of unclaimed)stationBroadcastTargets.set(p,{
                operator,pricing:sharedPricing,sourceEvses:unresolved,
                sourceTargetCardinalityMismatch:true
              });
              for(const e0 of unresolved)genericGroupedSourceEvses.add(e0);
            }
          }
        }
      }

      if(recognizedSingleOperator && unresolved.length===unclaimed.length &&
         unclaimed.every(p=>(globalPdcOwners.get(p)?.size||0)===1)){
        const compiledRows=[];
        let valid=true;
        for(const e0 of unresolved){
          const connectors=e0?.connectors||[];
          if(!connectors.length){valid=false;break;}
          const compiled=[];
          for(const c0 of connectors){
            const x=compileConnector(c0);if(!x.ok){valid=false;break;}
            compiled.push({pricing:x.pricing,connectorPk:c0.pk??null});
          }
          if(!valid)break;
          const unique=[...new Map(compiled.map(x=>[pricingSig(x.pricing),x.pricing])).values()];
          if(unique.length!==1){valid=false;break;}
          compiledRows.push({e:e0,pricing:unique[0],connectorCount:connectors.length});
        }
        if(valid&&compiledRows.length===unresolved.length&&compiledRows.length){
          const pricingSigs=new Set(compiledRows.map(x=>pricingSig(x.pricing)));
          const connectorCounts=new Set(compiledRows.map(x=>x.connectorCount));
          if(pricingSigs.size===1){
            const operator=[...opSet][0];
            const sharedPricing=compiledRows[0].pricing;
            const exactConnectorCount=connectorCounts.size===1?compiledRows[0].connectorCount:null;
            const sourceConnectorCountTotal=compiledRows.reduce((n,x)=>n+x.connectorCount,0);
            for(const p of unclaimed)genericExactSetTargets.set(p,{
              operator,pricing:sharedPricing,connectorCount:exactConnectorCount,
              connectorCountKnown:connectorCounts.size===1,
              sourceConnectorCountTotal,
              sourceEvses:unresolved
            });
            for(const e0 of unresolved)genericGroupedSourceEvses.add(e0);
          }
        }
      }
    }

    if(stationBroadcastTargets.size){
      const publishedLocations=new Set();
      const coveredSources=new Set();
      const byOp=new Map();
      for(const [targetNorm,g] of stationBroadcastTargets.entries()){
        const targetPdc=localByNorm.get(targetNorm);
        if(!targetPdc)continue;
        const currency=g.pricing.rules?.[0]?.currency||'EUR';
        const offer={
          id:`electroverse-evse-station-price-broadcast:${row.electroverseLocationPk}:${targetNorm}`,
          provider:'Electroverse',
          countries:['FR'],
          currency,
          priority:80,
          verifiedScope:'exact_evse_station_homogeneous_tariff',
          evseIds:[targetPdc],
          pricing:g.pricing,
          metadata:{
            verified:true,
            identityMode:'strict_station_homogeneous_price_broadcast',
            offerGranularity:'evse_price_only',
            electroverseLocationPk:String(row.electroverseLocationPk),
            electroverseEvsePks:g.sourceEvses.map(e=>e.pk??null),
            physicalReferences:g.sourceEvses.map(e=>text(e?.physicalReference)),
            connectorCount:null,
            connectorCountKnown:false,
            sourceTargetCardinalityMismatch:true,
            sourceGroupSize:g.sourceEvses.length,
            targetGroupSize:stationBroadcastTargets.size,
            operator:g.operator,
            tariffHash:row.tariffHash||null,
            fetchedAt:row.fetchedAt||null,
            source:'Electroverse tariff cache; full-station homogeneous compiled tariff'
          }
        };
        const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);
        tiles.get(id).push(offer);
        publishedLocations.add(String(row.electroverseLocationPk));
        for(const e0 of g.sourceEvses)if(e0?.pk!=null)coveredSources.add(String(e0.pk));
        const o=byOp.get(g.operator)||{targets:0,sources:new Set()};
        o.targets++;for(const e0 of g.sourceEvses)if(e0?.pk!=null)o.sources.add(String(e0.pk));byOp.set(g.operator,o);
        stats.pricedExactEvses++;stats.publishedEvses++;stats.publishedOffers++;
      }
      stats.stationHomogeneousBroadcastPublishedLocations+=publishedLocations.size;
      stats.stationHomogeneousBroadcastPublishedTargets+=stationBroadcastTargets.size;
      stats.stationHomogeneousBroadcastCoveredSources+=coveredSources.size;
      for(const [op,v] of byOp){
        const q=stats.stationHomogeneousBroadcastPublishedByOperator[op]||{targets:0,sources:0};
        q.targets+=v.targets;q.sources+=v.sources.size;
        stats.stationHomogeneousBroadcastPublishedByOperator[op]=q;
      }
    }

    if(genericExactSetTargets.size){
      for(const [targetNorm,g] of genericExactSetTargets.entries()){
        const targetPdc=localByNorm.get(targetNorm);
        const currency=g.pricing.rules?.[0]?.currency||'EUR';
        const offer={
          id:`electroverse-evse-generic-group:${row.electroverseLocationPk}:${targetNorm}`,
          provider:'Electroverse',
          countries:['FR'],
          currency,
          priority:80,
          verifiedScope:'exact_evse_group',
          evseIds:[targetPdc],
          pricing:g.pricing,
          metadata:{
            verified:true,
            identityMode:g.connectorCountKnown?'strict_generic_single_operator_homogeneous_exact_set':'strict_generic_single_operator_price_only_exact_set',
            electroverseLocationPk:String(row.electroverseLocationPk),
            electroverseEvsePks:g.sourceEvses.map(e=>e.pk??null),
            physicalReferences:g.sourceEvses.map(e=>text(e?.physicalReference)),
            connectorCount:g.connectorCount,
            connectorCountKnown:g.connectorCountKnown,
            sourceConnectorCountTotal:g.sourceConnectorCountTotal,
            sourceGroupSize:g.sourceEvses.length,
            targetGroupSize:g.sourceEvses.length,
            operator:g.operator,
            tariffHash:row.tariffHash||null,
            fetchedAt:row.fetchedAt||null,
            source:'Electroverse tariff cache'
          }
        };
        const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);
        tiles.get(id).push(offer);
        if(g.connectorCountKnown){
          stats.genericHomogeneousGroupCandidateEvses++;
          stats.genericHomogeneousGroupPublishedEvses++;
          stats.genericHomogeneousGroupByOperator[g.operator]=(stats.genericHomogeneousGroupByOperator[g.operator]||0)+1;
        }else{
          stats.genericPriceOnlyGroupCandidateEvses++;
          stats.genericPriceOnlyGroupPublishedEvses++;
          stats.genericPriceOnlyGroupByOperator[g.operator]=(stats.genericPriceOnlyGroupByOperator[g.operator]||0)+1;
        }
        stats.pricedExactEvses++;
        stats.publishedEvses++;stats.publishedOffers++;
        if(g.connectorCountKnown)stats.publishedConnectorCount+=g.connectorCount;
      }
    }

    for(const e of row.tariff?.evses||[]){
      stats.cacheEvses++;
      const validatedResidualTargetPre=validatedResidualTargets.get(String(row.electroverseLocationPk)+':'+String(e?.pk??''));
      if(!validatedResidualTargetPre && (izfGroupedSourceEvses.has(e)||viaGroupedSourceEvses.has(e)||c55GroupedSourceEvses.has(e)||hpcGroupedSourceEvses.has(e)||s30StructuredSourceEvses.has(e)||pd1TechnicalSourceEvses.has(e)||drvPowerSourceEvses.has(e)||operatorGroupedSourceEvses.has(e)||customGyPairGroupedSourceEvses.has(e)||genericGroupedSourceEvses.has(e)))continue;
      const pr=text(e?.physicalReference);
      if(!pr){rej('evse_missing_physical_reference');continue;}
      stats.physicalRefs++;
      const k=norm(pr);
      let targetPdc=pr,identityMode='exact_unique_national_irve_pdc',parentMode=false,parentNorm='',ordinalMode=false;
      const validatedResidualTarget=validatedResidualTargets.get(String(row.electroverseLocationPk)+':'+String(e?.pk??''));
      if(validatedResidualTarget){
        const targetNorm=norm(validatedResidualTarget);
        const owners=globalPdcOwners.get(targetNorm);
        if(!local.has(targetNorm)||!owners||owners.size!==1){rej('validated_numeric_residual_target_invalid');continue;}
        targetPdc=localByNorm.get(targetNorm);
        const validatedKey=String(row.electroverseLocationPk)+':'+String(e?.pk??'');
        const finalResidualIndividual=finalResidualIndividualTargets.get(validatedKey);
        if(finalResidualIndividual){
          if(finalResidualIndividual.mode==='unique_suffix_bijection'){
            identityMode='validated_final_residual_unique_suffix_bijection';
            stats.finalResidualUniqueSuffixCandidateEvses++;
          }else{
            identityMode='validated_final_residual_common_tail_bijection';
            stats.finalResidualCommonTailCandidateEvses++;
          }
        }else if(validatedS82ResidualTargets.has(validatedKey)){
          identityMode='validated_s82_residual_unique_suffix_bijection';
          stats.validatedS82ResidualCandidateEvses++;
        }else if(validatedMgpResidualTargets.has(validatedKey)){
          identityMode='validated_mgp_residual_unique_suffix_bijection';
          stats.validatedMgpResidualCandidateEvses++;
        }else if(validatedLe2ResidualTargets.has(validatedKey)){
          identityMode='validated_le2_residual_unique_suffix_bijection';
          stats.validatedLe2ResidualCandidateEvses++;
        }else if(validatedBResidualTargets.has(validatedKey)){
          identityMode='validated_55c_bindex_duplicate_safe';
          stats.validatedBResidualCandidateEvses=(stats.validatedBResidualCandidateEvses||0)+1;
        }else if(validatedSaeResidualTargets.has(validatedKey)){
          identityMode='validated_sae_structured_parent';
          parentMode=true;
          parentNorm=targetNorm;
          stats.validatedSaeResidualCandidateEvses=(stats.validatedSaeResidualCandidateEvses||0)+1;
        }else if(validatedH01ResidualTargets.has(validatedKey)){
          identityMode='validated_h01_structured_parent';
          parentMode=true;
          parentNorm=targetNorm;
          stats.validatedH01ResidualCandidateEvses=(stats.validatedH01ResidualCandidateEvses||0)+1;
        }else if(validatedAdpResidualTargets.has(validatedKey)){
          identityMode='validated_adp_structured_parent';
          parentMode=true;
          parentNorm=targetNorm;
          stats.validatedAdpResidualCandidateEvses=(stats.validatedAdpResidualCandidateEvses||0)+1;
        }else if(validatedGenericSmallTargets.has(validatedKey)){
          identityMode='validated_generic_small_bucket';
          stats.validatedGenericSmallCandidateEvses=(stats.validatedGenericSmallCandidateEvses||0)+1;
        }else if(validatedP01ResidualTargets.has(validatedKey)){
          const p01Meta0=validatedP01ResidualMetadata.get(validatedKey);
          identityMode=p01Meta0?.recoveryMode==='station_point_ordinal_remap'
            ? 'validated_p01_station_point_ordinal_remap'
            : p01Meta0?.recoveryMode==='same_parent_homogeneous_price_only'
              ? 'validated_p01_same_parent_homogeneous_price_only'
              : 'validated_p01_structured_parent_identity';
          parentMode=true;
          parentNorm=targetNorm;
          stats.validatedP01ResidualCandidateEvses++;
          if(p01Meta0?.recoveryMode==='same_parent_homogeneous_price_only')stats.validatedP01PriceOnlyCandidateEvses++;
        }else{
          identityMode='validated_numeric_residual_unique_bijection';
          stats.validatedNumericResidualCandidateEvses++;
        }
      }else if(local.has(k)){
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
        }else if(trimmedSuffixTargets.has(e)){
          const targetNorm=trimmedSuffixTargets.get(e);
          const owners=globalPdcOwners.get(targetNorm);
          if(!owners||owners.size!==1){rej('trimmed_suffix_pdc_not_globally_unique');continue;}
          targetPdc=localByNorm.get(targetNorm);
          identityMode='strict_trimmed_long_suffix_identity';
          stats.trimmedSuffixCandidateRefs++;
        }else if(pd1FinalOrdinalTargets.has(e)){
          const targetNorm=pd1FinalOrdinalTargets.get(e);
          const owners=globalPdcOwners.get(targetNorm);
          if(!owners||owners.size!==1){rej('pd1_final_ordinal_pdc_not_globally_unique');continue;}
          targetPdc=localByNorm.get(targetNorm);
          identityMode='strict_pd1_final_ordinal_subgroup_bijection';
          stats.pd1FinalOrdinalCandidateRefs++;
        }else if(viaFinalOrdinalTargets.has(e)){
          const targetNorm=viaFinalOrdinalTargets.get(e);
          const owners=globalPdcOwners.get(targetNorm);
          if(!owners||owners.size!==1){rej('via_final_ordinal_pdc_not_globally_unique');continue;}
          targetPdc=localByNorm.get(targetNorm);
          identityMode='strict_via_final_ordinal_subgroup_bijection';
          stats.viaFinalOrdinalCandidateRefs++;
        }else if(c55BIndexTargets.has(e)){
          const targetNorm=c55BIndexTargets.get(e);
          const owners=globalPdcOwners.get(targetNorm);
          if(!owners||owners.size!==1){rej('c55_bindex_pdc_not_globally_unique');continue;}
          targetPdc=localByNorm.get(targetNorm);
          identityMode='strict_55c_bindex_zero_based_suffix';
          stats.c55BIndexCandidateEvses++;
        }else if(viaStructuredBasePairTargets.has(e)){
          const targetNorm=viaStructuredBasePairTargets.get(e);
          const owners=globalPdcOwners.get(targetNorm);
          if(!owners||owners.size!==1){rej('via_structured_base_pair_pdc_not_globally_unique');continue;}
          targetPdc=localByNorm.get(targetNorm);
          identityMode='strict_via_structured_base_pair';
          stats.viaStructuredBasePairCandidateEvses++;
        }else if(viaOfficialTargets.has(e)){
          const targetNorm=viaOfficialTargets.get(e);
          const owners=globalPdcOwners.get(targetNorm);
          if(!owners||owners.size!==1){rej('vianeo_official_pdc_not_globally_unique');continue;}
          targetPdc=localByNorm.get(targetNorm);
          identityMode='strict_vianeo_official_source_ref_identity';
          stats.viaOfficialIdentityCandidateEvses++;
        }else{
          rej(candidates.length?'parent_pdc_ambiguous':'physical_reference_not_in_local_national_pdcs');continue;
        }
      }

      const p01Meta=validatedP01ResidualMetadata.get(String(row.electroverseLocationPk)+':'+String(e?.pk??''));
      const donorEvse=p01Meta?.donorElectroverseEvsePk!=null?p01DonorEvseByPk.get(String(p01Meta.donorElectroverseEvsePk)):null;
      const pricingEvse=(p01Meta&&donorEvse)?donorEvse:e;
      const connectors=pricingEvse?.connectors||[];
      if(!connectors.length){rej(p01Meta?'validated_p01_donor_missing_connectors':'evse_no_connectors');continue;}
      const compiled=[];
      let bad=null;
      for(const c of connectors){
        const x=compileConnector(c);
        if(!x.ok){bad=x.reason;break;}
        compiled.push({pricing:x.pricing,connectorPk:c.pk??null,powerKw:c.kilowatts??null,standard:c.standard??null});
      }
      if(bad){
        if(validatedResidualTarget){
          stats.validatedResidualCompileFailures[bad]=(stats.validatedResidualCompileFailures[bad]||0)+1;
        }
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
        }else if(bad==='duration_threshold_mismatch'){
          pricingDiagnostics.thresholdMismatch.evses++;
          for(const c0 of connectors){
            const rs=c0?.complexPricingDetail?.restrictions||[];
            const mins=rs.map(r=>Number(r?.durationRestrictions?.minDurationSeconds)).filter(x=>Number.isFinite(x)&&x>0);
            const maxs=rs.map(r=>Number(r?.durationRestrictions?.maxDurationSeconds)).filter(x=>Number.isFinite(x)&&x>0);
            for(const min of mins)for(const max of maxs){
              const key=`${max}->${min}`;
              pricingDiagnostics.thresholdMismatch.pairs[key]=(pricingDiagnostics.thresholdMismatch.pairs[key]||0)+1;
            }
            if(pricingDiagnostics.thresholdMismatch.samples.length<60)pricingDiagnostics.thresholdMismatch.samples.push({
              locationPk:String(row.electroverseLocationPk),physicalReference:pr,evsePk:e.pk??null,
              connectorPk:c0.pk??null,
              restrictions:rs.map(r=>({
                timeRestrictions:r?.timeRestrictions||null,
                weekdayRestrictions:r?.weekdayRestrictions||null,
                durationRestrictions:r?.durationRestrictions||null,
                priceComponents:r?.priceComponents||[]
              }))
            });
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
      if(compiled.some(x=>(x.pricing?.rules||[]).some(r=>Array.isArray(r.ocpiDurationBands)&&r.ocpiDurationBands.length)))stats.durationBandCandidateEvses++;
      const unique=[...new Map(compiled.map(x=>[pricingSig(x.pricing),x.pricing])).values()];
      if(p01Meta?.recoveryMode==='same_parent_homogeneous_price_only'){
        if(unique.length!==1){rej('validated_p01_price_only_donor_heterogeneous');continue;}
        const pricing=unique[0],sig=pricingSig(pricing);
        const gk=String(row.electroverseLocationPk)+'|'+parentNorm;
        let g=p01PriceOnlyGroups.get(gk);
        if(!g){
          g={
            locationPk:String(row.electroverseLocationPk),parentPdc:targetPdc,parentNorm,lat,lon,
            pricing,pricingSig:sig,sourcePks:new Set(),physicalReferences:new Set(),
            donorPks:new Set(),invalid:false
          };
          p01PriceOnlyGroups.set(gk,g);
        }else if(g.pricingSig!==sig){
          g.invalid=true;
        }
        g.sourcePks.add(e.pk??null);
        if(pr)g.physicalReferences.add(pr);
        if(p01Meta?.donorElectroverseEvsePk!=null)g.donorPks.add(p01Meta.donorElectroverseEvsePk);
        continue;
      }
      if(unique.length!==1 && !parentMode){
        // V9 connector-power representation:
        // one national EVSE may legitimately expose several connector tariffs.
        // Publish one offer line per power + pricing signature while keeping the
        // same EVSE identity. This avoids flattening distinct connector prices.
        const variants=new Map();
        for(const x of compiled){
          const powerKw=Number.isFinite(Number(x.powerKw))?Number(x.powerKw):null;
          const key=String(powerKw??'UNKNOWN')+'|'+pricingSig(x.pricing);
          let v=variants.get(key);
          if(!v){
            v={powerKw,pricing:x.pricing,connectors:[]};
            variants.set(key,v);
          }
          v.connectors.push(x);
        }
        for(const [variantKey,v] of variants){
          const pricing=v.pricing,currency=pricing.rules?.[0]?.currency||'EUR';
          const standards=[...new Set(v.connectors.map(x=>String(x.standard?.name||x.standard||'')).filter(Boolean))];
          const powerLabel=v.powerKw==null?'unknown':String(v.powerKw).replace(/[^0-9A-Za-z._-]/g,'_');
          const sigHash=sha(pricingSig(pricing)).slice(0,10);
          const offer={
            id:`electroverse-evse-power:${row.electroverseLocationPk}:${e.pk??k}:${powerLabel}:${sigHash}`,
            provider:'Electroverse',
            countries:['FR'],
            currency,
            priority:80,
            verifiedScope:'exact_evse_connector_power',
            evseIds:[targetPdc],
            pricing,
            metadata:{
              verified:true,
              identityMode,
              offerGranularity:'connector_power',
              offerVariantKey:variantKey,
              powerKw:v.powerKw,
              standards,
              electroverseLocationPk:String(row.electroverseLocationPk),
              electroverseEvsePk:e.pk??null,
              physicalReference:pr,
              connectorPks:v.connectors.map(x=>x.connectorPk),
              connectorCount:v.connectors.length,
              tariffHash:row.tariffHash||null,
              fetchedAt:row.fetchedAt||null,
              source:'Electroverse tariff cache'
            }
          };
          const id=tileId(lat,lon);if(!tiles.has(id))tiles.set(id,[]);
          tiles.get(id).push(offer);
          stats.connectorPowerVariantOffers++;
          stats.connectorPowerVariantConnectors+=v.connectors.length;
          if(validatedResidualTarget)stats.validatedResidualOffersCreated++;
        }
        stats.connectorPowerVariantEvses++;
        if(validatedResidualTarget)stats.validatedResidualHeterogeneousConnectors++;
        continue;
      }
      if(unique.length!==1){
        if(validatedResidualTarget)stats.validatedResidualHeterogeneousConnectors++;
        rej('heterogeneous_connectors_within_evse');continue;
      }

      const pricing=unique[0],currency=pricing.rules?.[0]?.currency||'EUR';
      if(parentMode){
        const gk=`${row.electroverseLocationPk}|${parentNorm}`;
        const g=parentGroups.get(gk)||{
          locationPk:String(row.electroverseLocationPk),parentPdc:targetPdc,parentNorm,
          lat,lon,entries:[],pricingBySig:new Map(),tariffHashes:new Set(),fetchedAts:new Set()
        };
        g.entries.push({
          physicalReference:pr,
          evsePk:e.pk??null,
          connectorPks:compiled.map(x=>x.connectorPk),
          connectorCount:compiled.length,
          compiled,
          pricing,
          donorElectroverseEvsePk:p01Meta?.donorElectroverseEvsePk??null,
          donorElectroverseLocationPk:p01Meta?.donorElectroverseLocationPk??null
        });
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
      if(validatedResidualTarget)stats.validatedResidualOffersCreated++;
      if(ordinalMode)stats.ordinalPublishedEvses++;
      if(identityMode==='strict_station_common_prefix_tail_bijection')stats.genericTailPublishedEvses++;
      if(identityMode==='strict_unique_local_suffix_identity')stats.suffixIdentityPublishedEvses++;
      if(identityMode==='strict_trimmed_long_suffix_identity')stats.trimmedSuffixPublishedEvses++;
      if(identityMode==='strict_pd1_final_ordinal_subgroup_bijection')stats.pd1FinalOrdinalPublishedEvses++;
      if(identityMode==='strict_via_final_ordinal_subgroup_bijection')stats.viaFinalOrdinalPublishedEvses++;
      if(identityMode==='strict_55c_bindex_zero_based_suffix')stats.c55BIndexPublishedEvses++;
      if(identityMode==='strict_via_structured_base_pair')stats.viaStructuredBasePairPublishedEvses++;
      if(identityMode==='strict_vianeo_official_source_ref_identity')stats.viaOfficialIdentityPublishedEvses++;
      if(identityMode==='validated_final_residual_unique_suffix_bijection')stats.finalResidualUniqueSuffixPublishedEvses++;
      if(identityMode==='validated_final_residual_common_tail_bijection')stats.finalResidualCommonTailPublishedEvses++;
      if(identityMode==='validated_p01_structured_parent_identity')stats.validatedP01ResidualPublishedEvses++;
      stats.publishedEvses++;stats.publishedOffers++;stats.publishedConnectorCount+=compiled.length;
    }
  }
}

for(const g of p01PriceOnlyGroups.values()){
  if(g.invalid){
    rej('validated_p01_price_only_parent_conflict');
    continue;
  }
  const pricing=g.pricing;
  const currency=pricing.rules?.[0]?.currency||'EUR';
  const offer={
    id:`electroverse-evse-p01-price-only:${g.locationPk}:${g.parentNorm}`,
    provider:'Electroverse',
    countries:['FR'],
    currency,
    priority:80,
    verifiedScope:'exact_evse',
    evseIds:[g.parentPdc],
    pricing,
    metadata:{
      verified:true,
      identityMode:'validated_p01_same_parent_homogeneous_price_only',
      offerGranularity:'evse_price_only',
      electroverseLocationPk:g.locationPk,
      electroverseEvsePks:[...g.sourcePks].filter(x=>x!=null),
      physicalReferences:[...g.physicalReferences],
      donorElectroverseEvsePks:[...g.donorPks],
      connectorCountKnown:false,
      source:'Electroverse tariff cache same-parent homogeneous sibling tariff'
    }
  };
  const id=tileId(g.lat,g.lon);if(!tiles.has(id))tiles.set(id,[]);
  tiles.get(id).push(offer);
  stats.validatedP01PriceOnlyPublishedEvses+=g.sourcePks.size;
  stats.validatedResidualOffersCreated++;
  stats.publishedEvses++;stats.publishedOffers++;
}

stats.parentCandidateGroups=parentGroups.size;
for(const g of parentGroups.values()){
  // A national parent EVSE may expose child connector references with different
  // powers and/or tariffs. Preserve every distinct power+pricing variant instead
  // of flattening the parent to one tariff or rejecting heterogeneous children.
  const variants=new Map();
  for(const entry of g.entries){
    for(const x of entry.compiled||[]){
      const powerKw=Number.isFinite(Number(x.powerKw))?Number(x.powerKw):null;
      const key=String(powerKw??'UNKNOWN')+'|'+pricingSig(x.pricing);
      let v=variants.get(key);
      if(!v){
        v={powerKw,pricing:x.pricing,units:[],sourcePks:new Set(),physicalReferences:new Set(),standards:new Set()};
        variants.set(key,v);
      }
      v.units.push({connectorPk:x.connectorPk,evsePk:entry.evsePk,physicalReference:entry.physicalReference});
      if(entry.evsePk!=null)v.sourcePks.add(entry.evsePk);
      if(entry.physicalReference)v.physicalReferences.add(entry.physicalReference);
      const standard=String(x.standard?.name||x.standard||'').trim();
      if(standard)v.standards.add(standard);
    }
  }
  for(const [variantKey,v] of variants){
    const pricing=v.pricing;
    const currency=pricing.rules?.[0]?.currency||'EUR';
    const powerLabel=v.powerKw==null?'unknown':String(v.powerKw).replace(/[^0-9A-Za-z._-]/g,'_');
    const sigHash=sha(pricingSig(pricing)).slice(0,10);
    const connectorPks=v.units.map(x=>x.connectorPk).filter(x=>x!=null);
    const offer={
      id:`electroverse-evse-parent-power:${g.locationPk}:${g.parentNorm}:${powerLabel}:${sigHash}`,
      provider:'Electroverse',
      countries:['FR'],
      currency,
      priority:80,
      verifiedScope:'exact_evse_connector_power',
      evseIds:[g.parentPdc],
      pricing,
      metadata:{
        verified:true,
        identityMode:'exact_unique_national_irve_pdc_parent_connector_suffix',
        offerGranularity:'connector_power',
        offerVariantKey:variantKey,
        powerKw:v.powerKw,
        standards:[...v.standards],
        electroverseLocationPk:g.locationPk,
        physicalReferences:[...v.physicalReferences],
        electroverseEvsePks:[...v.sourcePks],
        donorElectroverseEvsePks:[...new Set(g.entries.map(x=>x.donorElectroverseEvsePk).filter(x=>x!=null))],
        connectorPks,
        connectorCount:v.units.length,
        childReferenceCount:v.physicalReferences.size,
        tariffHashes:[...g.tariffHashes],
        fetchedAts:[...g.fetchedAts],
        source:'Electroverse tariff cache'
      }
    };
    const id=tileId(g.lat,g.lon);if(!tiles.has(id))tiles.set(id,[]);
    tiles.get(id).push(offer);
    stats.parentPublishedEvses++;
    stats.parentPublishedChildRefs+=v.physicalReferences.size;
    stats.publishedEvses++;stats.publishedOffers++;stats.publishedConnectorCount+=v.units.length;
  }
}

const attachedP01Aliases=new Set();
for(const offers of tiles.values()) for(const offer of offers){
  const target=norm(offer.evseIds?.[0]);
  if(!target)continue;
  const aliases=validatedP01AliasesByTarget.get(target)||[];
  if(!aliases.length)continue;
  const offerLoc=String(offer.metadata?.electroverseLocationPk??'');
  const matching=aliases.filter(x=>!offerLoc||String(x.electroverseLocationPk)===offerLoc);
  if(!matching.length)continue;
  offer.metadata=offer.metadata||{};
  offer.metadata.electroverseAliasEvsePks=[...new Set([
    ...(offer.metadata.electroverseAliasEvsePks||[]),
    ...matching.map(x=>x.electroverseEvsePk).filter(x=>x!=null)
  ])];
  offer.metadata.electroverseAliasPhysicalReferences=[...new Set([
    ...(offer.metadata.electroverseAliasPhysicalReferences||[]),
    ...matching.map(x=>x.physicalReference).filter(Boolean)
  ])];
  for(const x of matching)attachedP01Aliases.add(String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk));
}
stats.validatedP01AliasSourceEvses=attachedP01Aliases.size;

const offersByTarget=new Map(),duplicateSamples=[];
for(const [tileIdKey,offers] of tiles.entries()) for(const offer of offers){
  const target=norm(offer.evseIds?.[0]);
  if(!target)continue;
  // Connector-power offers intentionally share the same national EVSE.
  // Deduplicate them only within the same power/tariff variant.
  const variant=offer.metadata?.offerGranularity==='connector_power'
    ? '|CONNECTOR_POWER|'+String(offer.metadata?.powerKw??'UNKNOWN')+'|'+pricingSig(offer.pricing)
    : '';
  const dedupeKey=target+variant;
  const arr=offersByTarget.get(dedupeKey)||[];
  arr.push({tileIdKey,offer,pricingSig:pricingSig(offer.pricing)});
  offersByTarget.set(dedupeKey,arr);
}
const mergeOfferProvenance=(keep,items)=>{
  keep.metadata=keep.metadata||{};
  const sourcePks=new Set();
  const refs=new Set();
  const aliasPks=new Set(keep.metadata.electroverseAliasEvsePks||[]);
  const aliasRefs=new Set(keep.metadata.electroverseAliasPhysicalReferences||[]);
  for(const x of items){
    const m=x.offer.metadata||{};
    for(const pk of m.electroverseEvsePks||[]) if(pk!=null) sourcePks.add(pk);
    if(m.electroverseEvsePk!=null) sourcePks.add(m.electroverseEvsePk);
    for(const r of m.physicalReferences||[]) if(r) refs.add(r);
    if(m.physicalReference) refs.add(m.physicalReference);
    for(const pk of m.electroverseAliasEvsePks||[]) if(pk!=null) aliasPks.add(pk);
    for(const r of m.electroverseAliasPhysicalReferences||[]) if(r) aliasRefs.add(r);
  }
  if(sourcePks.size){
    keep.metadata.electroverseEvsePks=[...sourcePks];
    delete keep.metadata.electroverseEvsePk;
  }
  if(refs.size){
    keep.metadata.physicalReferences=[...refs];
    delete keep.metadata.physicalReference;
  }
  if(aliasPks.size) keep.metadata.electroverseAliasEvsePks=[...aliasPks];
  if(aliasRefs.size) keep.metadata.electroverseAliasPhysicalReferences=[...aliasRefs];
  keep.metadata.provenanceMergedFromIdenticalOffers=items.length;
};
const dropOfferIds=new Set();
for(const [target,items] of offersByTarget.entries()){
  if(items.length<2)continue;
  stats.duplicatePublishedEvseTargetsBeforeDedup+=items.length-1;
  const sigs=new Set(items.map(x=>x.pricingSig));
  const validatedItems=items.filter(x=>['validated_numeric_residual_unique_bijection','validated_s82_residual_unique_suffix_bijection','validated_mgp_residual_unique_suffix_bijection','validated_le2_residual_unique_suffix_bijection','validated_final_residual_unique_suffix_bijection','validated_final_residual_common_tail_bijection'].includes(x.offer.metadata?.identityMode));
  if(validatedItems.length===1){
    // A strict individual post-overlay bijection is more specific than any grouped
    // attribution that happens to claim the same national target. Preserve it and
    // discard the competing group offers, even when their pricing differs.
    const keep=validatedItems[0];
    if(sigs.size===1) mergeOfferProvenance(keep.offer,items);
    for(const x of items) if(x!==keep) dropOfferIds.add(x.offer.id);
    stats.dedupedIdenticalOffers+=sigs.size===1?items.length-1:0;
    if(sigs.size>1){
      stats.conflictingPublishedEvseTargetsBeforeDedup+=items.length-1;
      stats.conflictingTargetsDropped++;
      rej('validated_numeric_superseded_group_conflict');
    }
  }else if(sigs.size===1){
    const sorted=[...items].sort((a,b)=>String(a.offer.id).localeCompare(String(b.offer.id)));
    mergeOfferProvenance(sorted[0].offer,items);
    for(const x of sorted.slice(1))dropOfferIds.add(x.offer.id);
    stats.dedupedIdenticalOffers+=items.length-1;
  }else{
    for(const x of items)dropOfferIds.add(x.offer.id);
    stats.conflictingPublishedEvseTargetsBeforeDedup+=items.length-1;
    stats.conflictingTargetsDropped++;
    rej('duplicate_evse_conflicting_pricing');
  }
  const debugNumericTargets=new Set(['FRGSPE12345958361','FRGSPE12345958371']);
  if(debugNumericTargets.has(target)){
    console.log('DEBUG_NUMERIC_DEDUP '+JSON.stringify({
      target,
      items:items.map(x=>({
        id:x.offer.id,
        identityMode:x.offer.metadata?.identityMode||null,
        sourcePks:[
          ...(x.offer.metadata?.electroverseEvsePks||[]).map(String),
          ...(x.offer.metadata?.electroverseEvsePk!=null?[String(x.offer.metadata.electroverseEvsePk)]:[])
        ],
        sourceProfiles:[
          ...(x.offer.metadata?.electroverseEvsePks||[]).map(String),
          ...(x.offer.metadata?.electroverseEvsePk!=null?[String(x.offer.metadata.electroverseEvsePk)]:[])
        ].map(pk=>({pk,profile:debugNumericProfiles.get(pk)||null})),
        physicalReferences:x.offer.metadata?.physicalReferences||[x.offer.metadata?.physicalReference].filter(Boolean),
        connectorCount:x.offer.metadata?.connectorCount??null,
        pricing:x.offer.pricing
      })),
      pricingConflict:sigs.size>1,
      dropped:items.filter(x=>dropOfferIds.has(x.offer.id)).map(x=>x.offer.id)
    },null,2));
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
stats.trimmedSuffixPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_trimmed_long_suffix_identity').length;
stats.pd1FinalOrdinalPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_pd1_final_ordinal_subgroup_bijection').length;
stats.izfHomogeneousGroupPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_izf_homogeneous_exact_set').length;
stats.viaFinalOrdinalPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_via_final_ordinal_subgroup_bijection').length;
stats.viaHomogeneousGroupPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_via_homogeneous_exact_set').length;
stats.viaStructuredBasePairPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_via_structured_base_pair').length;
stats.viaOfficialIdentityPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_vianeo_official_source_ref_identity').length;
stats.c55HomogeneousGroupPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_55c_homogeneous_exact_set').length;
stats.hpcOrdinalGroupPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_hpc_duplicate_ordinal_to_three_digit_pdc').length;
stats.s30StructuredChildPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_s30_structured_child_collapse').length;
stats.c55BIndexPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_55c_bindex_zero_based_suffix').length;
stats.validatedNumericResidualPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='validated_numeric_residual_unique_bijection').length;
stats.validatedS82ResidualPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='validated_s82_residual_unique_suffix_bijection').length;
stats.validatedMgpResidualPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='validated_mgp_residual_unique_suffix_bijection').length;
stats.validatedLe2ResidualPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='validated_le2_residual_unique_suffix_bijection').length;
stats.finalResidualUniqueSuffixPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='validated_final_residual_unique_suffix_bijection').length;
stats.finalResidualCommonTailPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='validated_final_residual_common_tail_bijection').length;
stats.finalResidualHomogeneousGroupPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='validated_final_residual_homogeneous_exact_set').length;
stats.pd1TechnicalGroupPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_pd1_official_technical_homogeneous_group').length;
stats.pd1TechnicalGroupByKey={};
for(const o of finalOffers.filter(o=>o.metadata?.identityMode==='strict_pd1_official_technical_homogeneous_group')){
  const k=JSON.stringify({kw:o.metadata?.powerKwClass,plugs:o.metadata?.plugTypes||[]});
  stats.pd1TechnicalGroupByKey[k]=(stats.pd1TechnicalGroupByKey[k]||0)+1;
}
stats.drvPowerGroupPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_drv_native_power_homogeneous_group').length;
stats.drvPowerGroupByKw={};
for(const o of finalOffers.filter(o=>o.metadata?.identityMode==='strict_drv_native_power_homogeneous_group')){
  const k=String(o.metadata?.powerKwClass??'UNKNOWN');
  stats.drvPowerGroupByKw[k]=(stats.drvPowerGroupByKw[k]||0)+1;
}
stats.drvHomogeneousGroupPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_drv_homogeneous_exact_set').length;
stats.sigHomogeneousGroupPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_sig_homogeneous_exact_set').length;
stats.qovHomogeneousGroupPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_qov_homogeneous_exact_set').length;
stats.bHomogeneousGroupPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_b_location_homogeneous_exact_set').length;
stats.genericHomogeneousGroupPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_generic_single_operator_homogeneous_exact_set').length;
stats.genericPriceOnlyGroupPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_generic_single_operator_price_only_exact_set').length;
stats.genericHomogeneousGroupByOperator={};
for(const o of finalOffers.filter(o=>o.metadata?.identityMode==='strict_generic_single_operator_homogeneous_exact_set')){
  const op=String(o.metadata?.operator||'UNKNOWN');
  stats.genericHomogeneousGroupByOperator[op]=(stats.genericHomogeneousGroupByOperator[op]||0)+1;
}
stats.genericPriceOnlyGroupByOperator={};
for(const o of finalOffers.filter(o=>o.metadata?.identityMode==='strict_generic_single_operator_price_only_exact_set')){
  const op=String(o.metadata?.operator||'UNKNOWN');
  stats.genericPriceOnlyGroupByOperator[op]=(stats.genericPriceOnlyGroupByOperator[op]||0)+1;
}
stats.trimmedSuffixPublishedEvses=finalOffers.filter(o=>o.metadata?.identityMode==='strict_trimmed_long_suffix_identity').length;
stats.durationBandPublishedEvses=finalOffers.filter(o=>(o.pricing?.rules||[]).some(r=>Array.isArray(r.ocpiDurationBands)&&r.ocpiDurationBands.length)).length;

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
    strictPd1FinalOrdinalSubgroupBijection:true,
    strictIzfHomogeneousExactSet:true,
    izfExactSetRequiresEqualCardinality:true,
    izfExactSetRequiresHomogeneousPricing:true,
    izfExactSetRequiresUniformConnectorCount:true,
    izfExactSetRequiresGlobalPdcUniqueness:true,
    strictViaFinalOrdinalSubgroupBijection:true,
    strictViaHomogeneousExactSet:true,
    strictVianeoOfficialSourceRefIdentity:true,
    vianeoOfficialIdentityRequiresLocalTarget:true,
    vianeoOfficialIdentityRequiresGlobalPdcUniqueness:true,
    vianeoOfficialIdentityRequiresUniqueTargetUse:true,
    viaExactSetRequiresEqualCardinality:true,
    viaExactSetRequiresHomogeneousPricing:true,
    viaExactSetRequiresUniformConnectorCount:true,
    viaExactSetRequiresGlobalPdcUniqueness:true,
    strictViaStructuredBasePair:true,
    viaStructuredBasePairRequiresEmbeddedStationStem:true,
    viaStructuredBasePairRequiresConnectorPairOneTwo:true,
    viaStructuredBasePairRequiresGlobalPdcUniqueness:true,
    strict55cHomogeneousExactSet:true,
    c55ExactSetRequiresEqualCardinality:true,
    c55ExactSetRequiresHomogeneousPricing:true,
    c55ExactSetRequiresUniformConnectorCount:true,
    c55ExactSetRequiresGlobalPdcUniqueness:true,
    strictHpcDuplicateOrdinalToThreeDigitPdc:true,
    hpcOrdinalRequiresExactSourceTargetOrdinalSet:true,
    hpcOrdinalRequiresGlobalPdcUniqueness:true,
    hpcDuplicateOrdinalRequiresHomogeneousPricing:true,
    strict55cBIndexZeroBasedSuffix:true,
    validatedNumericResidualUniqueBijection:true,
    validatedNumericResidualMappingCount:validatedNumericResidualTargets.size,
    validatedS82ResidualUniqueSuffixBijection:true,
    validatedS82ResidualMappingCount:validatedS82ResidualTargets.size,
    validatedMgpResidualUniqueSuffixBijection:true,
    validatedMgpResidualMappingCount:validatedMgpResidualTargets.size,
    validatedLe2ResidualUniqueSuffixBijection:true,
    validatedLe2ResidualMappingCount:validatedLe2ResidualTargets.size,
    c55BIndexRequiresExactResidualSet:true,
    c55BIndexRequiresGlobalPdcUniqueness:true,
    strictPd1OfficialTechnicalHomogeneousGroup:true,
    pd1TechnicalUsesOfficialPowerdotInventory:true,
    pd1TechnicalRequiresExactPowerAndPlugGroup:true,
    pd1TechnicalRequiresExactGroupCardinality:true,
    pd1TechnicalRequiresHomogeneousElectroversePricing:true,
    pd1TechnicalRequiresGlobalPdcUniqueness:true,
    pd1TechnicalNeverInfersIndividualOrderWithinGroup:true,
    strictDrvNativePowerHomogeneousGroup:true,
    drvPowerUsesOfficialNativePowerKw:true,
    drvPowerRequiresExactGroupCardinality:true,
    drvPowerRequiresHomogeneousElectroversePricing:true,
    drvPowerRequiresGlobalPdcUniqueness:true,
    drvPowerNeverInfersIndividualOrderWithinGroup:true,
    strictDrvHomogeneousExactSet:true,
    strictSigHomogeneousExactSet:true,
    strictQovHomogeneousExactSet:true,
    strictBLocationHomogeneousExactSet:true,
    operatorExactSetRequiresEqualCardinality:true,
    operatorExactSetRequiresSingleOperatorUnclaimedTargets:true,
    operatorExactSetRequiresHomogeneousPricing:true,
    operatorExactSetRequiresUniformConnectorCount:true,
    operatorExactSetRequiresGlobalPdcUniqueness:true,
    strictGenericSingleOperatorHomogeneousExactSet:true,
    genericExactSetRequiresRecognizedSingleOperator:true,
    genericExactSetRequiresEqualCardinality:true,
    genericExactSetRequiresHomogeneousPricing:true,
    genericExactSetRequiresUniformConnectorCount:true,
    genericPriceOnlyExactSetAllowsUnknownConnectorDistribution:true,
    genericPriceOnlyExactSetRequiresHomogeneousPricing:true,
    genericExactSetRequiresGlobalPdcUniqueness:true,
    suffixIdentityRequiresGlobalUniqueness:true,
    suffixIdentityRequiresUnclaimedTarget:true,
    strictTrimmedLongSuffixIdentityMinLength:7,
    trimmedSuffixRequiresGlobalUniqueness:true,
    trimmedSuffixRequiresUnclaimedTarget:true,
    trimmedSuffixRejectsDuplicateTargetClaims:true,
    evseLevelPricing:true,
    stationLevelFlattening:false,
    electraDependency:false,
    proximityInference:false,
    heterogeneousConnectorsWithinEvseFailClosed:true,
    unsupportedPricingFailClosed:true,
    duplicateSamePriceDeduplicated:true,
    duplicateConflictingPriceFailClosed:true,
    dateRestrictedPricingUsesActiveFranceLocalDate:true,
    dateRestrictionEndExclusive:true,
    boundedDurationPricingAsOcpiBands:true,
    allDurationRestrictionsAsOcpiBands:true,
    boundedDurationBandOverlapFailClosed:true
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

// rebuild trigger after S63 validated residual mappings 2026-10-01

// V9 connector-power offer model enabled 2026-10-01

// rebuild trigger after post-connector-power MAP validation 2026-10-01

// merge compatible split all-day pricing components 2026-10-01

// debug NUMERIC exact-set dedupe 2026-10-01
// enrich NUMERIC dedupe debug 2026-10-01
// trace NUMERIC source connector profiles 2026-10-01

// rebuild trigger after hardened zero mapping 2026-10-01

// rebuild after persisted P01 donor ledger 2026-10-01

// rebuild after persisted P01 alias ledger 2026-10-01
