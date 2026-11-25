import unittest
from scripts.audit_irve_g5_station_references import compare,classify_mixed,cohort,BLOCKERS
import json
class TestSets(unittest.TestCase):
    def test_equal(self):self.assertEqual(compare(["FRFR1EX1","FRFR1EX2"],["X2","X1"])[0],"FULL_SHORT_REFERENCE_SET_EQUAL")
    def test_extra(self):self.assertEqual(compare(["FRFR1EX1","FRFR1EX2"],["X1"])[1],{"X2":1})
    def test_extra_source(self):self.assertEqual(compare(["FRFR1EX1"],["X1","X2"])[2],{"X2":1})
    def test_duplicate(self):self.assertEqual(compare(["FRFR1EX1","FRLE2EX1"],["X1","X1"])[0],"DUPLICATE_REFERENCE_WITHIN_SITE")
    def test_missing(self):self.assertEqual(compare(["FRFR1EX1"],[""])[0],"MISSING_OR_NONSTRUCTURED_REFERENCE")
    def test_empty(self):self.assertEqual(compare([],["X1"])[0],"EMPTY_SCOPE")
    def test_mixed(self):self.assertTrue(classify_mixed(["FRFR1EX1","FRFR1EX2"],["FRFR1EX1","X2"]))
    def test_mixed_collision(self):self.assertFalse(classify_mixed(["FRFR1EX1","FRLE2EX1"],["FRFR1EX1","X1"]))
    def test_mixed_repeated(self):self.assertFalse(classify_mixed(["FRFR1EX1","FRFR1EX2"],["X1","X1"]))
    def test_no_arbitrary_cut(self):self.assertFalse(classify_mixed(["FRFR1EX1"],["1"]))
    def test_cohort(self):self.assertTrue(cohort({"diagnostics":json.dumps(sorted(BLOCKERS))}));self.assertFalse(cohort({"diagnostics":json.dumps(sorted(BLOCKERS|{"NO_PRICE"}))}))
