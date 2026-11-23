import test from 'node:test';
import assert from 'node:assert/strict';
import {compileG5CpoProofs,classifyG5MatchHierarchy,auditG5Hierarchy}
  from '../scripts/lib/electroverse_g5_matching_hierarchy.mjs';

const mapping={electroverseLocationPk:'CL1',irveStationId:'FRLDLP001',
  irvePdcIds:['FR*LDL*E1'],irve:{operator:'Lidl France'},
  electroverse:{operatorId:123}};
const offer=(ref,target='FR*LDL*E1')=>({
 id:'t1',evseIds:[target],metadata:{electroverseLocationPk:'CL1',
 physicalReference:ref},
});
const pair={supplierOperatorId:'123',nationalOperator:'Lidl France',country:'FR',
 reviewStatus:'INDEPENDENT_REVIEW_APPROVED',reviewedAt:'2026-11-23',
 evidence:{kind:'explicit_supplier_operator_to_cpo_link',
 supplierRecord:'supplier official document ID 123',
 nationalRecord:'national operator official document ID LDL',
 sourceOperatorIdExplicit:true,nationalCpoIdentityExplicit:true}};
const approved=()=>compileG5CpoProofs({schemaVersion:1,approvedPairs:[pair]});
const options={targetOwnersUnique:true,sameCountry:true,stationIdentityConfirmed:true};
test('statistical names, physical ID and proximity alone never certify a CPO',()=>{
 const result=classifyG5MatchHierarchy(offer('FRLDLE1'),mapping,new Map(),options);
 assert.equal(result.assignable,false);
 assert.equal(result.reason,'independent_operator_equivalence_missing');
});
test('crosswalk requires two distinct explicit independently reviewed sources',()=>{
 assert.throws(()=>compileG5CpoProofs({schemaVersion:1,approvedPairs:[{
   ...pair,evidence:{...pair.evidence,nationalRecord:pair.evidence.supplierRecord},
 }]}),/unproved operator/);
 assert.throws(()=>compileG5CpoProofs({schemaVersion:1,approvedPairs:[{
  ...pair,reviewStatus:'NAME_SIMILAR',
 }]}),/unproved operator/);
 assert.throws(()=>compileG5CpoProofs({schemaVersion:1,approvedPairs:[pair,pair]}),/duplicate/);
});
test('exact EVSE identity plus reviewed operator, country and unique owner takes priority',()=>{
 const decision=classifyG5MatchHierarchy(offer('FR*LDL*E1'),mapping,approved(),options);
 assert.equal(decision.classification,'exact+operator');
 assert.equal(decision.assignable,true);
 const ambiguous=classifyG5MatchHierarchy(offer('FR*LDL*E1'),mapping,approved(),
   {...options,targetOwnersUnique:false});
 assert.equal(ambiguous.assignable,false);
 assert.equal(classifyG5MatchHierarchy(offer('FR*LDL*E1'),mapping,approved(),
   {...options,sameCountry:false}).assignable,false);
});
test('wrong reviewed supplier CPO prevents exact-ID price attribution',()=>{
 const wrong={...mapping,irve:{operator:'Other Operator'}};
 assert.equal(classifyG5MatchHierarchy(offer('FRLDLE1'),wrong,approved(),options).assignable,false);
});
const fallback={method:'gps',reviewStatus:'INDEPENDENT_SCOPE_REVIEW_APPROVED',
 reviewedAt:'2026-11-23',sourceRecord:'Electroverse independently reviewed connector',
 nationalRecord:'National independently reviewed connector',
 stationId:'FRLDLP001',country:'FR',uniqueSiteCandidates:1,distanceM:9.5,
 targetPdcIds:['FR*LDL*E1'],pdcScopeReviewed:true,
 connectorAndPowerReviewed:true,tariffHomogeneityReviewed:true};
test('GPS fallback only under 10m with explicit CPO, unique station and PDC scope',()=>{
 const input=offer('non-identifying reference');
 const ok=classifyG5MatchHierarchy(input,mapping,approved(),{...options,fallback});
 assert.equal(ok.classification,'gps+operator');
 for(const f of [
   {...fallback,distanceM:12},
   {...fallback,uniqueSiteCandidates:2},
   {...fallback,pdcScopeReviewed:false},
   {...fallback,connectorAndPowerReviewed:false},
   {...fallback,tariffHomogeneityReviewed:false},
   {...fallback,targetPdcIds:['other']},
 ]) assert.equal(classifyG5MatchHierarchy(input,mapping,approved(),
   {...options,fallback:f}).assignable,false);
});
test('address fallback requires exact independent address and EVSE technical scope',()=>{
 const input=offer('not an ID');
 const f={...fallback,method:'address',distanceM:15,exactAddressConfirmed:true};
 assert.equal(classifyG5MatchHierarchy(input,mapping,approved(),{
   ...options,fallback:f}).classification,'address+operator');
 assert.equal(classifyG5MatchHierarchy(input,mapping,approved(),{
   ...options,fallback:{...f,exactAddressConfirmed:false}}).assignable,false);
});
test('current empty proof registry leaves offers pending, not silently retariffed',()=>{
 const base={schemaVersion:1,approvedPairs:[]};
 const r=auditG5Hierarchy([offer('FRLDLE1')],[mapping],base);
 assert.equal(r.operatorPairsIndependentlyReviewed,0);
 assert.equal(r.offersReviewed,1);
 assert.equal(r.independentlyAssignableOffers,0);
 assert.equal(r.byDecision.independent_operator_equivalence_missing,1);
 assert.equal(r.automaticPublication,false);
});
