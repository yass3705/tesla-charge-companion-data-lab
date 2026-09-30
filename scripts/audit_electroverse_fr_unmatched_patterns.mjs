import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const MANIFEST=CACHE+'/manifest.json';
const OUT=process.argv[2]||'reports/electroverse-fr-unmatched-patterns.json';
const OVERLAY='data/platforms/electroverse/france-evse';

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const text=x=>String(x??'').trim();
const inc=(o,k,n=1)=>o[k]=(o[k]||0)+n;
const top=(o,n=50)=>Object.entries(o).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).slice(0,n).map(([key,count])=>({key,count}));
const opOf=p=>{
  const m=String(p||'').match(/^FR([A-Z0-9]{1,6})E/);
  return m?m[1]:'UNKNOWN';
};
const rawShape=s=>{
  const x=text(s);
  if(/^\d+$/.test(x))return 'digits';
  if(/^[A-Za-z]+$/.test(x))return 'letters';
  if(/^[A-Za-z0-9]+$/.test(x))return 'alnum';
  if(/^[A-Za-z0-9]+-[A-Za-z0-9-]+$/.test(x))return 'hyphenated';
  if(x.includes('*'))return 'asterisk';
  if(x.includes('_'))return 'underscore';
  if(x.includes(':'))return 'colon';
  if(x.includes('/'))return 'slash';
  return 'other';
};

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const manifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const overlayManifest=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedPdcs=new Set();
for(const t of overlayManifest.tiles||[]){
  const gz=await fs.readFile(OVERLAY+'/'+t.file);
  const payload=JSON.parse(zlib.gunzipSync(gz).toString('utf8'));
  for(const o of payload.emspOffers||[])for(const id of o.evseIds||[])publishedPdcs.add(norm(id));
}
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const globalPdcOwners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;
  const set=globalPdcOwners.get(k)||new Set();set.add(String(m.irveStationId||m.electroverseLocationPk||''));globalPdcOwners.set(k,set);
}

const unmatched=[];
const unmatchedByLocation=new Map();
const operatorProfiles=new Map();
const counters={
  byNormLength:{},byRawShape:{},byOperator:{},byLocalPdcCount:{},
  uniqueLocalContainsRef:{},uniqueRefContainsLocalPdc:{},uniquePdcPayloadEqualsRef:{},
  uniqueLastTokenSuffix:{},uniqueFirstTokenSuffix:{},partialCommonPrefixTail:{},
  unclaimedFinalOrdinalRefs:{},unclaimedShortSuffixRefs:{},unclaimedPdcsByOperator:{},
  trimmedLongSuffixRefs:{},trimmedLongSuffixLengths:{}
};

