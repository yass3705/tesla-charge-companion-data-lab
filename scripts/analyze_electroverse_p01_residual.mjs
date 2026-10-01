import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse/p01-residual-analysis.json';
const VALIDATED_OUT='data/platforms/electroverse/validated-mappings/p01-structured-residual.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const priceOnlySig=e=>JSON.stringify([...new Set((e?.connectors||[]).map(c=>JSON.stringify({
  isChargingFree:c?.isChargingFree??null,
  priceComponents:c?.priceComponents??null,
  complexPricingDetail:c?.complexPricingDetail??null
})))].sort());
const p01ParentBody=raw=>{
  const parts=String(raw||'').split('*').map(v=>v.trim()).filter(Boolean);
  if(parts.length!==6||parts[0].toUpperCase()!=='FR'||parts[1].toUpperCase()!=='P01')return null;
  return norm(parts[2]+parts[3]+parts[4]).replace(/^E/,'')||null;
};
const sourceSig=e=>JSON.stringify((e?.connectors||[]).map(c=>({
  kilowatts:c?.kilowatts??null,
  standard:c?.standard?.name??c?.standard??null,
  isChargingFree:c?.isChargingFree??null,
  priceComponents:c?.priceComponents??null,
  complexPricingDetail:c?.complexPricingDetail??null
})).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b))));
const opFromRef=raw=>{
  const s=String(raw??'').trim();
  const star=s.split('*').map(x=>x.trim()).filter(Boolean);
  if(star.length>=2 && /^FR$/i.test(star[0])) return star[1].toUpperCase();
  const n=norm(s);
  const m=n.match(/^FR([A-Z0-9]{1,8})E/);
  if(m)return m[1];
  if(/^MAT\d+/i.test(s))return 'MAT';
  if(/^B\d+/i.test(s))return 'B';
  if(/^\d+$/.test(s))return 'NUMERIC';
  return n.slice(0,12)||'MISSING';
};

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));

const oman=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedSourcePks=new Set(),publishedTargets=new Set();
for(const t of oman.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
  for(const o of tile.emspOffers||[]){
    for(const pk of o?.metadata?.electroverseEvsePks||[]) if(pk!=null)publishedSourcePks.add(String(pk));
    if(o?.metadata?.electroverseEvsePk!=null) publishedSourcePks.add(String(o.metadata.electroverseEvsePk));
    for(const id of o.evseIds||[])publishedTargets.add(norm(id));
  }
}

const owners=new Map();
for(const m of mapping.mappings||[]) for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;
  const s=owners.get(k)||new Set();s.add(String(m.irveStationId??''));owners.set(k,s);
}

