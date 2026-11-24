import unittest
from scripts.audit_irve_g5_nonexact_inventory import allocation,evidence_class,alias_scope
class InventoryTests(unittest.TestCase):
    def test_allocations(self):
        self.assertEqual([allocation(n,s) for n,s in ((True,True),(True,False),(False,True),(False,False))],["BOTH_ALREADY_MATCHED","NATIONAL_ALREADY_MATCHED","SOURCE_ALREADY_MATCHED","BOTH_UNMATCHED"])
    def test_alias(self):self.assertEqual(evidence_class("validated_alias+operator",["a"],[]),"DOCUMENTED_ALIAS")
    def test_address(self):self.assertEqual(evidence_class("address+operator",[],[1],"PASS","FAIL"),"ADDRESS")
    def test_gps(self):self.assertEqual(evidence_class("gps+operator_unverified",[],[],"FAIL","PASS"),"GPS")
    def test_historical_only(self):self.assertEqual(evidence_class("gps+operator",[],[1],"FAIL","FAIL"),"HISTORICAL_OFFER_ONLY")
    def test_unproven_site(self):self.assertEqual(evidence_class("gps+operator",[],[],"MISSING","FAIL"),"OTHER_UNPROVEN_SITE")
    def test_inconsistent(self):self.assertEqual(evidence_class("gps+operator",["a"],[]),"ALIAS_LEDGER_INCONSISTENCY")
    def test_scope(self):
        n=dict(id=1,plug="CCS",mode="DC",kw=60);s=dict(id=2,plug="CCS",mode="DC",kw=60)
        self.assertEqual(alias_scope(s,n,[n],[s]),([1],[2]))
    def test_missing_competitor(self):
        n=dict(id=1,plug="CCS",mode="DC",kw=60);s=dict(id=2,plug="CCS",mode="DC",kw=60);t=dict(id=3,plug=None,mode=None,kw=None)
        self.assertEqual(alias_scope(s,n,[n],[s,t]),([1],[2,3]))
    def test_power_not_relaxed(self):
        n=dict(id=1,plug="CCS",mode="DC",kw=60);s=dict(id=2,plug="CCS",mode="DC",kw=90)
        self.assertEqual(alias_scope(s,n,[n],[s]),([],[]))
if __name__=="__main__":unittest.main()