for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk)); if(!m)continue;
    const localRaw=(m.irvePdcIds||row.irvePdcIds||[]).filter(Boolean);
    const localByNorm=new Map(localRaw.map(p=>[norm(p),p]).filter(([k])=>k));
    const local=[...localByNorm.keys()];
    if(!local.length)continue;

    // Reproduce all currently accepted identity families.
    const ordinalTargets=new Map(),usedForOrdinal=new Set(),hardNumeric=[];
    for(const e0 of row.tariff?.evses||[]){
      const pr0=text(e0?.physicalReference);if(!pr0)continue;
      const k0=norm(pr0);
      if(local.includes(k0)){usedForOrdinal.add(k0);continue;}
      const p0=local.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
      if(p0.length===1){usedForOrdinal.add(p0[0]);continue;}
      if(/^\d{1,2}$/.test(k0))hardNumeric.push({e:e0,n:Number(k0)});
    }
    if(hardNumeric.length&&new Set(hardNumeric.map(x=>x.n)).size===hardNumeric.length){
      const available=local.filter(p=>!usedForOrdinal.has(p));let chosen=null;
      for(const width of [1,2]){
        if(available.some(p=>p.length<=width))continue;
        const prefixes=new Set(available.map(p=>p.slice(0,-width)));if(prefixes.size!==1)continue;
        const nums=available.map(p=>/^\d+$/.test(p.slice(-width))?Number(p.slice(-width)):NaN);
        if(nums.some(x=>!Number.isFinite(x)))continue;
        const wanted=new Set(hardNumeric.map(x=>x.n)),byNum=new Map();let ok=true;
        for(let i=0;i<available.length;i++){const n=nums[i];if(!wanted.has(n))continue;if(byNum.has(n)){ok=false;break;}byNum.set(n,available[i]);}
        if(!ok||byNum.size!==hardNumeric.length)continue;
        if([...byNum.values()].some(p=>(globalPdcOwners.get(p)?.size||0)!==1))continue;
        chosen=byNum;break;
      }
      if(chosen)for(const x of hardNumeric)ordinalTargets.set(x.e,chosen.get(x.n));
    }

    const genericTargets=new Map(),usedForGeneric=new Set(),genericHard=[];
    for(const e0 of row.tariff?.evses||[]){
      const pr0=text(e0?.physicalReference);if(!pr0)continue;const k0=norm(pr0);
      if(local.includes(k0)){usedForGeneric.add(k0);continue;}
      const p0=local.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
      if(p0.length===1){usedForGeneric.add(p0[0]);continue;}
      genericHard.push({e:e0,k:k0});
    }
    if(genericHard.length&&new Set(genericHard.map(x=>x.k)).size===genericHard.length){
      const available=local.filter(p=>!usedForGeneric.has(p));
      if(available.length){
        let cp=available[0];for(const p of available.slice(1)){let i=0;while(i<cp.length&&i<p.length&&cp[i]===p[i])i++;cp=cp.slice(0,i);if(!cp)break;}
        if(cp.length>=4){
          const t2p=new Map();let ok=true;
          for(const p of available){const tail=p.slice(cp.length);if(!tail||t2p.has(tail)){ok=false;break;}t2p.set(tail,p);}
          if(ok&&genericHard.every(x=>t2p.has(x.k))){
            const targets=genericHard.map(x=>t2p.get(x.k));
            if(new Set(targets).size===genericHard.length&&targets.every(p=>(globalPdcOwners.get(p)?.size||0)===1))
              for(const x of genericHard)genericTargets.set(x.e,t2p.get(x.k));
          }
        }
      }
    }

    const suffixTargets=new Map(),reservedTargets=new Set();
    for(const e0 of row.tariff?.evses||[]){
      const pr0=text(e0?.physicalReference);if(!pr0)continue;const k0=norm(pr0);
      if(local.includes(k0)){reservedTargets.add(k0);continue;}
      const p0=local.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
      if(p0.length===1){reservedTargets.add(p0[0]);continue;}
      if(ordinalTargets.has(e0)){reservedTargets.add(ordinalTargets.get(e0));continue;}
      if(genericTargets.has(e0)){reservedTargets.add(genericTargets.get(e0));continue;}
    }
    const claimed=new Set();
    for(const e0 of row.tariff?.evses||[]){
      const pr0=text(e0?.physicalReference);if(!pr0)continue;const k0=norm(pr0);
      if(k0.length<4||local.includes(k0)||ordinalTargets.has(e0)||genericTargets.has(e0))continue;
      const p0=local.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\d{1,2}$/.test(k0.slice(p.length)));
      if(p0.length===1)continue;
      const matches=local.filter(p=>p.endsWith(k0));
      if(matches.length!==1)continue;
      const target=matches[0];
      if(reservedTargets.has(target)||claimed.has(target)||(globalPdcOwners.get(target)?.size||0)!==1)continue;
      suffixTargets.set(e0,target);claimed.add(target);
    }

    const claimedIdentityTargets=new Set();
    for(const e0 of row.tariff?.evses||[]){
      const pr0=text(e0?.physicalReference);if(!pr0)continue;const k0=norm(pr0);
      if(local.includes(k0)){claimedIdentityTargets.add(k0);continue;}
      const p0=local.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\\d{1,2}$/.test(k0.slice(p.length)));
      if(p0.length===1){claimedIdentityTargets.add(p0[0]);continue;}
      if(ordinalTargets.has(e0)){claimedIdentityTargets.add(ordinalTargets.get(e0));continue;}
      if(genericTargets.has(e0)){claimedIdentityTargets.add(genericTargets.get(e0));continue;}
      if(suffixTargets.has(e0)){claimedIdentityTargets.add(suffixTargets.get(e0));continue;}
    }
    const unclaimedLocal=local.filter(p=>!claimedIdentityTargets.has(p));
    if(unclaimedLocal.length)inc(counters.unclaimedPdcsByOperator,opOf(local[0]),unclaimedLocal.length);

    const unresolvedForUnclaimed=[];
    for(const e0 of row.tariff?.evses||[]){
      const pr0=text(e0?.physicalReference);if(!pr0)continue;const k0=norm(pr0);
      if(local.includes(k0)||ordinalTargets.has(e0)||genericTargets.has(e0)||suffixTargets.has(e0))continue;
      const p0=local.filter(p=>k0.startsWith(p)&&k0.length>p.length&&/^\\d{1,2}$/.test(k0.slice(p.length)));
      if(p0.length)continue;
      unresolvedForUnclaimed.push({e:e0,raw:pr0,k:k0});
      if(k0.length<4){
        const sm=unclaimedLocal.filter(p=>p.endsWith(k0));
        if(sm.length===1)inc(counters.unclaimedShortSuffixRefs,opOf(sm[0]),1);
      }
      let trimmedHit=null;
      for(let len=Math.min(k0.length-1,20);len>=6;len--){
        const s=k0.slice(-len),sm=unclaimedLocal.filter(p=>p.endsWith(s));
        if(sm.length===1&&(globalPdcOwners.get(sm[0])?.size||0)===1){trimmedHit={p:sm[0],len};break;}
      }
      if(trimmedHit){
        inc(counters.trimmedLongSuffixRefs,opOf(trimmedHit.p),1);
        inc(counters.trimmedLongSuffixLengths,String(trimmedHit.len),1);
      }
    }
    const stemGroups=new Map();
    for(const x of unresolvedForUnclaimed){
      const mm=x.raw.match(/^(.*?)[\\s_\\-\\/]*([0-9]{1,2})$/);if(!mm||!mm[1])continue;
      const stem=norm(mm[1]),ord=Number(mm[2]),arr=stemGroups.get(stem)||[];
      arr.push({...x,ord});stemGroups.set(stem,arr);
    }
    for(const items of stemGroups.values()){
      if(!items.length||new Set(items.map(x=>x.ord)).size!==items.length)continue;
      const wanted=new Set(items.map(x=>x.ord)),matches=[];
      for(const width of [1,2]){
        const groups=new Map();
        for(const p of unclaimedLocal){
          if(p.length<=width)continue;const tail=p.slice(-width);if(!/^\\d+$/.test(tail))continue;
          const prefix=p.slice(0,-width),ord=Number(tail),arr=groups.get(prefix)||[];
          arr.push({p,ord});groups.set(prefix,arr);
        }
        for(const rows of groups.values()){
          if(rows.length!==items.length||new Set(rows.map(r=>r.ord)).size!==rows.length)continue;
          if(rows.some(r=>!wanted.has(r.ord)))continue;
          if(rows.some(r=>(globalPdcOwners.get(r.p)?.size||0)!==1))continue;
          matches.push(rows);
        }
      }
      if(matches.length===1)inc(counters.unclaimedFinalOrdinalRefs,opOf(matches[0][0].p),items.length);
    }

    for(const e of row.tariff?.evses||[]){
      const raw=text(e?.physicalReference); if(!raw)continue; const k=norm(raw);
      if(local.includes(k))continue;
      const parents=local.filter(p=>k.startsWith(p)&&k.length>p.length&&/^\d{1,2}$/.test(k.slice(p.length)));
      if(parents.length===1||ordinalTargets.has(e)||genericTargets.has(e)||suffixTargets.has(e))continue;
      // Only the exact rejection family requested: no parent candidate at all.
      if(parents.length)continue;

      const operator=opOf(local[0]);
      let op=operatorProfiles.get(operator);
      if(!op){op={count:0,lengths:{},shapes:{},samples:[]};operatorProfiles.set(operator,op);}
      op.count++;inc(op.lengths,String(k.length));inc(op.shapes,rawShape(raw));
      if(op.samples.length<12)op.samples.push({
        locationPk:String(row.electroverseLocationPk),evsePk:e.pk??null,
        physicalReference:raw,normalized:k,localPdcCount:local.length,localPdcs:localRaw.slice(0,20)
      });
      inc(counters.byNormLength,String(k.length));inc(counters.byRawShape,rawShape(raw));
      inc(counters.byOperator,operator);inc(counters.byLocalPdcCount,String(local.length));

      const contains=local.filter(p=>p.includes(k)&&k.length>=3);
      if(contains.length===1)inc(counters.uniqueLocalContainsRef,String(k.length));
      const refContains=local.filter(p=>k.includes(p)&&p.length>=4);
      if(refContains.length===1)inc(counters.uniqueRefContainsLocalPdc,String(k.length));

      const payload=local.filter(p=>{
        const i=p.indexOf('E',2);return i>=0&&p.slice(i+1)===k;
      });
      if(payload.length===1)inc(counters.uniquePdcPayloadEqualsRef,String(k.length));

      const tokens=raw.toUpperCase().split(/[^A-Z0-9]+/).filter(Boolean);
      const last=tokens.at(-1)||'',first=tokens[0]||'';
      const lastM=last.length>=2?local.filter(p=>p.endsWith(norm(last))):[];
      if(lastM.length===1)inc(counters.uniqueLastTokenSuffix,String(norm(last).length));
      const firstM=first.length>=2?local.filter(p=>p.endsWith(norm(first))):[];
      if(firstM.length===1)inc(counters.uniqueFirstTokenSuffix,String(norm(first).length));

      // Relaxed station-tail diagnostic: individual exact tail hit under a station common prefix,
      // without promoting it unless the full station is a bijection.
      let cp=local[0];for(const p of local.slice(1)){let i=0;while(i<cp.length&&i<p.length&&cp[i]===p[i])i++;cp=cp.slice(0,i);if(!cp)break;}
      if(cp.length>=4){
        const hits=local.filter(p=>p.slice(cp.length)===k);
        if(hits.length===1)inc(counters.partialCommonPrefixTail,String(k.length));
      }

      const locKey=String(row.electroverseLocationPk);
      unmatchedByLocation.set(locKey,(unmatchedByLocation.get(locKey)||0)+1);
      if(unmatched.length<200)unmatched.push({
        locationPk:String(row.electroverseLocationPk),evsePk:e.pk??null,physicalReference:raw,
        normalized:k,operator,localPdcCount:local.length,localPdcs:localRaw.slice(0,30)
      });
    }
  }
}

