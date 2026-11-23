/**
 * Audit the optional, reversible Electroverse technical-fault screen.
 * Never infer free/occupied; never join supplier statuses on a global EVSE PK.
 * A missing status snapshot must not prevent publication of tariff comparisons.
 */
import fs from 'node:fs/promises';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import {assessElectroverseFault, DEFAULT_FAULT_MAX_AGE_MS} from './lib/electroverse_status_fault_filter.mjs';

const ROOT='data/platforms/electroverse/france-evse';
const STAT='data/electroverse/live_statuses';
const OUTPUT='reports/electroverse/status-gate-postbuild.json';
const read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const gz=async p=>JSON.parse(zlib.gunzipSync(await fs.readFile(p)).toString('utf8'));
const manifest=await read(ROOT+'/manifest.json');
const gate=manifest.statusGate||{};
const snapshotValidated=gate.statusEvidence==='validated_optional_historical_snapshot';
let doc={locations:{},observedAtByLocation:{}};
if(snapshotValidated){
 const stat=await read(STAT+'/manifest.json');
 const raw=await fs.readFile(STAT+'/'+stat.ledger);
 const digest=crypto.createHash('sha256').update(raw).digest('hex');
 doc=JSON.parse(zlib.gunzipSync(raw).toString('utf8'));
 if(!gate.statusEvidenceSha256||gate.statusEvidenceSha256!==digest ||
    stat.ledger!=='evses.json.gz'||stat.statusRole!=='historical_nonblocking_observations' ||
    stat.failedLocations!==0||stat.completeness?.locations!==true||
    doc.sourceFingerprint!==stat.sourceFingerprint||
    doc.generatedAt!==gate.generatedAt){
   throw Error('Optional historical status screening provenance mismatch');
 }
}
const screenedAtMs=Date.parse(gate.faultCheckedAt);
if(snapshotValidated && !Number.isFinite(screenedAtMs))
 throw Error('Missing fault screening timestamp for reproducible postbuild audit');
const maxAgeMs=Number(gate.faultMaxAgeHours)*3600000 || DEFAULT_FAULT_MAX_AGE_MS;
if(snapshotValidated && maxAgeMs!==DEFAULT_FAULT_MAX_AGE_MS)
 throw Error('Unapproved EVSE fault screening age policy');

const bad=[],unknownProvenance=[],covered={};
let offers=0,withPK=0,publishedSourcePkRefs=0;
for(const tile of manifest.tiles||[]){
 const body=await gz(ROOT+'/'+tile.file);
 for(const offer of body.emspOffers||[]){
  offers++;
  const meta=offer.metadata||{};
  const loc=String(meta.electroverseLocationPk??'');
  const ids=[...new Set([
   ...(meta.electroverseEvsePks||[]),
   ...(meta.electroverseAliasEvsePks||[]),
   meta.electroverseEvsePk,
  ].filter(x=>x!=null).map(String))];
  if(!loc || !ids.length){
   unknownProvenance.push({offer:offer.id,locationPk:loc||null,targets:offer.evseIds||[]});
   continue;
  }
  withPK++;
  for(const pk of ids){
   publishedSourcePkRefs++;
   const assessment=assessElectroverseFault(doc,loc,pk,{
    nowMs:screenedAtMs,maxFaultAgeMs:maxAgeMs,
   });
   covered[assessment.status]=(covered[assessment.status]||0)+1;
   if(assessment.excludeFromActiveTariffs)
    bad.push({offer:offer.id,sourceLocationPk:loc,sourceEvsePk:pk,
              status:assessment.status,observedAt:assessment.observedAt,
              targets:offer.evseIds||[]});
  }
 }
}
const report={
 generatedAt:new Date().toISOString(),statusSnapshotAt:gate.generatedAt||null,
 overlayAt:manifest.generatedAt,screenedAt:gate.faultCheckedAt||null,
 optionalSnapshotValidated:snapshotValidated,optionalEvidenceIssue:gate.statusEvidenceIssue||null,
 sourceEvsePkCollisions:doc?.sourceEvsePkDuplicatedAcrossLocations??null,
 offers,offersWithExplicitSourcePks:withPK,publishedSourcePkRefs,statusSummary:covered,
 confirmedFaultsStillPublished:bad.length,examples:bad.slice(0,100),
 missingProvenanceOffers:unknownProvenance.length,
 policy:'Only station-scoped, timestamped recent OUTOFORDER/INOPERATIVE may be filtered; UNKNOWN/BLOCKED/CHARGING and missing observations do not suppress prices',
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUTPUT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));
if(bad.length||unknownProvenance.length)process.exitCode=2;
