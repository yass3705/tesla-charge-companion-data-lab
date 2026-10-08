import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const base='data/platforms/electra/france/';
const norm=x=>String(x??'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const load=async p=>JSON.parse(zlib.gunzipSync(await fs.readFile(p)).toString('utf8'));
const [residual,source,manifest]=await Promise.all([load(base+'residuals.json.gz'),load(base+'source-locations.json.gz'),fs.readFile(base+'manifest.json','utf8').then(JSON.parse)]);
const locById=new Map((source.locations||[]).map(x=>[String(x.id),x]));
const national=await load('data/national/france-irve-static-v9/all.json.gz');
const powerByEvse=new Map();
for(const row of national)for(const cfg of row?.[8]||[])for(const pdc of cfg?.[6]||[]){
 const k=norm(pdc),kw=Number(cfg?.[3]);if(!Number.isFinite(kw)||kw<=0)continue;
 const prev=powerByEvse.get(k);powerByEvse.set(k,prev==null?kw:prev===kw?kw:null);
}
const tariffPowerScope=t=>{
 const restrictions=(t.elements||[]).map(e=>e?.restrictions||{});
 if(!restrictions.length||restrictions.some(r=>r.minPower==null&&r.maxPower==null))return null;
 const lo=Math.max(...restrictions.map(r=>r.minPower==null?0:Number(r.minPower)));
 const hi=Math.min(...restrictions.map(r=>r.maxPower==null?Infinity:Number(r.maxPower)));
 return lo<=hi?{lo,hi}:null;
};
const count=(map,key)=>map[key]=(map[key]||0)+1;
const compType=x=>String(x?.type||'MISSING').toUpperCase();
const supported=new Set(['ENERGY','TIME','FLAT','PARKING_TIME','CONGESTION_TIME']);
const cases=[],blockedBy={},components={},restrictions={},heteroReasons={};
for(const row of residual.locations||[]){
  if(!['unsupported_tariff','heterogeneous_location_tariffs','tariff_attribution_missing_evse_evidence','same_power_tariff_assignment_ambiguous'].includes(row.reason))continue;
  const loc=locById.get(String(row.electraLocationId));
  const tariff=loc?.chargeTariffs||[],issues=new Set(),types=new Set(),restrictionFields=new Set(),tariffSignatures=new Set(),tariffDetails=[];
  for(const t of tariff){
    const sections=[],tsign=[];
    for(const e of t.elements||[]){
      const rr=e.restrictions||{},pcs=e.priceComponents||[];
      for(const [k,v] of Object.entries(rr))if(v!=null&&v!==''&&!(Array.isArray(v)&&!v.length)){restrictionFields.add(k);count(restrictions,k);}
      const min=Number(rr.minDuration);
      const dims=[];
      for(const pc of pcs){
        const k=compType(pc),n=Number(pc.price);types.add(k);count(components,k);
        if(!supported.has(k))issues.add('unknown_component:'+k);
        if(!Number.isFinite(n)||n<0)issues.add('invalid_component_price');
        if(k==='CONGESTION_TIME'&&Number.isFinite(min)&&min>0)issues.add('congestion_duration_band_supported');
        dims.push([k,n]);
      }
      if(!pcs.length)issues.add('empty_tariff_element');
      const s=JSON.stringify({r:rr,p:dims});sections.push(s);tsign.push(s);
    }
    if(!sections.length)issues.add('tariff_without_elements');
    const sig=JSON.stringify(tsign);
    tariffSignatures.add(sig);
    tariffDetails.push({tariffId:t.chargeTariffId||t.id||null,currency:t.currency,
      sections:tsign.slice(0,8),components:[...types]});
  }
  if(row.reason==='unsupported_tariff'&&issues.size===0)issues.add('other_compiler_restriction');
  if(['heterogeneous_location_tariffs','tariff_attribution_missing_evse_evidence','same_power_tariff_assignment_ambiguous'].includes(row.reason)){
    if(tariff.length>1&&tariffSignatures.size>1)count(heteroReasons,'different_tariff_rules_at_location');
    else if(tariff.length>1)count(heteroReasons,'same_raw_tariff_different_compilation');
    else count(heteroReasons,'single_tariff_compilation_mismatch');
  }
  for(const issue of issues)if(issue!=='congestion_duration_band_supported')count(blockedBy,issue);
  const knownPowerGroups={};
  for(const id of (loc?.evses||[]).map(e=>e.evseId).filter(Boolean)){
    const kw=powerByEvse.get(norm(id));const label=kw==null?'unknown':String(kw);
    (knownPowerGroups[label]??=[]).push(id);
  }
  let provenSamePowerConflict=false,missingPowerEvidence=false;
  const scopes=tariff.map(tariffPowerScope);
  if(scopes.some(x=>!x))missingPowerEvidence=true;
  for(const [kwLabel,evseIds] of Object.entries(knownPowerGroups)){
    if(kwLabel==='unknown'){missingPowerEvidence=true;continue;}
    const power=Number(kwLabel),hits=scopes.map((v,i)=>({v,i})).filter(x=>x.v&&power>=x.v.lo&&power<=x.v.hi);
    const distinct=new Set(hits.map(x=>[...tariffSignatures][x.i]));
    if(evseIds.length>=2&&distinct.size>1)provenSamePowerConflict=true;
  }
  // No EVSE -> tariff linkage is exposed by the location-based source.
  // Do not count different station tariffs as a confirmed same-power issue.
  const verdict=provenSamePowerConflict?'same_power_tariff_conflict_evidenced':
      missingPowerEvidence?'tariff_evse_attribution_not_proven':'power_scoped_tariffs_pending_final_validation';
  const item={locationId:String(row.electraLocationId),name:row.name,cpo:row.cpo,powerGroups:knownPowerGroups,samePowerVerdict:verdict,provenSamePowerConflict,missingPowerEvidence,
    reason:row.reason,evseCount:loc?.evses?.length??row.evses?.length??0,
    tariffCount:tariff.length,tariffSignatureCount:tariffSignatures.size,
    components:[...types].sort(),restrictionFields:[...restrictionFields].sort(),issues:[...issues],
    evseIds:(loc?.evses||row.evses||[]).map(e=>e.evseId).filter(Boolean).slice(0,12),
    examples:tariffDetails.slice(0,3)};
  cases.push(item);
}
const summary={schemaVersion:1,generatedAt:new Date().toISOString(),sourceGeneratedAt:manifest.generatedAt,
  counts:{total:cases.length,unsupported:cases.filter(x=>x.reason==='unsupported_tariff').length,
    heterogeneous:cases.filter(x=>['heterogeneous_location_tariffs','tariff_attribution_missing_evse_evidence','same_power_tariff_assignment_ambiguous'].includes(x.reason)).length,
    evidenceRequired:cases.filter(x=>x.missingPowerEvidence).length,
    trueSamePowerConflicts:cases.filter(x=>x.provenSamePowerConflict).length,
    congestionDurationSupported:cases.filter(x=>x.issues.includes('congestion_duration_band_supported')).length},
  unresolvedKinds:blockedBy,componentTypes:components,restrictionFields:restrictions,
  heterogeneousPatterns:heteroReasons,
  sampleUnsupported:cases.filter(x=>x.reason==='unsupported_tariff').slice(0,30),
  sampleHeterogeneous:cases.filter(x=>x.reason==='heterogeneous_location_tariffs').slice(0,20),
  caseArchive:'reports/france/irve/electra-pricing-residual-cases-2026-10-08.json.gz',
  decisionPolicy:'Tariffs belong to exact EVSE; different prices across distinct powers in the same station are expected. Count a same-power conflict only where explicit EVSE-to-tariff evidence proves it. SOC80 congestion and explicit duration bounds are supported; retain fail-closed unknown associations.'
};
await fs.mkdir('reports/france/irve',{recursive:true});
await fs.writeFile('reports/france/irve/electra-pricing-residual-audit-2026-10-08.json',JSON.stringify(summary,null,2)+'\n');
await fs.writeFile(summary.caseArchive,zlib.gzipSync(Buffer.from(JSON.stringify({schemaVersion:1,cases})),{level:9}));
console.log(JSON.stringify({generatedAt:summary.generatedAt,counts:summary.counts,unresolvedKinds:summary.unresolvedKinds,
 heterogeneousPatterns:heteroReasons,componentTypes:components,restrictionFields:restrictions,
 sampleUnsupported:summary.sampleUnsupported.slice(0,5).map(x=>({name:x.name,cpo:x.cpo,issues:x.issues,components:x.components,restrictions:x.restrictionFields}))}));