const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const donorsByRef=new Map();
const donorsByParent=new Map();
const donorsByLocation=new Map();
for(const sh of cman.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    for(const e of row?.tariff?.evses||[]){
      const rk=norm(e?.physicalReference);
      if(!rk||(e?.connectors||[]).length===0)continue;
      const donor={
        electroverseLocationPk:String(row.electroverseLocationPk),
        electroverseEvsePk:e.pk,
        physicalReference:String(e.physicalReference),
        sourceSignature:sourceSig(e),
        priceOnlySignature:priceOnlySig(e)
      };
      const a=donorsByRef.get(rk)||[];a.push(donor);donorsByRef.set(rk,a);
      const pb=p01ParentBody(e.physicalReference);
      if(pb){const b=donorsByParent.get(pb)||[];b.push(donor);donorsByParent.set(pb,b);}
      const lk=String(row.electroverseLocationPk);
      const c=donorsByLocation.get(lk)||[];c.push(donor);donorsByLocation.set(lk,c);
    }
  }
}
const groups=[];
const structuredCandidates=[];
let residual=0,locations=0;
for(const sh of cman.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const es=(row?.tariff?.evses||[]).filter(e=>{
      if(e?.pk==null||publishedSourcePks.has(String(e.pk)))return false;
      return opFromRef(e?.physicalReference)==='P01';
    });
    if(!es.length)continue;
    residual+=es.length;locations++;
    const m=byPk.get(String(row.electroverseLocationPk));
    const local=[...new Set((m?.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const available=local.filter(p=>!publishedTargets.has(p));
    const refs=es.map(e=>({e,k:norm(e.physicalReference),raw:String(e.physicalReference)}));
    const evseBody=v=>{
      const n=norm(v),mm=n.match(/^FR[A-Z0-9]{1,8}E(.+)$/);
      return mm?mm[1]:null;
    };
    const structuredParent=[];
    for(const x of refs){
      const parts=String(x.raw||'').split('*').map(v=>v.trim()).filter(Boolean);
      // Expected P01 child reference: FR*P01*E<zone>*<station>*<point>*<connector>.
      if(parts.length!==6||parts[0].toUpperCase()!=='FR'||parts[1].toUpperCase()!=='P01')continue;
      const parentBody=norm(parts[2]+parts[3]+parts[4]).replace(/^E/,'');
      if(!parentBody)continue;
      const matches=available.filter(p=>{
        const pb=evseBody(p);
        return pb===parentBody&&(owners.get(p)?.size||0)===1;
      });
      if(matches.length===1)structuredParent.push({
        evsePk:x.e.pk,target:matches[0],raw:x.raw,
        parentBody,connectorOrdinal:parts[5]
      });
    }
    const structuredTargetCounts=new Map();
    for(const x of structuredParent){
      structuredTargetCounts.set(x.target,(structuredTargetCounts.get(x.target)||0)+1);
      structuredCandidates.push({
        electroverseLocationPk:String(row.electroverseLocationPk),
        irveStationId:m?.irveStationId??row.irveStationId??null,
        electroverseEvsePk:x.evsePk,
        targetPdc:x.target,
        physicalReference:x.raw,
        parentBody:x.parentBody,
        connectorOrdinal:x.connectorOrdinal,
        sourceSignature:sourceSig(x.e)
      });
    }

    const crossOperatorParent=[];
    for(const x of refs){
      const sb=evseBody(x.raw);
      if(!sb)continue;
      const matches=available.filter(p=>{
        const pb=evseBody(p);
        if(!pb||!sb.startsWith(pb)||sb.length<=pb.length)return false;
        const suffix=sb.slice(pb.length);
        return /^\d{1,2}$/.test(suffix)&&(owners.get(p)?.size||0)===1;
      });
      if(matches.length===1)crossOperatorParent.push({evsePk:x.e.pk,target:matches[0],raw:x.raw});
    }

    const exactSuffix=[];
    for(const x of refs){
      const matches=available.filter(p=>x.k.length>=4&&p.endsWith(x.k)&&(owners.get(p)?.size||0)===1);
      if(matches.length===1)exactSuffix.push({evsePk:x.e.pk,target:matches[0],raw:x.raw});
    }
    const exactSuffixUniqueTargets=new Set(exactSuffix.map(x=>x.target)).size===exactSuffix.length;

    let commonPrefix='';
    if(available.length){
      commonPrefix=available[0];
      for(const p of available.slice(1)){
        let i=0;while(i<commonPrefix.length&&i<p.length&&commonPrefix[i]===p[i])i++;
        commonPrefix=commonPrefix.slice(0,i);if(!commonPrefix)break;
      }
    }
    const tailMap=new Map();let tailsUnique=true;
    for(const p of available){
      const tail=p.slice(commonPrefix.length);
      if(!tail||tailMap.has(tail)){tailsUnique=false;break;}
      tailMap.set(tail,p);
    }
    const tailMatches=refs.map(x=>({evsePk:x.e.pk,target:tailMap.get(x.k)||null,raw:x.raw}));
    const commonTailBijection=commonPrefix.length>=4&&tailsUnique&&
      tailMatches.every(x=>x.target&&(owners.get(x.target)?.size||0)===1)&&
      new Set(tailMatches.map(x=>x.target)).size===tailMatches.length;

    const homogeneousPricing=new Set(es.map(e=>JSON.stringify((e.connectors||[]).map(c=>({
      isChargingFree:c?.isChargingFree??null,
      priceComponents:c?.priceComponents??null,
      complexPricingDetail:c?.complexPricingDetail??null
    }))))).size===1;
    const connectorCounts=new Set(es.map(e=>(e.connectors||[]).length));
    const exactSetSafe=es.length===available.length&&available.length>0&&
      available.every(p=>(owners.get(p)?.size||0)===1)&&homogeneousPricing;

    let mode='none';
    if(exactSuffix.length===es.length&&exactSuffixUniqueTargets)mode='unique_suffix_bijection';
    else if(commonTailBijection)mode='common_tail_bijection';
    else if(exactSetSafe)mode=connectorCounts.size===1?'homogeneous_exact_set':'price_only_exact_set';

    groups.push({
      electroverseLocationPk:String(row.electroverseLocationPk),
      irveStationId:m?.irveStationId??row.irveStationId??null,
      residualCount:es.length,
      availablePdcCount:available.length,
      localPdcSample:available.slice(0,30),
      mode,
      homogeneousPricing,
      uniformConnectorCount:connectorCounts.size===1,
      commonPrefix:commonPrefix||null,
      structuredParentCount:structuredParent.length,
      structuredParentUniqueTargets:new Set(structuredParent.map(x=>x.target)).size,
      structuredParentAllSourcesMatched:structuredParent.length===es.length,
      structuredParentTargetMultiplicity:Object.fromEntries([...structuredTargetCounts.entries()].sort()),
      structuredParent:structuredParent.slice(0,120),
      crossOperatorParentCount:crossOperatorParent.length,
      crossOperatorParentUniqueTargets:new Set(crossOperatorParent.map(x=>x.target)).size,
      crossOperatorParent:crossOperatorParent.slice(0,80),
      refs:refs.slice(0,20).map(x=>({
        evsePk:x.e.pk,
        physicalReference:x.raw,
        connectorCount:(x.e.connectors||[]).length,
        connectors:(x.e.connectors||[]).map(c=>({
          kilowatts:c?.kilowatts??null,
          standard:c?.standard?.name??c?.standard??null
        }))
      })),
      exactSuffix:exactSuffix.slice(0,20),
      commonTailMappings:commonTailBijection?tailMatches.slice(0,20):[]
    });
  }
}
const byMode={};
for(const g of groups)byMode[g.mode]=(byMode[g.mode]||0)+g.residualCount;
const byTarget=new Map();
for(const x of structuredCandidates){
  const a=byTarget.get(x.target)||[];a.push(x);byTarget.set(x.target,a);
}
const validatedMappings=[];
const conflictedTargets=[];
let suppressedExactDuplicates=0;
for(const [target,candidates] of byTarget){
  const byRaw=new Map();
  for(const x of candidates){
    const rk=norm(x.physicalReference);
    const a=byRaw.get(rk)||[];a.push(x);byRaw.set(rk,a);
  }
  let unsafe=false;
  for(const [raw,rows] of byRaw){
    const sigs=new Set(rows.map(x=>x.sourceSignature));
    if(sigs.size>1){
      unsafe=true;
      conflictedTargets.push({target,physicalReference:raw,sourceEvsePks:rows.map(x=>x.electroverseEvsePk),reason:'same_child_reference_conflicting_tariff_or_technical_profile'});
    }
  }
  if(unsafe)continue;
  for(const rows of byRaw.values()){
    rows.sort((a,b)=>Number(a.electroverseEvsePk)-Number(b.electroverseEvsePk));
    validatedMappings.push(rows[0]);
    suppressedExactDuplicates+=Math.max(0,rows.length-1);
  }
}
const donorRecoverableMappings=[];
const donorAmbiguities=[];
for(const x of validatedMappings){
  const donors=(donorsByRef.get(norm(x.physicalReference))||[])
    .filter(d=>String(d.electroverseEvsePk)!==String(x.electroverseEvsePk));
  if(!donors.length)continue;
  const sigs=new Set(donors.map(d=>d.sourceSignature));
  if(sigs.size!==1){
    donorAmbiguities.push({
      targetPdc:x.targetPdc,
      physicalReference:x.physicalReference,
      residualEvsePk:x.electroverseEvsePk,
      donorEvsePks:donors.map(d=>d.electroverseEvsePk),
      reason:'exact_physical_reference_has_conflicting_donor_profiles'
    });
    continue;
  }
  donors.sort((a,b)=>Number(a.electroverseEvsePk)-Number(b.electroverseEvsePk));
  const donor=donors[0];
  donorRecoverableMappings.push({
    ...x,
    recoveryMode:'exact_physical_reference_donor',
    donorElectroverseLocationPk:donor.electroverseLocationPk,
    donorElectroverseEvsePk:donor.electroverseEvsePk,
    donorSourceSignature:donor.sourceSignature,
    donorCandidateCount:donors.length
  });
}

const exactRecoveredKeys=new Set(donorRecoverableMappings.map(x=>String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk)));
const sameParentHomogeneousCandidates=[];
const stationHomogeneousCandidates=[];
for(const x of validatedMappings){
  const key=String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk);
  if(exactRecoveredKeys.has(key))continue;
  const parentDonors=donorsByParent.get(x.parentBody)||[];
  const parentPriceSigs=new Set(parentDonors.map(d=>d.priceOnlySignature).filter(Boolean));
  if(parentDonors.length&&parentPriceSigs.size===1){
    const donor=[...parentDonors].sort((a,b)=>Number(a.electroverseEvsePk)-Number(b.electroverseEvsePk))[0];
    sameParentHomogeneousCandidates.push({
      ...x,recoveryMode:'same_parent_homogeneous_price_only',
      donorElectroverseLocationPk:donor.electroverseLocationPk,
      donorElectroverseEvsePk:donor.electroverseEvsePk,
      donorPriceOnlySignature:donor.priceOnlySignature,
      donorCandidateCount:parentDonors.length
    });
    continue;
  }
  const stationDonors=donorsByLocation.get(String(x.electroverseLocationPk))||[];
  const stationPriceSigs=new Set(stationDonors.map(d=>d.priceOnlySignature).filter(Boolean));
  if(stationDonors.length&&stationPriceSigs.size===1){
    const donor=[...stationDonors].sort((a,b)=>Number(a.electroverseEvsePk)-Number(b.electroverseEvsePk))[0];
    stationHomogeneousCandidates.push({
      ...x,recoveryMode:'station_homogeneous_price_only',
      donorElectroverseLocationPk:donor.electroverseLocationPk,
      donorElectroverseEvsePk:donor.electroverseEvsePk,
      donorPriceOnlySignature:donor.priceOnlySignature,
      donorCandidateCount:stationDonors.length
    });
  }
}

