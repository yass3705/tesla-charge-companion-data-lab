import unittest
from scripts.audit_electroverse_g5_exact_mismatches import disposition,group_disposition,power_band,reason_combo

def row(decision, current="PASS", plug="PASS", power="PASS"):
    return {"decision":decision,"criteria":{"current":current,"plug":plug,"power":power}}

class ExactAuditTests(unittest.TestCase):
    def test_normal_alternative(self):
        self.assertEqual(disposition([row("REJECTED_CONTRADICTION",plug="FAIL"),row("MATCH_VALIDATED")]),"HAS_VALIDATED_MATCH")
    def test_conflict_not_resolved_by_missing(self):
        self.assertEqual(disposition([row("REJECTED_CONTRADICTION",power="FAIL"),row("UNRESOLVED_INSUFFICIENT_EVIDENCE",power="MISSING")]),"NONCONTRADICTORY_WITH_MISSING_TECHNICAL_DATA")
    def test_no_compatible(self):
        self.assertEqual(disposition([row("REJECTED_CONTRADICTION",power="FAIL"),row("REJECTED_CONTRADICTION",plug="FAIL")]),"NO_TECHNICALLY_COMPATIBLE_EXACT_PAIR")
    def test_scope_not_validated(self):
        self.assertEqual(disposition([row("REJECTED_AMBIGUITY")]),"TECHNICALLY_CONCORDANT_BUT_UNVALIDATED")
    def test_partial_evse(self):
        self.assertEqual(group_disposition([[row("MATCH_VALIDATED")],[row("REJECTED_CONTRADICTION",power="FAIL")]])[0],"PARTIALLY_VALIDATED")
    def test_band_boundaries(self):
        self.assertEqual([power_band(x) for x in [None,0,1,5,15,30,50,100,101]],["MISSING","0","0-1","1-5","5-15","15-30","30-50","50-100",">100"])
    def test_multiple_failures(self):
        self.assertEqual(reason_combo(row("REJECTED_CONTRADICTION",current="FAIL",plug="FAIL",power="FAIL")),"current+plug+power")

if __name__=="__main__":unittest.main()
