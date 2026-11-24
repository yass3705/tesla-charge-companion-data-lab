import unittest
from scripts.audit_electroverse_g5_real_matching import scoped_power_check,exact_scope_check,MULTITYPE
class AcToleranceTests(unittest.TestCase):
    def n(self,kw=22,plug="TYPE2",mode="AC",scope="SINGLE_DECLARED_TYPE_NOMINAL_ONLY"):
        return dict(kw=kw,plug=plug,mode=mode,power_scope=scope)
    def s(self,kw=22.1,plug="TYPE2",mode="AC",connector="1"):
        return dict(kw=kw,plug=plug,mode=mode,pk="evse",connector=connector,price=True)
    def test_22_1(self):
        self.assertEqual(scoped_power_check(self.s(),self.n(),True,True),("PASS",0.1,"AC_1KW_TOLERANCE_USER_APPROVED"))
    def test_7_4(self):
        self.assertEqual(scoped_power_check(self.s(7),self.n(7.4),True,True)[0],"PASS")
    def test_inclusive_boundary_both_directions(self):
        for kw in (21,23):self.assertEqual(scoped_power_check(self.s(kw),self.n(),True,True)[0],"PASS")
    def test_above_boundary(self):
        self.assertEqual(scoped_power_check(self.s(23.01),self.n(),True,True)[0],"FAIL")
    def test_disabled(self):
        self.assertEqual(scoped_power_check(self.s(),self.n(),True,False)[0],"FAIL")
        self.assertEqual(scoped_power_check(self.s(),self.n(),False,True)[0],"FAIL")
    def test_dc(self):
        self.assertEqual(scoped_power_check(self.s(151,"CCS","DC"),self.n(150,"CCS","DC"),True,True)[0],"FAIL")
    def test_multitype_above(self):
        self.assertEqual(scoped_power_check(self.s(22.5),self.n(scope=MULTITYPE),True,True)[0],"FAIL")
    def test_multitype_below(self):
        self.assertEqual(scoped_power_check(self.s(21.5),self.n(scope=MULTITYPE),True,True)[0],"MISSING")
    def test_missing_conflicting_scope(self):
        self.assertEqual(scoped_power_check(self.s(),self.n(scope="PDC_NOMINAL_MISSING_OR_CONFLICTING"),True,True)[0],"FAIL")
    def test_plug_and_current(self):
        for s in (self.s(22.1,"EF"),self.s(22.1,mode="DC"),self.s(22.1,plug=None)):
            self.assertEqual(scoped_power_check(s,self.n(),True,True)[0],"FAIL")
    def test_unique_scope(self):
        n=self.n();s=self.s()
        self.assertEqual(exact_scope_check(s,n,[n],[s],True,True),("PASS","PASS","NOT_APPLICABLE"))
    def test_scope_ambiguity(self):
        n=self.n();s=self.s();other=self.s(22,connector="2")
        self.assertNotEqual(exact_scope_check(s,n,[n],[s,other],True,True)[0],"PASS")
    def test_missing_power(self):
        self.assertEqual(scoped_power_check(self.s(None),self.n(),True,True)[0],"MISSING")
if __name__=="__main__":unittest.main()
