import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const base='data/platforms/electra/france/';
const load=async p=>JSON.parse(zlib.gunzipSync(await fs.readFile(p)).toString('utf8'));
const [residual,source,manifest]=await Promise.all([load(base+'residuals.json.gz'),load(base+'source-locations.json.gz'),fs.readFile(base+'manifest.json','utf8').then(JSON.parse)]);
const locById=new Map((source.locations||[]).map(x=>[String(x.id),x]));
const count=(map,key)=>map[key]=(map[key]||0)+1;
const compType=x=>String(x?.type||'MISSING').toUpperCase();
const supported=new Set(['ENERGY','TIME','FLAT','PARKING_TIME','CONGESTION_TIME']);
const cases=[],blockedBy={},components={},restrictions={},heteroReasons={};
for(const row of residual.locations||[]){
  if(!['unsupported_tariff','heterogeneous_location_tariffs'].includes(row.reason))continue;
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
        if(k==='CONGESTION_TIME'&&Number.isFinite(min)&&min>0)issues.add('congestion_with_min_duration');
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
  if(row.reason==='heterogeneous_location_tariffs'){
    if(tariff.length>1&&tariffSignatures.size>1)count(heteroReasons,'different_tariff_rules_at_location');
    else if(tariff.length>1)count(heteroReasons,'same_raw_tariff_different_compilation');
    else count(heteroReasons,'single_tariff_compilation_mismatch');
  }
  for(const issue of issues)count(blockedBy,issue);
  const item={locationId:String(row.electraLocationId),name:row.name,cpo:row.cpo,
    reason:row.reason,evseCount:loc?.evses?.length??row.evses?.length??0,
    tariffCount:tariff.length,tariffSignatureCount:tariffSignatures.size,
    components:[...types].sort(),restrictionFields:[...restrictionFields].sort(),issues:[...issues],
    evseIds:(loc?.evses||row.evses||[]).map(e=>e.evseId).filter(Boolean).slice(0,12),
    examples:tariffDetails.slice(0,3)};
  cases.push(item);
}
const summary={schemaVersion:1,generatedAt:new Date().toISOString(),sourceGeneratedAt:manifest.generatedAt,
  counts:{total:cases.length,unsupported:cases.filter(x=>x.reason==='unsupported_tariff').length,
    heterogeneous:cases.filter(x=>x.reason==='heterogeneous_location_tariffs').length},
  unresolvedKinds:blockedBy,componentTypes:components,restrictionFields:restrictions,
  heterogeneousPatterns:heteroReasons,
  sampleUnsupported:cases.filter(x=>x.reason==='unsupported_tariff').slice(0,30),
  sampleHeterogeneous:cases.filter(x=>x.reason==='heterogeneous_location_tariffs').slice(0,20),
  caseArchive:'reports/france/irve/electra-pricing-residual-cases-2026-10-08.json.gz',
  decisionPolicy:'Do not broadcast a heterogeneous station tariff to its EVSEs without an authoritative EVSE-to-tariff assignment. Preserve all source stations and tariffs.'
};
await fs.mkdir('reports/france/irve',{recursive:true});
await fs.writeFile('reports/france/irve/electra-pricing-residual-audit-2026-10-08.json',JSON.stringify(summary,null,2)+'\n');
await fs.writeFile(summary.caseArchive,zlib.gzipSync(Buffer.from(JSON.stringify({schemaVersion:1,cases})),{level:9}));
console.log(JSON.stringify({generatedAt:summary.generatedAt,counts:summary.counts,unresolvedKinds:summary.unresolvedKinds,
 heterogeneousPatterns:heteroReasons,componentTypes:components,restrictionFields:restrictions,
 sampleUnsupported:summary.sampleUnsupported.slice(0,5).map(x=>({name:x.name,cpo:x.cpo,issues:x.issues,components:x.components,restrictions:x.restrictionFields}))}));
