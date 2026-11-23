/**
 * Independent, read-only G5 scope audit. Runs only on a built France overlay.
 * PASS here means national PDC membership and France-only quarantine PASS;
 * operator equivalences, GPS fallback evidence, and Production import do NOT
 * become G5 PASS just because this narrow audit succeeds.
 */
import fs from 'node:fs/promises';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import path from 'node:path';
import {
  buildElectroverseNationalScopeIndex,
  classifyElectroverseNationalOffer,
} from './lib/electroverse_g5_national_scope.mjs';

const root=process.argv[2]||'data/platforms/electroverse/france-evse';
const mapPath=process.argv[3]||'data/electroverse/irve_location_mapping.json';
const manifest=JSON.parse(await fs.readFile(path.join(root,'manifest.json'),'utf8'));
const national=JSON.parse(await fs.readFile(mapPath,'utf8'));
const byLocation=buildElectroverseNationalScopeIndex(national.mappings);
const sourceRowsByLocation=new Map(national.mappings.map(x=>[String(x.electroverseLocationPk),x]));
const bad=[],samples=[],byMode={},nationalStations=new Set(),pdcs=new Set(),distanceOver10=new Set();
let total=0,operatorNamed=0,metadataOperator=0,verified=0,unknownPowerCount=0;
const idSeen=new Set(),duplicates=[];
for(const tile of manifest.tiles||[]){
 const bytes=await fs.readFile(path.join(root,tile.file));
 const digest=crypto.createHash('sha256').update(bytes).digest('hex');
 if(digest!==tile.sha256 || bytes.length!==tile.bytes)
   throw Error('G5 tile checksum mismatch: '+tile.file);
 const rows=JSON.parse(zlib.gunzipSync(bytes).toString('utf8')).emspOffers||[];
 if(rows.length!==tile.count)throw Error('G5 tile row count mismatch: '+tile.file);
 for(const offer of rows){
  total++;
  if(idSeen.has(offer.id))duplicates.push(offer.id);
  idSeen.add(offer.id);
  const decision=classifyElectroverseNationalOffer(offer,byLocation);
  if(!decision.ok){bad.push({...decision,id:offer.id});continue;}
  if(offer.countries?.length!==1 || offer.countries[0]!=='FR' ||
      offer.provider!=='Electroverse' || offer.metadata?.verified!==true ||
      !Array.isArray(offer.evseIds) || offer.evseIds.length===0){
   bad.push({id:offer.id,reason:'offer_contract_or_country_invalid'});continue;
  }
  const mapped=byLocation.get(decision.locationPk);
  const sourceRow=sourceRowsByLocation.get(decision.locationPk);
  const distance=sourceRow?.evidence?.distanceM;
  if(typeof distance==='number' && distance>10)distanceOver10.add(decision.locationPk);
  if(mapped.operator)operatorNamed++;
  if(offer.metadata?.operator)metadataOperator++;
  verified++;
  byMode[offer.metadata?.identityMode||'UNKNOWN']=(byMode[offer.metadata?.identityMode||'UNKNOWN']||0)+1;
  nationalStations.add(mapped.stationId);
  for(const target of offer.evseIds)pdcs.add(target);
  if(!offer.metadata?.powerKw && !offer.metadata?.powerKwClass)unknownPowerCount++;
  if(samples.length<12 && typeof distance==='number' && distance>10)
    samples.push({id:offer.id,loc:decision.locationPk,method:sourceRow.matchMethod,
      distanceM:distance,identityMode:offer.metadata?.identityMode});
 }
}
const report={
 checkedAt:new Date().toISOString(),sourceManifestSha256:crypto.createHash('sha256')
  .update(await fs.readFile(path.join(root,'manifest.json'))).digest('hex'),
 offers:total,verifiedOffers:verified,strictSourceLocationPdcExceptions:bad.length,
 uniqueOfferIds:idSeen.size,duplicateOfferIds:duplicates.length,
 mappedNationalStations:nationalStations.size,mappedNationalPdcTargets:pdcs.size,
 offersWithMappedOperatorName:operatorNamed,offersWithOperatorMetadata:metadataOperator,
 locationsMappedByDistanceOver10m:distanceOver10.size,
 longDistanceMappingSamples:samples,
 offersWithoutExplicitPowerMetadata:unknownPowerCount,
 allCountriesStrictFrance:true,operatorIndependentEquivalenceTest:'NOT_VALIDATED',
 fallbackGpsAddressOperatorEvidence:'NOT_VALIDATED',
 reviewedIdentityModes:byMode,issues:bad.slice(0,80),
 quarantinedBeforeOutput:manifest.nationalScopeGate||null,
 residualGate:'G5_PARTIAL_UNTIL_OPERATOR_AND_GPS_FALLBACK_CONTRACT_TESTED',
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/g5-national-scope.json',JSON.stringify(report,null,2)+'\n');
console.log('ELECTROVERSE_G5_NATIONAL_SCOPE '+JSON.stringify({
 offers:total,checked:verified,errors:bad.length,duplicates:duplicates.length,
 excluded:manifest.nationalScopeGate?.quarantinedOffers,
 operatorVerification:'pending',over10mLocations:distanceOver10.size,
}));
if(bad.length||duplicates.length||verified!==total)process.exitCode=2;
