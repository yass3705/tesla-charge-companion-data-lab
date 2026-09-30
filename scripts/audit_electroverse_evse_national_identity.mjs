import fs from 'node:fs/promises';

const MAP='data/electroverse/irve_location_mapping.json';
const MAN='data/electroverse/tariff_cache/manifest.json';
const OUT='reports/electroverse/evse-national-identity-audit.json';

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const manifest=JSON.parse(await fs.readFile(MAN,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));

let locations=0,evses=0,physicalRefs=0,currentExact=0,unionExact=0,rowOnlyRecovered=0;
let mappingEmptyRowNonEmptyLocations=0,mappingEmptyRowNonEmptyEvses=0;
let globallyUniqueViaUnion=0,globallyAmbiguousViaUnion=0;
let uniqueLocalParentPrefix=0,ambiguousLocalParentPrefix=0;
let globalExactOutsideLocal=0,globalParentUniqueAny=0,globalParentUniqueOutsideLocal=0,globalParentAmbiguous=0;
const suffixCounts={};
const unmatchedSamples=[], recoveredSamples=[], parentPrefixSamples=[], globalParentSamples=[];

const rows=[];
const parentGroups=new Map();
for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile('data/electroverse/tariff_cache/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})) rows.push(row);
}

const currentOwners=new Map(), unionOwners=new Map();
function addOwner(map,pdc,station){
  const k=norm(pdc); if(!k)return;
  const s=map.get(k)||new Set(); s.add(String(station??'')); map.set(k,s);
}
function rawPricingSig(e){
  return JSON.stringify((e?.connectors||[]).map(c=>({
    isChargingFree:c?.isChargingFree??null,
    priceComponents:c?.priceComponents??null,
    complexPricingDetail:c?.complexPricingDetail??null
  })));
}
for(const m of mapping.mappings||[]) for(const p of m.irvePdcIds||[]) addOwner(currentOwners,p,m.irveStationId);
for(const row of rows){
  const m=byPk.get(String(row.electroverseLocationPk));
  const station=m?.irveStationId??row.irveStationId??row.electroverseLocationPk;
  for(const p of m?.irvePdcIds||[]) addOwner(unionOwners,p,station);
  for(const p of row.irvePdcIds||[]) addOwner(unionOwners,p,station);
}

for(const row of rows){
  locations++;
  const m=byPk.get(String(row.electroverseLocationPk));
  const mapIds=(m?.irvePdcIds||[]).map(norm).filter(Boolean);
  const rowIds=(row.irvePdcIds||[]).map(norm).filter(Boolean);
  const currentLocal=new Set(mapIds.length?mapIds:rowIds);
  const unionLocal=new Set([...mapIds,...rowIds]);
  if(mapIds.length===0 && rowIds.length>0) mappingEmptyRowNonEmptyLocations++;
  for(const e of row.tariff?.evses||[]){
    evses++;
    const pr=String(e?.physicalReference??'').trim();
    if(!pr)continue;
    physicalRefs++;
    const k=norm(pr);
    const curOwners=currentOwners.get(k);
    const uOwners=unionOwners.get(k);
    const cur=currentLocal.has(k)&&curOwners?.size===1;
    const uni=unionLocal.has(k)&&uOwners?.size===1;
    if(cur) currentExact++;
    if(uni) unionExact++;
    if(uOwners?.size===1) {
      globallyUniqueViaUnion++;
      if(!unionLocal.has(k)) globalExactOutsideLocal++;
    }
    if(uOwners?.size>1) globallyAmbiguousViaUnion++;
    if(mapIds.length===0 && rowIds.length>0) mappingEmptyRowNonEmptyEvses++;
    if(!cur && uni){
      rowOnlyRecovered++;
      if(recoveredSamples.length<50) recoveredSamples.push({
        pk:row.electroverseLocationPk,
        irveStationId:m?.irveStationId??row.irveStationId,
        physicalReference:pr,
        evsePk:e.pk,
        mappingPdcCount:mapIds.length,
        rowPdcCount:rowIds.length
      });
    } else if(!uni) {
      const rawLocal=[...(m?.irvePdcIds||[]),...(row.irvePdcIds||[])];
      const parentCandidates=[...new Map(rawLocal.map(p=>[norm(p),p]).filter(([p])=>p && k.startsWith(p) && k.length>p.length)).values()];
      const globalParents=[];
      for(const n of [1,2]){
        if(k.length<=n)continue;
        const suffix=k.slice(-n);
        if(!/^\d{1,2}$/.test(suffix))continue;
        const parent=k.slice(0,-n);
        const owners=currentOwners.get(parent);
        if(owners?.size===1) globalParents.push({parent,suffix,owner:[...owners][0]});
      }
      const uniqueGlobalParents=[...new Map(globalParents.map(x=>[x.parent,x])).values()];
      if(uniqueGlobalParents.length===1){
        globalParentUniqueAny++;
        const gp=uniqueGlobalParents[0];
        const localHas=[...rawLocal].some(p=>norm(p)===gp.parent);
        if(!localHas) globalParentUniqueOutsideLocal++;
        if(globalParentSamples.length<100) globalParentSamples.push({
          pk:row.electroverseLocationPk,physicalReference:pr,evsePk:e.pk,
          parentNorm:gp.parent,suffix:gp.suffix,ownerStationId:gp.owner,localHas
        });
      } else if(uniqueGlobalParents.length>1) globalParentAmbiguous++;
      if(parentCandidates.length===1){
        uniqueLocalParentPrefix++;
        const parent=norm(parentCandidates[0]);
        const suffix=k.slice(parent.length);
        suffixCounts[suffix]=(suffixCounts[suffix]||0)+1;
        const parentPdc=parentCandidates[0];
        const parentNorm=norm(parentPdc);
        const ownerCount=currentOwners.get(parentNorm)?.size||0;
        const gk=String(row.electroverseLocationPk)+'|'+parentNorm;
        const g=parentGroups.get(gk)||{pk:String(row.electroverseLocationPk),parentPdc,parentNorm,ownerCount,children:[],pricingSigs:new Set()};
        g.children.push({physicalReference:pr,evsePk:e.pk,suffix});
        g.pricingSigs.add(rawPricingSig(e));
        parentGroups.set(gk,g);
        if(parentPrefixSamples.length<100) parentPrefixSamples.push({
          pk:row.electroverseLocationPk,
          irveStationId:m?.irveStationId??row.irveStationId,
          physicalReference:pr,
          parentPdc,
          parentOwnerCount:ownerCount,
          suffix,
          evsePk:e.pk
        });
      } else if(parentCandidates.length>1) ambiguousLocalParentPrefix++;
      if(unmatchedSamples.length<100) unmatchedSamples.push({
        pk:row.electroverseLocationPk,
        irveStationId:m?.irveStationId??row.irveStationId,
        physicalReference:pr,
        evsePk:e.pk,
        mappingPdcCount:mapIds.length,
        rowPdcCount:rowIds.length,
        localPdcIds:rawLocal,
        parentCandidates,
        unionOwners:uOwners?[...uOwners]:[]
      });
    }
  }
}

