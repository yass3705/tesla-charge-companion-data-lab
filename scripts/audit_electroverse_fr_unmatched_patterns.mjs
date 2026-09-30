import fs from 'node:fs/promises';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const MANIFEST=CACHE+'/manifest.json';
const OUT=process.argv[2]||'reports/electroverse-fr-unmatched-patterns.json';

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
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const globalPdcOwners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;
  const set=globalPdcOwners.get(k)||new Set();set.add(String(m.irveStationId||m.electroverseLocationPk||''));globalPdcOwners.set(k,set);
}

const unmatched=[];
const counters={
  byNormLength:{},byRawShape:{},byOperator:{},byLocalPdcCount:{},
  uniqueLocalContainsRef:{},uniqueRefContainsLocalPdc:{},uniquePdcPayloadEqualsRef:{},
  uniqueLastTokenSuffix:{},uniqueFirstTokenSuffix:{},partialCommonPrefixTail:{}
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

    for(const e of row.tariff?.evses||[]){
      const raw=text(e?.physicalReference); if(!raw)continue; const k=norm(raw);
      if(local.includes(k))continue;
      const parents=local.filter(p=>k.startsWith(p)&&k.length>p.length&&/^\d{1,2}$/.test(k.slice(p.length)));
      if(parents.length===1||ordinalTargets.has(e)||genericTargets.has(e)||suffixTargets.has(e))continue;
      // Only the exact rejection family requested: no parent candidate at all.
      if(parents.length)continue;

      const operator=opOf(local[0]);
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

      if(unmatched.length<200)unmatched.push({
        locationPk:String(row.electroverseLocationPk),evsePk:e.pk??null,physicalReference:raw,
        normalized:k,operator,localPdcCount:local.length,localPdcs:localRaw.slice(0,30)
      });
    }
  }
}

const total=Object.values(counters.byNormLength).reduce((a,b)=>a+b,0);
const report={
  generatedAt:new Date().toISOString(),dataset:'electroverse-fr-unmatched-identity-pattern-audit',
  totalUnmatched:total,
  topOperators:top(counters.byOperator,30),
  normLength:top(counters.byNormLength,50),
  rawShape:top(counters.byRawShape,20),
  localPdcCount:top(counters.byLocalPdcCount,30),
  candidateDiagnostics:{
    uniqueLocalPdcContainsWholeRefByRefLength:top(counters.uniqueLocalContainsRef,50),
    uniqueRefContainsWholeLocalPdcByRefLength:top(counters.uniqueRefContainsLocalPdc,50),
    exactPdcPayloadAfterFirstEEqualsRefByRefLength:top(counters.uniquePdcPayloadEqualsRef,50),
    uniqueLastRawTokenMatchesPdcSuffixByTokenLength:top(counters.uniqueLastTokenSuffix,50),
    uniqueFirstRawTokenMatchesPdcSuffixByTokenLength:top(counters.uniqueFirstTokenSuffix,50),
    individualCommonPrefixTailHitByRefLength:top(counters.partialCommonPrefixTail,50)
  },
  sampleUnmatched:unmatched
};
await fs.mkdir(OUT.split('/').slice(0,-1).join('/')||'.',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