const total=Object.values(counters.byNormLength).reduce((a,b)=>a+b,0);
let preciseFullyCoveredLocations=0,precisePartialLocations=0,preciseZeroCoveredLocations=0;
let preciseLocalPdcs=0,preciseCoveredPdcs=0,preciseUncoveredPdcs=0;
const preciseUncoveredByOperator={};
for(const [locationPk] of unmatchedByLocation){
  const m=byPk.get(locationPk);if(!m)continue;
  const local=[...new Set((m.irvePdcIds||[]).map(norm).filter(Boolean))];
  if(!local.length)continue;
  const covered=local.filter(p=>publishedPdcs.has(p)),missing=local.filter(p=>!publishedPdcs.has(p));
  preciseLocalPdcs+=local.length;preciseCoveredPdcs+=covered.length;preciseUncoveredPdcs+=missing.length;
  const op=opOf(local[0]);
  if(!missing.length)preciseFullyCoveredLocations++;
  else if(!covered.length)preciseZeroCoveredLocations++;
  else precisePartialLocations++;
  if(missing.length)inc(preciseUncoveredByOperator,op,missing.length);
}
const report={
  generatedAt:new Date().toISOString(),dataset:'electroverse-fr-unmatched-identity-pattern-audit',
  totalUnmatched:total,
  preciseCoverageGap:{
    locationsWithExactUnmatchedRefs:unmatchedByLocation.size,
    fullyCoveredLocations:preciseFullyCoveredLocations,
    partialLocations:precisePartialLocations,
    zeroCoveredLocations:preciseZeroCoveredLocations,
    localPdcsAtThoseLocations:preciseLocalPdcs,
    coveredPdcsAtThoseLocations:preciseCoveredPdcs,
    uncoveredPdcsAtThoseLocations:preciseUncoveredPdcs,
    coverageRate:preciseLocalPdcs?preciseCoveredPdcs/preciseLocalPdcs:null,
    uncoveredPdcsByOperator:top(preciseUncoveredByOperator,50)
  },
  topOperators:top(counters.byOperator,30),
  operatorProfiles:[...operatorProfiles.entries()].sort((a,b)=>b[1].count-a[1].count).slice(0,30).map(([operator,p])=>({
    operator,count:p.count,topLengths:top(p.lengths,10),topShapes:top(p.shapes,10),samples:p.samples
  })),
  normLength:top(counters.byNormLength,50),
  rawShape:top(counters.byRawShape,20),
  localPdcCount:top(counters.byLocalPdcCount,30),
  candidateDiagnostics:{
    uniqueLocalPdcContainsWholeRefByRefLength:top(counters.uniqueLocalContainsRef,50),
    uniqueRefContainsWholeLocalPdcByRefLength:top(counters.uniqueRefContainsLocalPdc,50),
    exactPdcPayloadAfterFirstEEqualsRefByRefLength:top(counters.uniquePdcPayloadEqualsRef,50),
    uniqueLastRawTokenMatchesPdcSuffixByTokenLength:top(counters.uniqueLastTokenSuffix,50),
    uniqueFirstRawTokenMatchesPdcSuffixByTokenLength:top(counters.uniqueFirstTokenSuffix,50),
    individualCommonPrefixTailHitByRefLength:top(counters.partialCommonPrefixTail,50),
    unclaimedPdcCountByOperator:top(counters.unclaimedPdcsByOperator,50),
    strictFinalOrdinalRefsAgainstUnclaimedPdcsByOperator:top(counters.unclaimedFinalOrdinalRefs,50),
    shortSuffixRefsAgainstUnclaimedPdcsByOperator:top(counters.unclaimedShortSuffixRefs,50),
    trimmedLongSuffixRefsAgainstUnclaimedPdcsByOperator:top(counters.trimmedLongSuffixRefs,50),
    trimmedLongSuffixMatchLengths:top(counters.trimmedLongSuffixLengths,50)
  },
  sampleUnmatched:unmatched
};
await fs.mkdir(OUT.split('/').slice(0,-1).join('/')||'.',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