const out={
 schemaVersion:1,generatedAt:new Date().toISOString(),
 residualSourceEvses:residual,affectedLocations:locations,byMode,
 safelyRecoverableSourceEvses:Object.entries(byMode).filter(([k])=>k!=='none').reduce((n,[,v])=>n+v,0),
 structuredCandidateSourceEvses:structuredCandidates.length,
 structuredValidatedChildRefs:validatedMappings.length,
 structuredSuppressedExactDuplicates:suppressedExactDuplicates,
 structuredConflictedTargets:conflictedTargets.length,
 exactReferenceDonorRecoverableSourceEvses:donorRecoverableMappings.length,
 exactReferenceDonorAmbiguities:donorAmbiguities.length,
 sameParentHomogeneousPriceOnlyCandidates:sameParentHomogeneousCandidates.length,
 stationHomogeneousPriceOnlyCandidates:stationHomogeneousCandidates.length,
 safeGroups:groups.filter(g=>g.mode!=='none').sort((a,b)=>b.residualCount-a.residualCount).slice(0,200),
 unresolvedSamples:groups.filter(g=>g.mode==='none').sort((a,b)=>b.residualCount-a.residualCount).slice(0,100),
 policy:'Diagnostic only. P01 bucket uses exact structured parent reconstruction. Multiple distinct child references may map to one national parent PDC. Exact duplicate child references are deduplicated only when tariff and technical profiles are identical; conflicting duplicates fail closed. No proximity inference.'
};
const validated={
 schemaVersion:1,
 generatedAt:out.generatedAt,
 dataset:'electroverse-france-p01-structured-residual-mappings',
 count:donorRecoverableMappings.length,
 identityCount:validatedMappings.length,
 policy:'Exact P01 child-to-parent identities only. Multiple distinct child references may share one globally unique local national parent PDC. Exact duplicate child references are deduplicated only when tariff and technical profiles are identical; any conflicting duplicate makes that parent fail closed. No proximity inference.',
 mappings:donorRecoverableMappings,
 identityMappings:validatedMappings,
 conflictedTargets,
 donorAmbiguities,
 sameParentHomogeneousCandidates,
 stationHomogeneousCandidates
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.mkdir('data/platforms/electroverse/validated-mappings',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
await fs.writeFile(VALIDATED_OUT,JSON.stringify(validated,null,2)+'\n');
console.log(JSON.stringify({report:out,identityValidatedCount:validatedMappings.length,donorRecoverableCount:donorRecoverableMappings.length,sameParentHomogeneousCandidates:sameParentHomogeneousCandidates.length,stationHomogeneousCandidates:stationHomogeneousCandidates.length},null,2));

// structured P01 residual diagnostic 2026-10-01
