import unittest,json
from scripts.audit_irve_g5_power_scope import scope,classify,projected_power
class ScopeTests(unittest.TestCase):
    def row(self, national=22, source=4, mode="AC", plug="PASS", current="PASS", power="FAIL"):
        return {"national_kw":national,"source_kw":source,"national_mode":mode,"criteria_json":json.dumps({"plug":plug,"current":current,"power":power})}
    def test_multitype(self):
        self.assertEqual(scope({"ef","type2"},{22}),"MULTITYPE_PDC_INDIVIDUAL_POWER_UNPROVEN")
    def test_single_not_individual_proof(self):
        self.assertEqual(scope({"ef"},{22}),"SINGLE_DECLARED_TYPE_NOMINAL_ONLY")
    def test_conflict(self):
        self.assertEqual(scope({"ef","type2"},{22,7}),"PDC_NOMINAL_MISSING_OR_CONFLICTING")
    def test_missing(self):
        self.assertEqual(scope({"ef"},{None}),"PDC_NOMINAL_MISSING_OR_CONFLICTING")
    def test_multitype_below(self):
        self.assertEqual(classify(self.row(),scope({"ef","type2"},{22})),"MULTITYPE_SOURCE_BELOW_NOMINAL_REVIEW")
    def test_multitype_above(self):
        self.assertEqual(classify(self.row(22,44),scope({"ef","type2"},{22})),"MULTITYPE_SOURCE_ABOVE_NOMINAL_REVIEW")
    def test_other_failure_kept(self):
        self.assertEqual(classify(self.row(plug="FAIL"),scope({"ef","type2"},{22})),"OTHER_TECHNICAL_CONTRADICTION")
    def test_small_ac_not_pass(self):
        self.assertEqual(classify(self.row(22.1,22),scope({"type2"},{22.1})),"AC_SMALL_DELTA_REVIEW_NOT_TOLERANCE")
    def test_dc_not_pass(self):
        self.assertEqual(classify(self.row(320,380,"DC"),scope({"ccs"},{320})),"DC_DELTA_REVIEW")
    def test_no_power_fail(self):
        self.assertEqual(classify(self.row(power="PASS"),scope({"ef","type2"},{22})),"NO_POWER_FAILURE")
    def test_legacy_projection(self):
        self.assertEqual(projected_power({"puissancenominale":"22,1"}),22.1)
if __name__=="__main__":unittest.main()
