import unittest
from scripts.audit_electroverse_g5_real_matching import scoped_power_check,exact_scope_check,decision_from_criteria,MULTITYPE,CRITERION_ORDER
class PowerScopeABTests(unittest.TestCase):
    def n(self,plug="EF",kw=22,scope=MULTITYPE,mode="AC"):
        return dict(plug=plug,kw=kw,power_scope=scope,mode=mode)
    def s(self,plug="EF",kw=4,connector="c",mode="AC",price=True):
        return dict(plug=plug,kw=kw,mode=mode,pk="evse",connector=connector,price=price)
    def test_old(self):
        self.assertEqual(scoped_power_check(self.s(),self.n())[0],"FAIL")
    def test_below(self):
        self.assertEqual(scoped_power_check(self.s(),self.n(),True),("MISSING",18,"POWER_SCOPE_NOT_COMPARABLE"))
    def test_equal_not_socket_proof(self):
        self.assertEqual(scoped_power_check(self.s(kw=22),self.n(),True)[0],"MISSING")
    def test_above(self):
        self.assertEqual(scoped_power_check(self.s(kw=44),self.n(),True)[0],"FAIL")
    def test_mono_small_delta(self):
        self.assertEqual(scoped_power_check(self.s(kw=7),self.n(kw=7.4,scope="SINGLE_DECLARED_TYPE_NOMINAL_ONLY"),True)[0],"FAIL")
    def test_dc(self):
        self.assertEqual(scoped_power_check(self.s("CCS",380,mode="DC"),self.n("CCS",320,mode="DC"),True)[0],"FAIL")
    def test_wrong_type(self):
        self.assertEqual(scoped_power_check(self.s("TYPE2"),self.n(),True)[0],"FAIL")
    def test_wrong_current(self):
        self.assertEqual(scoped_power_check(self.s(mode="DC"),self.n(),True)[0],"FAIL")
    def test_no_positive_power(self):
        self.assertEqual(scoped_power_check(self.s(kw=0),self.n(),True)[0],"MISSING")
        self.assertIsNone(scoped_power_check(self.s(kw=0),self.n(),True)[2])
    def test_unique_scope(self):
        n=self.n();s=self.s();other=self.n("TYPE2")
        self.assertNotEqual(exact_scope_check(s,n,[n,other],[s])[0],"PASS")
        self.assertEqual(exact_scope_check(s,n,[n,other],[s],True),("PASS","PASS","NOT_APPLICABLE"))
    def test_ambiguous_scope(self):
        n=self.n();s=self.s();other=self.s(kw=3,connector="other")
        self.assertNotEqual(exact_scope_check(s,n,[n],[s,other],True)[0],"PASS")
    def test_duplicate_connector(self):
        n=self.n();s=self.s();other=self.s()
        self.assertEqual(exact_scope_check(s,n,[n],[s,other],True)[1],"FAIL")
    def test_missing_price(self):
        n=self.n();s=self.s(price=False)
        self.assertEqual(exact_scope_check(s,n,[n],[s],True)[0],"MISSING")
    def test_remaining_blocker(self):
        c={k:"PASS" for k in CRITERION_ORDER};c["power"]="MISSING";c["plug"]="FAIL"
        self.assertEqual(decision_from_criteria(c)["decision"],"REJECTED_CONTRADICTION")
    def test_remaining_ambiguity(self):
        c={k:"PASS" for k in CRITERION_ORDER};c["power"]="MISSING";c["evse_uniqueness"]="FAIL"
        self.assertEqual(decision_from_criteria(c)["decision"],"REJECTED_AMBIGUITY")
    def test_missing_scope(self):
        c={k:"PASS" for k in CRITERION_ORDER};c["power"]="MISSING";c["tariff_scope"]="NOT_EVALUATED"
        self.assertEqual(decision_from_criteria(c)["decision"],"UNRESOLVED_INSUFFICIENT_EVIDENCE")
    def test_valid_missing(self):
        c={k:"PASS" for k in CRITERION_ORDER};c["power"]="MISSING"
        self.assertEqual(decision_from_criteria(c)["decision"],"MATCH_VALIDATED")
if __name__=="__main__":unittest.main()
