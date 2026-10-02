import fs from 'node:fs/promises';
const MAP='data/electroverse/irve_location_mapping.json';
const OUT='reports/electroverse/b043-target-owner-audit.json';
const targets=new Set(['FRSRGE12346051671','FRSRGE12346051672','FRSRGE12346051681','FRSRGE12346051682']);
const m=JSON.parse(await fs.readFile(MAP,'utf8'));
const owners=[];
for(const row of m.mappings||[]){
 const hits=(row.irvePdcIds||[]).filter(p=>targets.has(String(p)));
 if(hits.length) owners.push({
  electroverseLocationPk:row.electroverseLocationPk,
  irveStationId:row.irveStationId,
  hits,
  irve:row.irve,
  electroverse:row.electroverse,
  matchMethod:row.matchMethod,
  confidence:row.confidence
 });
}
const out={generatedAt:new Date().toISOString(),targetCount:targets.size,ownerRows:owners};
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');console.log(JSON.stringify(out,null,2));