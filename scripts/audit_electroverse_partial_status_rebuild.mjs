/**
 * Safe and read-only dry run of the Elektroverse source-status gate on persisted
 * partitions. Unlike the production builder, never creates or modifies overlay.
 */
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
const CACHE='data/electroverse/tariff_cache';
const PART='data/electroverse/live_statuses/parts';
const OUT='reports/electroverse/partial-status-rebuild-preview.json';
const allowed=new Set(['AVAILABLE','CHARGING']);
const m=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const fingerprint=crypto.createHash('sha256').update(JSON.stringify({date:m.generatedAt,shards:m.shards?.map(s=>[s.file,s.count,s.sizeBytes])})).digest('hex');
const ledger={};
let partCount=0,expected=0,pending=0,stale=0;
const parts=[];
for(let i=0;i<16;i++){
 const file=PART+'/part-'+String(i).padStart(2,'0')+'.json';
 let p;try{p=JSON.parse(await fs.readFile(file,'utf8'))}catch(e){if(e.code==='ENOENT')continue;throw e}
 if(p.sourceFingerprint!==fingerprint)throw Error('Incompatible status source fingerprint: '+file);
 const n=Object.keys(p.entries||{}).length;
 if(n>p.expectedLocations)throw Error('Overfull checkpoint '+file);
 const age=Date.now()-Date.parse(p.startedAt);
 if(!Number.isFinite(age)||age>16*3600000)stale++;
 for(const [loc,evses] of Object.entries(p.entries||{})){
  if(ledger[loc])throw Error('Location appears twice: '+loc);
  ledger[loc]=evses;
 }
 partCount++;expected+=p.expectedLocations;pending+=p.expectedLocations-n;
 parts.push({partition:i,expected:p.expectedLocations,verified:n,remaining:p.expectedLocations-n,
  startedAt:p.startedAt,updatedAt:p.updatedAt});
}
const totals={stationsCovered:0,sourceEvseCount:0,retained:0,excluded:0,
 missingSourcePk:0,sourceReferences:0,duplicateReferencesBefore:0,duplicateReferencesAfter:0,
 statusCounts:{},sampleExclusions:[],sampleMissingSource:[],validPhysicalRefs:0};
const seenLoc=new Set();
const stationSummary=[];
for(const sh of m.shards||[]){
 const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
 for(const [key,row] of Object.entries(data.stations||{})){
  if(!(key in ledger))continue;
  const sourceLoc=String(row.electroverseLocationPk??'');
  if(sourceLoc!==String(key))throw Error('Source location field does not match cache key: '+key+' / '+sourceLoc);
  seenLoc.add(key);totals.stationsCovered++;
  const byRefBefore=new Map(),byRefAfter=new Map();
  let accepted=0,excluded=0,missing=0;
  for(const e of row.tariff?.evses||[]){
   totals.sourceEvseCount++;
   const pk=String(e.pk??''),status=String(ledger[key][pk]??'MISSING').toUpperCase();
   totals.statusCounts[status]=(totals.statusCounts[status]||0)+1;
   if(status==='MISSING'){missing++;totals.missingSourcePk++;
    if(totals.sampleMissingSource.length<15)totals.sampleMissingSource.push({loc:key,pk,ref:e.physicalReference||''});}
   const ref=String(e.physicalReference||'').replace(/[^A-Z0-9]/ig,'').toUpperCase();
   if(ref){byRefBefore.set(ref,(byRefBefore.get(ref)||0)+1);totals.sourceReferences++;}
   if(allowed.has(status)){
    accepted++;totals.retained++;
    if(!allowed.has(status))throw Error('impossible invalid retained source');
    if(ref){byRefAfter.set(ref,(byRefAfter.get(ref)||0)+1);totals.validPhysicalRefs++;}
   }else{
    excluded++;totals.excluded++;
    if(totals.sampleExclusions.length<25)totals.sampleExclusions.push({loc:key,pk,ref:e.physicalReference||null,status});
   }
  }
  const countDuplicates=map=>[...map.values()].filter(n=>n>1).length;
  totals.duplicateReferencesBefore+=countDuplicates(byRefBefore);
  totals.duplicateReferencesAfter+=countDuplicates(byRefAfter);
  stationSummary.push({loc:key,sourceCount:(row.tariff?.evses||[]).length,accepted,excluded,missing,
   multiplePhysicalReferencesRemaining:countDuplicates(byRefAfter)});
 }
}
if(seenLoc.size!==Object.keys(ledger).length)
 throw Error('Ledger contains source location not present in cache: '+seenLoc.size+' != '+Object.keys(ledger).length);
if(totals.retained+totals.excluded!==totals.sourceEvseCount)throw Error('Status gate accounting mismatch');
const output={schemaVersion:1,generatedAt:new Date().toISOString(),mode:'READ_ONLY_PARTITION_SHADOW_PREVIEW',
 publication:false,sourceCacheDate:m.generatedAt,sourceFingerprint:fingerprint,
 sourceTotalLocations:m.totalStations,coveredLocations:Object.keys(ledger).length,
 partCount,pending,partFreshnessWarningCount:stale,partitionCoverage:parts,
 totals,activePriceConflictsUnresolvedByThisTest:true,
 note:'This validates source PK status gating on persisted status partitions. It does not produce the national overlay, decide conflicting tariffs, or publish V9.'};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify({RESULT:'SAFE_SHADOW_PREVIEW_SUCCESS',parts:partCount,
 locations:output.coveredLocations,retained:totals.retained,excluded:totals.excluded,
 duplicateBefore:totals.duplicateReferencesBefore,duplicateAfter:totals.duplicateReferencesAfter,
 unknown:totals.statusCounts.UNKNOWN||0,missing:totals.missingSourcePk,stale}));
