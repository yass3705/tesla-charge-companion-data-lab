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
const unmatchedSamples=[], recoveredSamples=[];

const rows=[];
for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile('data/electroverse/tariff_cache/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})) rows.push(row);
}

const currentOwners=new Map(), unionOwners=new Map();
function addOwner(map,pdc,station){
  const k=norm(pdc); if(!k)return;
  const s=map.get(k)||new Set(); s.add(String(station??'')); map.set(k,s);
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
    if(uOwners?.size===1) globallyUniqueViaUnion++;
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
    } else if(!uni && unmatchedSamples.length<100){
      unmatchedSamples.push({
        pk:row.electroverseLocationPk,
        irveStationId:m?.irveStationId??row.irveStationId,
        physicalReference:pr,
        evsePk:e.pk,
        mappingPdcCount:mapIds.length,
        rowPdcCount:rowIds.length,
        unionOwners:uOwners?[...uOwners]:[]
      });
    }
  }
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
  policy:'Diagnostic only. Exact normalized physicalReference against union of mapping + row IRVE PDC IDs; no proximity inference.',
  recoveredSamples,
  unmatchedSamples
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
