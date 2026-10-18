import fs from 'node:fs/promises';
import path from 'node:path';
import {resolveSnapshot,snapshotManifest} from './reve-v2-snapshot.mjs';

const SNAP=await resolveSnapshot();
const SOURCE_MANIFEST=await snapshotManifest(SNAP);
const OUT=path.join('data/reve-v2/analysis',path.basename(SNAP));
// analysis-only touch: raw snapshot and protected synthesis are never modified
await fs.mkdir(OUT,{recursive:true});
const files=(await fs.readdir(SNAP)).filter(x=>/^locations-page-\d+\.json$/.test(x)).sort();
const owners=new Map(), statuses={}, sourceTypes={}, missing=[];
let locations=0,evses=0,connectors=0,locWithTariff=0,evseWithTariff=0,connectorWithTariff=0,freeConnectors=0,pricedConnectors=0,tariffObjects=0;
const locIds=new Set(),evseIds=new Set(),connectorIds=new Set(),dupes={locations:0,evses:0,connectors:0};
for(const file of files){
 const j=JSON.parse(await fs.readFile(path.join(SNAP,file),'utf8'));
 for(const loc of (j.data||[])){
  locations++; if(locIds.has(loc.id)) dupes.locations++; else locIds.add(loc.id);
  const owner=loc.owner?.name||'(missing owner)';
  const o=owners.get(owner)||{owner,locations:0,evses:0,connectors:0,connectorsWithTariff:0,connectorsMissingTariff:0};
  o.locations++;
  statuses[loc.status||'UNKNOWN']=(statuses[loc.status||'UNKNOWN']||0)+1;
  sourceTypes[loc.source_type||'UNKNOWN']=(sourceTypes[loc.source_type||'UNKNOWN']||0)+1;
  let lTar=false;
  for(const evse of (loc.evses||[])){
   evses++;o.evses++; if(evseIds.has(evse.evse_id)) dupes.evses++; else evseIds.add(evse.evse_id);
   let eTar=false;
   for(const con of (evse.connectors||[])){
    connectors++;o.connectors++; if(connectorIds.has(con.id)) dupes.connectors++; else connectorIds.add(con.id);
    const ts=Array.isArray(con.tariffs)?con.tariffs:[];
    if(ts.length){connectorWithTariff++;o.connectorsWithTariff++;eTar=true;lTar=true;tariffObjects+=ts.length;
      if(ts.some(t=>(t.human||[]).some(h=>/gratuito|free/i.test(h)))) freeConnectors++;
      if(ts.some(t=>(t.tariff?.elements||[]).some(e=>(e.price_components||[]).some(pc=>Number.isFinite(Number(pc.price)))))) pricedConnectors++;
    } else {
      o.connectorsMissingTariff++;
      missing.push({locationId:loc.id,locationName:loc.name,owner,evseId:evse.evse_id,connectorId:con.id,status:evse.status||loc.status||null,maxElectricPower:con.max_electric_power??null,sourceType:loc.source_type||null});
    }
   }
   if(eTar) evseWithTariff++;
  }
  if(lTar) locWithTariff++;
  owners.set(owner,o);
 }
}
const ownerRows=[...owners.values()].sort((a,b)=>b.locations-a.locations||a.owner.localeCompare(b.owner));
const summary={schemaVersion:1,snapshot:SNAP,generatedAt:new Date().toISOString(),pages:files.length,counts:{locations,uniqueLocations:locIds.size,evses,uniqueEvses:evseIds.size,connectors,uniqueConnectors:connectorIds.size,owners:owners.size,tariffObjects},coverage:{locationsWithTariff:locWithTariff,locationsWithTariffPct:+(100*locWithTariff/locations).toFixed(2),evsesWithTariff:evseWithTariff,evsesWithTariffPct:+(100*evseWithTariff/evses).toFixed(2),connectorsWithTariff:connectorWithTariff,connectorsWithTariffPct:+(100*connectorWithTariff/connectors).toFixed(2),connectorsMissingTariff:connectors-connectorWithTariff,pricedConnectors,freeConnectors},duplicates:dupes,statuses,sourceTypes,validation:{pageCountOk:files.length===Number(SOURCE_MANIFEST.pagesSucceeded),sourceNonEmpty:locations>0,duplicateLocationRate:+(dupes.locations/Math.max(1,locations)).toFixed(6),ok:files.length===Number(SOURCE_MANIFEST.pagesSucceeded)&&locations>0}};
await fs.writeFile(path.join(OUT,'coverage-summary.json'),JSON.stringify(summary,null,2)+'\n');
await fs.writeFile(path.join(OUT,'owners-summary.json'),JSON.stringify({schemaVersion:1,generatedAt:summary.generatedAt,owners:ownerRows},null,2)+'\n');
await fs.writeFile(path.join(OUT,'missing-tariff-connectors.json'),JSON.stringify({schemaVersion:1,generatedAt:summary.generatedAt,count:missing.length,items:missing},null,2)+'\n');
console.log(JSON.stringify(summary,null,2));
