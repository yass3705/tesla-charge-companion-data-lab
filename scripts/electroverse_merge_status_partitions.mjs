/** Merge two checkpoints from the same immutable cache partition without losing successes. */
import fs from 'node:fs/promises';
const [incomingPath,destinationPath]=process.argv.slice(2);
if(!incomingPath||!destinationPath)throw Error('Usage: node electroverse_merge_status_partitions.mjs incoming.json destination.json');
const incoming=JSON.parse(await fs.readFile(incomingPath,'utf8'));
let existing;
try{existing=JSON.parse(await fs.readFile(destinationPath,'utf8'));}
catch(e){if(e.code!=='ENOENT')throw e;}
const entries={...(existing?.entries||{})};
const errors={...(existing?.errors||{})};
if(existing){
 for(const field of ['partition','partitionCount','sourceFingerprint','expectedLocations']){
  if(existing[field]!==incoming[field])throw Error('Checkpoint source mismatch: '+field);
 }
}
const later=existing&&Date.parse(existing.updatedAt)>Date.parse(incoming.updatedAt);
for(const [pk,entry] of Object.entries(incoming.entries||{})){
 if(!(pk in entries)||!later)entries[pk]=entry;
}
Object.assign(errors,incoming.errors||{});
for(const key of Object.keys(entries))delete errors[key];
const merged={...incoming,startedAt:[existing?.startedAt,incoming.startedAt].filter(Boolean).sort()[0],
 updatedAt:[existing?.updatedAt,incoming.updatedAt].filter(Boolean).sort().at(-1),
 entries,errors};
await fs.mkdir(destinationPath.slice(0,destinationPath.lastIndexOf('/')),{recursive:true});
await fs.writeFile(destinationPath,JSON.stringify(merged,null,2)+'\n');
console.log(JSON.stringify({partition:merged.partition,previousGood:Object.keys(existing?.entries||{}).length,
 incomingGood:Object.keys(incoming.entries||{}).length,mergedGood:Object.keys(entries).length,
 mergedErrors:Object.keys(errors).length,remaining:merged.expectedLocations-Object.keys(entries).length,
 startedAt:merged.startedAt,updatedAt:merged.updatedAt}));
