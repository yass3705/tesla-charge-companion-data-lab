import unittest
import ast
import inspect
from scripts.audit_irve_g5_v6_simulation import hold_reasons,tariff_status,station_reasons,main
import json
class TestV6(unittest.TestCase):
 def test_missing_operator_allowed(self):self.assertEqual(hold_reasons({"operator":"MISSING","country":"MISSING"}),[])
 def test_operator_fail_blocks(self):self.assertEqual(hold_reasons({"operator":"FAIL"}),["V5_CONTRADICTION:operator"])
 def test_power_fail_blocks(self):self.assertEqual(hold_reasons({"power":"FAIL"}),["V5_CONTRADICTION:power"])
 def test_missing_tariff_scope(self):self.assertEqual(tariff_status(None),"TARIFF_SCOPE_UNVERIFIED")
 def test_schema_recognized(self):self.assertEqual(tariff_status({"raw_verified":"True","scope":"DIRECT_CONNECTOR_EVIDENCE_ONLY","additional_blockers":"[]","schema":"DIRECT_CONDITIONAL_NO_OBSERVED_POWER_CONDITION"}),"TARIFF_SCHEMA_RECOGNIZED_PENDING_G6")
 def test_unknown_schema_does_not_remove_identity(self):self.assertEqual(tariff_status({"raw_verified":"True","scope":"DIRECT_CONNECTOR_EVIDENCE_ONLY","additional_blockers":"[\"SCHEMA_REVIEW_REQUIRED\"]","schema":"UNKNOWN_OR_CONFLICTING_SCHEMA_REVIEW"}),"TARIFF_SCHEMA_REVIEW_G6")
 def site(self):return {"raw_pdc_count":"2","source_evse_count":"2","raw_ids":'["FRFR1EX1","FRFR1EX2"]',"source_groups":'[["1","X1"],["2","X2"]]',"station_id":"N","location_pk":"L","global_national_sites":'["N"]',"global_source_sites":'["L"]',"v5_other_station_anchor":"False","v5_reference_conflicts":"0"}
 def refs(self):return {x:{"status":"GLOBAL_STRUCTURAL_UNIQUENESS_ONLY","national_raw_owners":json.dumps([["N","FRFR1E"+x]]),"source_owners":json.dumps([["L",str(i)]]),"full_id_owners":"[]"} for i,x in enumerate(["X1","X2"],1)}
 def test_station(self):self.assertEqual(station_reasons(self.site(),self.refs()),[])
 def test_collision(self):
  r=self.refs();r["X2"]["status"]="NATIONAL_MULTIPLE_RAW_OWNERS";self.assertIn("SIBLING_REFERENCE_GLOBAL_COLLISION_OR_FULL_ID",station_reasons(self.site(),r))
 def test_occupied_anchor(self):
  s=self.site();s["v5_other_station_anchor"]="True";self.assertIn("V5_STATION_OR_REFERENCE_ANCHOR_CONFLICT",station_reasons(s,self.refs()))
 def test_station_not_unique(self):
  s=self.site();s["global_national_sites"]='["N","M"]';self.assertIn("STATION_FINGERPRINT_NOT_BIDIRECTIONALLY_UNIQUE",station_reasons(s,self.refs()))
 def test_single_station(self):
  s=self.site();s["raw_pdc_count"]="1";self.assertIn("SINGLE_EVSE_NO_ADDITIONAL_SET_EVIDENCE",station_reasons(s,self.refs()))

 def test_ledger_reference_survives_candidate_loop_and_final_hash_check(self):
  # Regression for run 45691838639: the candidate loop rebound the ledger dict.
  tree=ast.parse(inspect.getsource(main))
  stores=[n for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store) and n.id=="ledger_files"]
  self.assertEqual(len(stores),1)
  checks=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="verify" and len(n.args)==2 and ast.unparse(n.args[0])=="ledger_files['db.sqlite']" and ast.unparse(n.args[1])=="p['sqliteSha256']"]
  self.assertEqual(len(checks),2)
  writes=[n.lineno for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="write_csv"]
  self.assertEqual(len(writes),2)
  self.assertLess(min(n.lineno for n in checks),min(writes))
  self.assertGreater(max(n.lineno for n in checks),max(writes))
