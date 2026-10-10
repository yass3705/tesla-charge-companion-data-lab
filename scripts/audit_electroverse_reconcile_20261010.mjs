import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

let source=await fs.readFile('scripts/build_electroverse_france_evse_overlay.mjs','utf8');
function patch(needle,replacement){
 const count=source.split(needle).length-1;
 if(count!==1)throw new Error('Instrument point changed '+count+': '+needle.slice(0,100));
 source=source.replace(needle,replacement);
}
const anchor='const tiles=new Map(),rejected={},parentGroups=new Map(),p01PriceOnlyGroups=new Map();';
patch(anchor,anchor+`
const __reconcileRows=[],__reconcileConflicts=[];
function __reconcileCapture(reason,row,e,extra={}){
 const m=byPk.get(String(row?.electroverseLocationPk||''));
 __reconcileRows.push({
  reason,locationPk:String(row?.electroverseLocationPk||''),
  sourceEvsePk:e?.pk==null?null:String(e.pk),
  physicalReference:e?.physicalReference||null,
  normalizedReference:norm(e?.physicalReference),
  stationName:row?.tariff?.name||row?.name||m?.electroverse?.name||null,
  irveStationId:m?.irveStationId||null,
  powerAndPlug:(e?.connectors||[]).map(c=>({powerKw:c.kilowatts||null,standard:c.standard?.humanName||c.standard?.name||null})),
  ...extra
 });
}
`);
patch("if(!pr){rej('evse_missing_physical_reference');continue;}",
"if(!pr){__reconcileCapture('evse_missing_physical_reference',row,e);rej('evse_missing_physical_reference');continue;}");
patch("if(!owners||owners.size!==1){rej('physical_reference_not_globally_unique');continue;}",
"if(!owners||owners.size!==1){__reconcileCapture('physical_reference_not_globally_unique',row,e,{globalOwnerStations:[...(owners||[])]});rej('physical_reference_not_globally_unique');continue;}");
patch("rej(candidates.length?'parent_pdc_ambiguous':'physical_reference_not_in_local_national_pdcs');continue;",
"{const reason=candidates.length?'parent_pdc_ambiguous':'physical_reference_not_in_local_national_pdcs';__reconcileCapture(reason,row,e,{localParentCandidates:candidates.map(x=>localByNorm.get(x))});rej(reason);continue;}");
patch("rej('duplicate_evse_conflicting_pricing');",
"__reconcileConflicts.push({targetPdc:target,candidates:items.map(x=>({offerId:x.offer?.id,sourceEvsePks:x.offer?.metadata?.electroverseEvsePks||[x.offer?.metadata?.electroverseEvsePk].filter(Boolean),pricing:x.offer?.pricing||null}))});rej('duplicate_evse_conflicting_pricing');");
source+=`
const __auditCounts=Object.fromEntries([...new Set(__reconcileRows.map(r=>r.reason))].map(k=>[k,__reconcileRows.filter(r=>r.reason===k).length]));
__auditCounts.duplicate_evse_conflicting_pricing=__reconcileConflicts.length;
for(const [reason,count] of Object.entries(__auditCounts)){
 if(Number(rejected[reason]||0)!==count)throw new Error('Audit count mismatch '+reason+' '+count+' vs '+rejected[reason]);
}
const __manual=__reconcileRows.filter(r=>r.reason!=='physical_reference_not_in_local_national_pdcs');
const __missing=__reconcileRows.filter(r=>r.reason==='physical_reference_not_in_local_national_pdcs');
const __byStation=new Map();
for(const r of __missing){const k=r.irveStationId||'NO_STATION';const old=__byStation.get(k)||{stationId:k,count:0,examples:[]};old.count++;if(old.examples.length<3)old.examples.push({evse:r.physicalReference,locationPk:r.locationPk});__byStation.set(k,old);}
const __report={
 schemaVersion:1,generatedAt:new Date().toISOString(),method:'instrumented exact overlay builder branch decisions',
 sources:{electroverseCacheGeneratedAt:manifest.generatedAt,irveMappingGeneratedAt:mapping.generatedAt||null,overlayRejections:rejected},
 counts:{manualIdentityCases:__manual.length,parentAmbiguous:__manual.filter(x=>x.reason==='parent_pdc_ambiguous').length,globallyNonUnique:__manual.filter(x=>x.reason==='physical_reference_not_globally_unique').length,missingPhysicalRef:__manual.filter(x=>x.reason==='evse_missing_physical_reference').length,pricingConflictTargets:__reconcileConflicts.length,unmatchedLocalRefs:__missing.length,unmatchedStations:__byStation.size},
 safety:'Reconciliation evidence only; matching failures do not justify guessed tariffs; live Electroverse app not checked. Mismatches can be stale, nonpublic or missing IRVE targets.',
 manualIdentityCases:__manual,
 conflictCases:__reconcileConflicts,
 unmatchedByStation:[...__byStation.values()].sort((a,b)=>b.count-a.count),
 unmatchedSamples:__missing.slice(0,80)
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/reconciliation-classified-2026-10-10.json',JSON.stringify(__report,null,2)+'\\n');
await fs.writeFile('reports/electroverse/reconciliation-unmatched-2026-10-10.json.gz',zlib.gzipSync(Buffer.from(JSON.stringify(__missing))));
console.log('RECONCILIATION_AUDIT',JSON.stringify(__report.counts));
`;
const tmp=await fs.mkdtemp(path.join(os.tmpdir(),'electroverse-reconciliation-'));
const target=path.join(process.cwd(),'scripts','.electroverse_audit_runtime_'+process.pid+'.mjs');
try{
 await fs.writeFile(target,source);
 const result=spawnSync('node',['--max-old-space-size=6144',target,path.join(tmp,'overlay')],{encoding:'utf8',maxBuffer:20*1024*1024,timeout:20*60*1000});
 if(result.stdout)console.log(result.stdout.slice(-7000));
 if(result.stderr)console.error(result.stderr.slice(-7000));
 if(result.status!==0)throw new Error('Reconciliation builder exited '+result.status+' '+(result.error?.message||''));
}finally{
 await fs.rm(target,{force:true});
 await fs.rm(tmp,{recursive:true,force:true});
}
