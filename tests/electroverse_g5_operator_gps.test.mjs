import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyG5Evidence,auditG5OperatorGps,normG5Id,normG5Name}
  from '../scripts/lib/electroverse_g5_operator_gps.mjs';

const mappings=[
 {electroverseLocationPk:'S1',irveStationId:'FRLDLP1',
   evidence:{distanceM:13.4},matchMethod:'spatial_mutual_nearest_v1',
   electroverse:{operatorId:12},
   irve:{name:'Site 1',operator:'LIDL France'}},
 {electroverseLocationPk:'S2',irveStationId:'FRPD1P2',
   evidence:{distanceM:14.1},matchMethod:'spatial_mutual_nearest_v1',
   electroverse:{operatorId:12},
   irve:{name:'Site 2',operator:'Power Dot France'}},
 {electroverseLocationPk:'S3',irveStationId:'FRLDLP3',
   evidence:{distanceM:4.3},matchMethod:'spatial_mutual_nearest_v1',
   electroverse:{operatorId:13},
   irve:{name:'Site 3',operator:'Lidl France'}},
];
const offer=(id,loc,mode,target,physicalReference,more={})=>({
 id,evseIds:[target],metadata:{
  electroverseLocationPk:loc,identityMode:mode,physicalReference,...more,
 }});
test('normalize official EVSE IDs and operator labels without defining a provider alias',()=>{
 assert.equal(normG5Id('FR*LDL*E1'),'FRLDLE1');
 assert.equal(normG5Name('Énergie & Services'),'ENERGIESERVICES');
});
test('exact source EVSE reference independently survives an old >10m station match as identity evidence only',()=>{
 const map=new Map(mappings.map(x=>[x.electroverseLocationPk,x]));
 const x=classifyG5Evidence(offer('o1','S1','exact_unique_national_irve_pdc',
   'FR*LDL*E1','FRLDLE1'),map);
 assert.equal(x.beyond10m,true);
 assert.equal(x.exactSourcePdc,true);
 assert.equal(x.gpsDecision,'EXACT_SOURCE_PDC_EVIDENCE_OPERATOR_PENDING');
 assert.equal(x.operatorEquivalence,'NOT_INDEPENDENTLY_PROVED');
});
test('nonexact PD1 group beyond 10m must not be promoted to proven GPS/operator identity',()=>{
 const map=new Map(mappings.map(x=>[x.electroverseLocationPk,x]));
 const x=classifyG5Evidence(offer('o2','S2',
  'strict_pd1_official_technical_homogeneous_group',
  'FRPD1ETARGET',null,{
   source:'Electroverse tariff cache + Powerdot official technical inventory',
   physicalReferences:['RMC571-1','RMC571-2'],
  }),map);
 assert.equal(x.exactSourcePdc,false);
 assert.equal(x.identityEvidence,'claimed_official_technical_group_needs_independent_review');
 assert.equal(x.gpsDecision,'REQUIRES_INDEPENDENT_OPERATOR_AND_ADDRESS_OR_GPS_PROOF');
});
test('historical operatorId associated with two IRVE operators is diagnostic, not crosswalk authorization',()=>{
 const rows=[
   offer('o1','S1','exact_unique_national_irve_pdc','FRLDLE1','FRLDLE1'),
   offer('o2','S2','strict_station_homogeneous_price_broadcast','FRPD1E1','other'),
   offer('o3','S3','exact_unique_national_irve_pdc','FRLDLE2','FRLDLE2'),
 ];
 const summary=auditG5OperatorGps(rows,mappings);
 assert.equal(summary.distanceOutlierLocationCount,2);
 assert.equal(summary.distanceOutlierOfferCount,2);
 assert.equal(summary.exactSourceIdOutlierOfferCount,1);
 assert.equal(summary.indirectOutlierOfferCount,1);
 assert.equal(summary.supplierIdsWithSeveralNationalOperatorLabels,1);
 assert.equal(summary.operatorIndependentCrosswalkValidated,false);
 assert.equal(summary.locationsWithIndirectUnprovenOffers,1);
 assert.equal(summary.outlierLocationsWithMultiLabelSupplierId,2);
 assert.equal(summary.operatorLabelDiagnostics.find(x=>x.supplierOperatorId==='12').independentCpoProof,false);
});
test('missing source station and duplicate map location are not treated as proof',()=>{
 const r=auditG5OperatorGps([offer('u','unmapped','exact_unique_national_irve_pdc','ABC','ABC')],mappings);
 assert.equal(r.missingMappingOffers,1);
 assert.throws(()=>auditG5OperatorGps([],mappings.concat(mappings[0])),/duplicate or missing/);
});
