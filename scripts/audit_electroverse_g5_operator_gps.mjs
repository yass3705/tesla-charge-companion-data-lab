/**
 * Independent G5 operator + GPS evidence inventory. No operator alias is
 * inferred from historical majority labels, no supplier calls, no publication.
 */
import fs from 'node:fs/promises';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import path from 'node:path';
import {auditG5OperatorGps} from './lib/electroverse_g5_operator_gps.mjs';
import {auditG5Hierarchy} from './lib/electroverse_g5_matching_hierarchy.mjs';

const root=process.argv[2]||'data/platforms/electroverse/france-evse';
const mapPath=process.argv[3]||'data/electroverse/irve_location_mapping.json';
const manifest=JSON.parse(await fs.readFile(path.join(root,'manifest.json'),'utf8'));
const raw=await fs.readFile(mapPath);
const mapping=JSON.parse(raw.toString('utf8'));
const officialTechnicalPath='data/operator_direct/powerdot_evse_technical_inventory.json';
const officialTechnicalRaw=await fs.readFile(officialTechnicalPath);
const officialTechnical=JSON.parse(officialTechnicalRaw.toString('utf8'));
if(officialTechnical.dataset!=='powerdot-official-france-technical-inventory' ||
   !Array.isArray(officialTechnical.evses) || officialTechnical.evses.length<6000)
 throw Error('Missing authoritative dated Powerdot identity/technical inventory');
if(!Array.isArray(mapping?.mappings))throw Error('Cannot audit missing original national location mapping');
const offers=[];
for(const tile of manifest.tiles||[]){
 const b=await fs.readFile(path.join(root,tile.file));
 if(crypto.createHash('sha256').update(b).digest('hex')!==tile.sha256||b.length!==tile.bytes)
   throw Error('Untrusted overlay tile: '+tile.file);
 const doc=JSON.parse(zlib.gunzipSync(b).toString('utf8'));
 const rows=doc.emspOffers||[];
 if(rows.length!==tile.count)throw Error('Invalid offer count: '+tile.file);
 offers.push(...rows);
}
const result=auditG5OperatorGps(offers,mapping.mappings,officialTechnical.evses);
const operatorReview=JSON.parse(await fs.readFile(
  'data/platforms/electroverse/validated-mappings/g5-operator-crosswalk-review.json','utf8'));
const hierarchy=auditG5Hierarchy(offers,mapping.mappings,operatorReview);
if(hierarchy.offersReviewed!==result.overallOfferCount ||
   hierarchy.status!=='AUDIT_ONLY_NO_PRICE_PROMOTION')
 throw Error('Independent G5 matching hierarchy audit incomplete');
if(result.missingMappingOffers!==0 || result.overallOfferCount!==manifest.stats?.publishedOffers)
 throw Error('G5 operator/GPS evidence must reconcile with built overlay');
const proof={
 checkedAt:new Date().toISOString(),
 overlayManifestSha256:crypto.createHash('sha256').update(
   await fs.readFile(path.join(root,'manifest.json'))).digest('hex'),
 originalNationalMappingSha256:crypto.createHash('sha256').update(raw).digest('hex'),
 officialTechnicalInventorySha256:crypto.createHash('sha256').update(officialTechnicalRaw).digest('hex'),
 officialTechnicalInventorySource:officialTechnical.source,
 officialTechnicalPublisherUpdatedAt:officialTechnical.publisherLastUpdateKnown,
 artifactProvider:'Electroverse',country:'FR',status:'AUDIT_ONLY_G5_PARTIAL',
 g5MatchingHierarchy:hierarchy,
 ...result,
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/g5-operator-gps.json',
 JSON.stringify(proof,null,2)+'\n');
console.log('ELECTROVERSE_G5_OPERATOR_GPS '+JSON.stringify({
 total:result.overallOfferCount,outlierLocations:result.distanceOutlierLocationCount,
 outlierOffers:result.distanceOutlierOfferCount,
 exactSourceIds:result.exactSourceIdOutlierOfferCount,
 indirectOffers:result.indirectOutlierOfferCount,
 technicallyCorroborated:result.technicallyCorroboratedOutlierOffers,
 stillUnprovedIndirect:result.indirectStillUnprovedOutlierOffers,
 operatorIdLabelConflicts:result.supplierIdsWithSeveralNationalOperatorLabels,
 operatorVerified:false,
 hierarchyReviewedOperatorPairs:hierarchy.operatorPairsIndependentlyReviewed,
 hierarchyUnresolvedOffers:hierarchy.offersReviewed-hierarchy.independentlyAssignableOffers,
 publication:false,
}));
