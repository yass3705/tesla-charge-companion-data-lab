import test from 'node:test';
import assert from 'node:assert/strict';
import {buildElectroverseNationalScopeIndex,classifyElectroverseNationalOffer,
  screenElectroverseG5NationalOffers} from '../scripts/lib/electroverse_g5_national_scope.mjs';

const mappings=[
 {electroverseLocationPk:'FR-A',irveStationId:'MELPRES5920011',
  irvePdcIds:['FR*MEL*E001'],irve:{lat:50.7,lon:3.1,operator:'TotalEnergies Charging Services'}},
 {electroverseLocationPk:'FR-SPANISH-IDENTIFIER',irveStationId:'ESZUNP7408049379758591626',
  irvePdcIds:['ESZUNEFR4521ER01'],irve:{lat:48.1,lon:2.47,operator:'Zunder'}},
 {electroverseLocationPk:'FR-DANISH-IDENTIFIER',irveStationId:'DKMONE3785539',
  irvePdcIds:['DKMONE3785539'],irve:{lat:43.63,lon:1.4,operator:'Monta'}},
 {electroverseLocationPk:'BE-SITE',irveStationId:'BEDRVPAHNX',
  irvePdcIds:['BEDRVEDKSZ1'],irve:{lat:50.68,lon:5.08,operator:'DRIVECO'}},
 {electroverseLocationPk:'FR-PAIR',irveStationId:'FRGYMP735550',
  irvePdcIds:['FRGYMEC12403041'],irve:{lat:48.0,lon:2.0,operator:'GEEVE'}},
];
const offer=(id,loc,target)=>({id,evseIds:[target],metadata:{electroverseLocationPk:loc}});
test('canonical PDC at source location is eligible; country not inferred from station ID prefix',()=>{
 const index=buildElectroverseNationalScopeIndex(mappings);
 for(const [loc,pdc] of [['FR-A','FR*MEL*E001'],
   ['FR-SPANISH-IDENTIFIER','ESZUNEFR4521ER01'],
   ['FR-DANISH-IDENTIFIER','DKMONE3785539']]){
   assert.equal(classifyElectroverseNationalOffer(offer('a',loc,pdc),index).ok,true,loc);
 }
});
test('Belgium mapped real-site evidence is quarantined, not erased at source',()=>{
 const index=buildElectroverseNationalScopeIndex(mappings);
 const a=classifyElectroverseNationalOffer(offer('a','BE-SITE','BEDRVEDKSZ1'),index);
 assert.equal(a.ok,false);
 assert.equal(a.reason,'confirmed_foreign_belgium_site_in_france_overlay');
});
test('unmapped PDCs and missing mapped stations are not published via a loose group join',()=>{
 const index=buildElectroverseNationalScopeIndex(mappings);
 assert.equal(classifyElectroverseNationalOffer(offer('a','FR-PAIR','FRGYMEC12403042'),index).reason,
  'target_not_in_source_location_national_pdcs');
 assert.equal(classifyElectroverseNationalOffer(offer('a','NO-SITE','FRGYMEC12403041'),index).reason,
  'no_source_location_in_national_mapping');
});
test('quarantine is reversible and leaves original mapped rows/offers unmodified',()=>{
 const entries=[offer('a','FR-A','FR*MEL*E001'),offer('b','BE-SITE','BEDRVEDKSZ1'),
  offer('c','FR-PAIR','FRGYMEC12403042')];
 const tiles=new Map([['t_a',entries]]);
 const {tiles:result,report}=screenElectroverseG5NationalOffers(tiles,mappings);
 assert.deepEqual(result.get('t_a'),[entries[0]]);
 assert.equal(report.quarantinedOffers,2);
 assert.equal(report.operatorIndependentMatchVerified,false);
 assert.deepEqual(tiles.get('t_a'),entries);
});
test('never claim operator equivalence just from its acronym or a source station match',()=>{
 const index=buildElectroverseNationalScopeIndex(mappings);
 const a=classifyElectroverseNationalOffer(offer('a','FR-A','FR*MEL*E001'),index);
 assert.equal(a.operatorProof,'requires_separate_operator_and_matching_method_audit');
});
test('duplicate mappings or invalid PDC arrays fail closed',()=>{
 assert.throws(()=>buildElectroverseNationalScopeIndex([...mappings,mappings[0]]),/Duplicate/);
 assert.throws(()=>buildElectroverseNationalScopeIndex([{electroverseLocationPk:'X'}]),/Invalid/);
});

test('documented national PDC supplement remains scoped to its exact station and dated source',()=>{
 const supplement=[{electroverseLocationPk:'FR-PAIR',irveStationId:'FRGYMP735550',
  addedPdcs:[{pdc:'FRGYMEC12403042',kilowatts:150}],
  evidence:{source:'published IRVE-derived inventory',observed:'2026-10-02'}}];
 const index=buildElectroverseNationalScopeIndex(mappings,supplement);
 const e=classifyElectroverseNationalOffer(offer('a','FR-PAIR','FRGYMEC12403042'),index);
 assert.equal(e.ok,true);
 assert.deepEqual(e.supplementalApprovedTargets,['FRGYMEC12403042']);
 assert.deepEqual(mappings[4].irvePdcIds,['FRGYMEC12403041']);
});

test('supplement without station-lock, date, or source cannot invent official PDC',()=>{
 const base={electroverseLocationPk:'FR-PAIR',irveStationId:'ANOTHER-STATION',
  addedPdcs:[{pdc:'FRGYMEC12403042'}],
  evidence:{source:'IRVE evidence',observed:'2026-10-02'}};
 assert.throws(()=>buildElectroverseNationalScopeIndex(mappings,[base]),/station locking/);
 assert.throws(()=>buildElectroverseNationalScopeIndex(mappings,[{
  ...base,irveStationId:'FRGYMP735550',evidence:{observed:'2026-10-02'}}]),/dated evidence/);
});
