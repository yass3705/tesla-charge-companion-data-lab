import unittest
from collections import defaultdict
from scripts.audit_irve_g5_alias_local import numeric,suffix_matches,possible_bijections,row_status,addr_state
class AliasLocalTest(unittest.TestCase):
    def test_numeric(self):
        self.assertEqual(numeric("001"),1)
        self.assertIsNone(numeric("1000"))
        self.assertIsNone(numeric("FR1"))
    def test_suffix(self):
        e={"mode":"strict_post_overlay_numeric_suffix_bijection","width":2,"prefix":"FRA"}
        self.assertTrue(suffix_matches("FRA01","1",e))
        self.assertFalse(suffix_matches("FRB01","1",e))
        self.assertFalse(suffix_matches("FRA02","1",e))
    def test_unique(self):
        self.assertEqual(possible_bijections([1,2],["FRA1","FRA2"],{"FRA1":{1},"FRA2":{2}}),[((1,"FRA1"),(2,"FRA2"))])
    def test_two_prefixes(self):
        t=["FRA1","FRA2","FRB1","FRB2"]
        self.assertEqual(len(possible_bijections([1,2],t,{x:{1} for x in t})),2)
    def test_duplicate_ordinals(self):
        self.assertEqual(possible_bijections([1,1],["A1"],{"A1":{1}}),[])
    def test_duplicate_owner(self):
        self.assertEqual(possible_bijections([1],["A1"],{"A1":{1,2}}),[])
    def test_missing_ordinal(self):
        self.assertEqual(possible_bijections([None,1],["A1"],{"A1":{1}}),[])
    def test_classification(self):
        self.assertEqual(row_status([],[],[],[],False,False,True),"TARGET_ABSENT_NATIONAL_STATIC")
        self.assertEqual(row_status([1],[],[],[],False,False,True),"TARGET_OUTSIDE_ACTIVE_PROJECTION")
        self.assertEqual(row_status([1],[1],[1],[1],False,False,False),"NO_EXPLICIT_EVIDENCE_FIELD")
        self.assertEqual(row_status([1],[1],[1],[1],False,True,True),"EXACT_ALREADY_VALIDATED_PAIR")
    def test_missing_source(self):
        self.assertEqual(row_status([1],[1],[],[],False,False,True),"SOURCE_LOCATION_EVSE_ABSENT")
        self.assertEqual(row_status([1],[1],[1],[],False,False,True),"SOURCE_REFERENCE_CHANGED_OR_MISSING")
    def test_address(self):
        self.assertEqual(addr_state("","Rue de Paris"),"MISSING")
        self.assertEqual(addr_state("Rue de Paris","Rue de Paris"),"PASS")
