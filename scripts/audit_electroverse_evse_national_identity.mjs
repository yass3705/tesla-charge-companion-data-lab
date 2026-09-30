import fs from 'node:fs/promises';

const MAP='data/electroverse/irve_location_mapping.json';
const MAN='data/electroverse/tariff_cache/manifest.json';
const OUT='reports/electroverse/evse-national-identity-audit.json';

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const manifest=JSON.parse(await fs.readFile(MAN,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));

let locations=0,evses=0,physicalRefs=0,exact=0,exactLocations=0,ambiguousRefs=0;
const unmatchedSamples=[], matchedSamples=[];
const globalPdcOwners=new Map();
for(const m of mapping.mappings||[]) for(const p of m.irvePdcIds||[]){
  const k=norm(p); if(!k)continue;
  const s=globalPdcOwners.get(k)||new Set();s.add(m.irveStationId);globalPdcOwners.set(k,s);
}

for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile('data/electroverse/tariff_cache/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    locations++;
    const m=byPk.get(String(row.electroverseLocationPk));
    const local=new Set((m?.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean));
    let hitLoc=false;
    for(const e of row.tariff?.evses||[]){
      evses++;
      const pr=String(e?.physicalReference??'').trim();
      if(!pr)continue;
      physicalRefs++;
      const k=norm(pr),owners=globalPdcOwners.get(k);
      if(owners?.size>1)ambiguousRefs++;
      if(local.has(k)&&owners?.size===1){
        exact++;hitLoc=true;
        if(matchedSamples.length<25)matchedSamples.push({pk:row.electroverseLocationPk,irveStationId:m?.irveStationId,physicalReference:pr,evsePk:e.pk});
      }else if(unmatchedSamples.length<50){
        unmatchedSamples.push({pk:row.electroverseLocationPk,irveStationId:m?.irveStationId??row.irveStationId,physicalReference:pr,evsePk:e.pk,localPdcCount:local.size,globalOwners:owners?[...owners]:[]});
      }
    }
    if(hitLoc)exactLocations++;
  }
}
const out={
  generatedAt:new Date().toISOString(),
  locations,evses,physicalRefs,
  exactUniqueNationalPdcMatches:exact,
  exactLocations,
  exactPhysicalRefPct:physicalRefs?Number((100*exact/physicalRefs).toFixed(3)):0,
  ambiguousRefs,
  policy:'Exact normalized physicalReference -> national IRVE PDC only; no proximity inference.',
  matchedSamples,unmatchedSamples
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
