import fs from 'node:fs/promises';
import path from 'node:path';
import {resolveSnapshot,snapshotManifest} from './reve-v2-snapshot.mjs';
const SNAP=await resolveSnapshot();
const SOURCE_MANIFEST=await snapshotManifest(SNAP);
const OUTDIR='data/reve-v2/canonical/shards';
const REPORT='data/reve-v2/canonical/build-report.json';
const files=(await fs.readdir(SNAP)).filter(x=>/^locations-page-\d+\.json$/.test(x)).sort();
const locs=new Map();
let rawLocations=0,rawEvses=0,rawConnectors=0,dupLocations=0,dupEvses=0,dupConnectors=0;
function richness(x){return JSON.stringify(x).length}
for(const file of files){
 const j=JSON.parse(await fs.readFile(path.join(SNAP,file),'utf8'));
 for(const loc of j.data||[]){
  rawLocations++;
  const prev=locs.get(loc.id);
  if(prev){dupLocations++; if(richness(loc)>richness(prev)) locs.set(loc.id,loc);}
  else locs.set(loc.id,loc);
 }
}
const stations=[];
const evseGlobal=new Set(), connectorGlobal=new Set();
let tariffMissing=0,withTariff=0;
for(const loc of locs.values()){
 const evses=[]; const localEvse=new Map();
 for(const e of loc.evses||[]){
  rawEvses++;
  const key=e.evse_id||e.id;
  if(localEvse.has(key)){dupEvses++; if(richness(e)>richness(localEvse.get(key))) localEvse.set(key,e);}
  else localEvse.set(key,e);
 }
 for(const e of localEvse.values()){
  evseGlobal.add(e.evse_id||e.id);
  const cons=[]; const localCon=new Map();
  for(const c of e.connectors||[]){
   rawConnectors++;
   if(localCon.has(c.id)){dupConnectors++; if(richness(c)>richness(localCon.get(c.id))) localCon.set(c.id,c);}
   else localCon.set(c.id,c);
  }
  for(const c of localCon.values()){
   if(connectorGlobal.has(c.id)){dupConnectors++;continue;} connectorGlobal.add(c.id);
   const tariffs=Array.isArray(c.tariffs)?c.tariffs:[];
   const missing=tariffs.length===0; if(missing) tariffMissing++; else withTariff++;
   cons.push({...c,tariff_missing:missing,provenance:{source:'REVE',snapshot:SNAP,location_id:loc.id,evse_id:e.evse_id,connector_id:c.id}});
  }
  evses.push({...e,connectors:cons});
 }
 stations.push({...loc,evses,provenance:{source:'REVE',snapshot:SNAP,location_id:loc.id}});
}
stations.sort((a,b)=>String(a.id).localeCompare(String(b.id)));
const canonical={schemaVersion:1,country:'ES',source:'REVE',policy:'REVE-only',generatedAt:new Date().toISOString(),snapshot:SNAP,stations};
const report={schemaVersion:1,generatedAt:canonical.generatedAt,validation:{pages:files.length,stations:stations.length,evses:evseGlobal.size,connectors:connectorGlobal.size,connectorsWithTariff:withTariff,tariffMissing,duplicateLocationsRemoved:dupLocations,duplicateEvsesObserved:dupEvses,duplicateConnectorsObserved:dupConnectors},checks:{pageCoverage:files.length===Number(SOURCE_MANIFEST.pagesSucceeded),stationFloor:stations.length>=10000,evseFloor:evseGlobal.size>=25000,connectorFloor:connectorGlobal.size>=30000,tariffAccounting:withTariff+tariffMissing===connectorGlobal.size,duplicateLocationRate:dupLocations/Math.max(1,rawLocations)<0.001}};
report.ok=Object.values(report.checks).every(Boolean);
if(!report.ok) throw new Error('Canonical validation failed '+JSON.stringify(report));
await fs.mkdir(OUTDIR,{recursive:true});
for(const n of await fs.readdir(OUTDIR))if(/^spain-reve-v2-\d+\.json$/.test(n))await fs.rm(path.join(OUTDIR,n));
const SHARD_SIZE=500;
for(let i=0;i<stations.length;i+=SHARD_SIZE){
 const index=Math.floor(i/SHARD_SIZE)+1;
 const n=String(index).padStart(3,'0');
 const shard={...canonical,stations:stations.slice(i,i+SHARD_SIZE),shard:{index,size:SHARD_SIZE,total:Math.ceil(stations.length/SHARD_SIZE)}};
 await fs.writeFile(path.join(OUTDIR,`spain-reve-v2-${n}.json`),JSON.stringify(shard,null,2)+'\\n');
}
report.storage={format:'sharded-json',stationsPerShard:500,shards:Math.ceil(stations.length/500)};
await fs.writeFile(REPORT,JSON.stringify(report,null,2)+'\\n');
console.log(JSON.stringify(report,null,2));

// workflow bootstrap
