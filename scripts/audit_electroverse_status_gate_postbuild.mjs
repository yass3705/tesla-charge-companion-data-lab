/** Prevent publication of Electroverse offers sourced from UNKNOWN / OUTOFORDER EVSEs. */
import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const ROOT='data/platforms/electroverse/france-evse';
const STAT='data/electroverse/live_statuses';
const OUTPUT='reports/electroverse/status-gate-postbuild.json';
const read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const gz=async p=>JSON.parse(zlib.gunzipSync(await fs.readFile(p)).toString('utf8'));
const manifest=await read(ROOT+'/manifest.json'),stat=await read(STAT+'/manifest.json'),doc=await gz(STAT+'/'+stat.ledger);
const statusByPk=new Map(),statusConflicts=[];
for(const [loc,entries] of Object.entries(doc.locations||{}))for(const [pk,status] of Object.entries(entries)){
 const prev=statusByPk.get(String(pk));
 if(prev&&prev!==status)statusConflicts.push({pk,location:loc,prior:prev,status});
 statusByPk.set(String(pk),status);
}
const allowed=new Set(['AVAILABLE','CHARGING']);
const bad=[],unknownProvenance=[],covered={};
let offers=0,withPK=0,publishedSourcePkRefs=0;
for(const tile of manifest.tiles||[]){
 const body=await gz(ROOT+'/'+tile.file);
 for(const offer of body.emspOffers||[]){
  offers++;
  const meta=offer.metadata||{};
  const ids=[...new Set([...(meta.electroverseEvsePks||[]),...(meta.electroverseAliasEvsePks||[]),meta.electroverseEvsePk].filter(x=>x!=null).map(String))];
  if(ids.length)withPK++;
  else {unknownProvenance.push({offer:offer.id,targets:offer.evseIds});continue;}
  for(const pk of ids){
   publishedSourcePkRefs++;
   const status=statusByPk.get(pk)||'MISSING';
   covered[status]=(covered[status]||0)+1;
   if(!allowed.has(status))bad.push({offer:offer.id,sourcePk:pk,status,targets:offer.evseIds||[]});
  }
 }
}
const report={generatedAt:new Date().toISOString(),statusSnapshotAt:stat.generatedAt,overlayAt:manifest.generatedAt,
 offers,offersWithExplicitSourcePks:withPK,publishedSourcePkRefs,statusSummary:covered,
 invalidPublishedSourceRefs:bad.length,examples:bad.slice(0,100),missingProvenanceOffers:unknownProvenance.length,
 statusPkConflicts:statusConflicts.length,policy:'All published Electroverse offer source EVSE PKs must be AVAILABLE/CHARGING in status snapshot; reject any UNKNOWN, OUTOFORDER, missing or other.'};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUTPUT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));
if(bad.length||unknownProvenance.length||statusConflicts.length)process.exitCode=2;
