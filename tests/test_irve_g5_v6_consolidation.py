import unittest
import sqlite3
from scripts.audit_irve_g5_v6_consolidation import cohort,install,ACCEPT,REJECT,RECOGNIZED,REVIEW,NONE

def row(n,s,state=ACCEPT,tariff=RECOGNIZED,why="[]"):
    return dict(national_id=n,source_id=s,identity_decision=state,tariff_decision=tariff,decision_reasons=why)

class ConsolidationTests(unittest.TestCase):
    def test_valid_union_includes_review(self):
        self.assertEqual(cohort([row(1,1)],[row(2,2,tariff=REVIEW),row(3,3,REJECT,NONE,'["COLLISION"]')],1,2,1),({(1,1)},{(2,2)}))
    def test_reassignment_fails(self):
        with self.assertRaises(ValueError):cohort([row(1,1)],[row(1,2)],1,1,1)
    def test_source_reassignment_fails(self):
        with self.assertRaises(ValueError):cohort([row(1,1)],[row(2,1)],1,1,1)
    def test_accept_with_reason_fails(self):
        with self.assertRaises(ValueError):cohort([row(1,1)],[row(2,2,why='["FAIL"]')],1,1,1)
    def test_held_requires_reason(self):
        with self.assertRaises(ValueError):cohort([row(1,1)],[row(2,2,REJECT,NONE)],1,1,0)
    def test_sidecar_keeps_original_decisions(self):
        db=sqlite3.connect(":memory:")
        db.executescript("""
        CREATE TABLE candidate(national_id INTEGER,source_id INTEGER,decision TEXT);
        CREATE TABLE national_disposition(national_id INTEGER,result TEXT);
        CREATE TABLE source_disposition(source_id INTEGER,result TEXT);
        INSERT INTO candidate VALUES(1,1,'MATCH_VALIDATED'),(2,2,'OLD_HELD'),(3,3,'OLD_HELD');
        INSERT INTO national_disposition VALUES(1,'MATCH_VALIDATED'),(2,'CANDIDATES_UNRESOLVED'),(3,'CANDIDATES_UNRESOLVED');
        INSERT INTO source_disposition SELECT national_id,result FROM national_disposition;
        """)
        install(db,[row(1,1)],[row(2,2,tariff=REVIEW),row(3,3,REJECT,NONE,'["COLLISION"]')])
        self.assertEqual(db.execute("SELECT decision FROM candidate WHERE national_id=2").fetchone()[0],"OLD_HELD")
        self.assertEqual(db.execute("SELECT effective_identity_decision,effective_tariff_state FROM v6_candidate_effective WHERE national_id=2").fetchone(),("MATCH_VALIDATED",REVIEW))
        self.assertEqual(db.execute("SELECT effective_identity_decision FROM v6_candidate_effective WHERE national_id=3").fetchone()[0],"OLD_HELD")
        self.assertEqual(db.execute("SELECT sum(v6_validated_count) FROM v6_national_disposition").fetchone()[0],2)