let parentGroupsUniqueOwner=0,parentGroupsHomogeneousPricing=0,parentGroupsSafe=0,parentChildRefsSafe=0,parentGroupsHeterogeneousPricing=0,parentGroupsNonUniqueOwner=0;
const parentGroupSamples=[];
for(const g of parentGroups.values()){
  const uniqueOwner=g.ownerCount===1;
  const homogeneous=g.pricingSigs.size===1;
  if(uniqueOwner) parentGroupsUniqueOwner++; else parentGroupsNonUniqueOwner++;
  if(homogeneous) parentGroupsHomogeneousPricing++; else parentGroupsHeterogeneousPricing++;
  if(uniqueOwner&&homogeneous){parentGroupsSafe++;parentChildRefsSafe+=g.children.length;}
  if(parentGroupSamples.length<100) parentGroupSamples.push({
    pk:g.pk,parentPdc:g.parentPdc,ownerCount:g.ownerCount,
    childCount:g.children.length,pricingVariantCount:g.pricingSigs.size,
    safe:uniqueOwner&&homogeneous,children:g.children.slice(0,10)
  });
}

const out={
  generatedAt:new Date().toISOString(),
  locations,evses,physicalRefs,
  currentExactUniqueNationalPdcMatches:currentExact,
  unionExactUniqueNationalPdcMatches:unionExact,
  rowOnlyRecovered,
  deltaExact:unionExact-currentExact,
  currentExactPct:physicalRefs?Number((100*currentExact/physicalRefs).toFixed(3)):0,
  unionExactPct:physicalRefs?Number((100*unionExact/physicalRefs).toFixed(3)):0,
  mappingEmptyRowNonEmptyLocations,
  mappingEmptyRowNonEmptyEvses,
  globallyUniqueViaUnion,
  globallyAmbiguousViaUnion,
  globalExactOutsideLocal,
  globalParentUniqueAny,
  globalParentUniqueOutsideLocal,
  globalParentAmbiguous,
  uniqueLocalParentPrefix,
  ambiguousLocalParentPrefix,
  parentGroupsTotal:parentGroups.size,
  parentGroupsUniqueOwner,
  parentGroupsNonUniqueOwner,
  parentGroupsHomogeneousPricing,
  parentGroupsHeterogeneousPricing,
  parentGroupsSafe,
  parentChildRefsSafe,
  suffixCounts:Object.fromEntries(Object.entries(suffixCounts).sort((a,b)=>b[1]-a[1]).slice(0,50)),
  policy:'Diagnostic only. Exact normalized physicalReference against union of mapping + row IRVE PDC IDs; no proximity inference.',
  recoveredSamples,
  parentPrefixSamples,
  parentGroupSamples,
  globalParentSamples,
  unmatchedSamples
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
