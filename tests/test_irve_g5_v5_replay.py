import unittest
from scripts.audit_irve_g5_v5_replay import apply_c,assert_unique,blockers,REASON,VALID
from scripts.audit_electroverse_g5_real_matching import CRITERION_ORDER,decision_from_criteria
from scripts.audit_irve_g5_power_identity_scenarios import signature
class V5Tests(unittest.TestCase):
    def fixture(self):
        c={k:"PASS" for k in CRITERION_ORDER}
        c.update(power="FAIL",cardinality="NOT_EVALUATED",tariff_scope="NOT_EVALUATED",tariff_homogeneity="NOT_EVALUATED",country="MISSING",operator="MISSING",address="NOT_APPLICABLE",gps="NOT_APPLICABLE")
        v=decision_from_criteria(c);v.update(power_delta_kw=60,power_justification=None)
        n=dict(id=1,evse_normalized="FRTEST",mode="DC",plug="CCS",kw=60)
        s=dict(id=2,location_pk="1",evse_pk="2",connector_pk="3",reference_normalized="FRTEST",mode="DC",plug="CCS",kw=120,has_price=1,recent_fault=0)
        return v,n,s
    def test_apply(self):
        v,_,_=self.fixture();a=apply_c(v,[])
        self.assertEqual(a["decision"],VALID);self.assertEqual(a["criteria"]["power"],"NOT_APPLICABLE")
        self.assertEqual(a["power_justification"],REASON);self.assertEqual(v["criteria"]["power"],"FAIL")
        self.assertEqual(a["criteria"]["operator"],"MISSING")
    def test_hold(self):
        v,_,_=self.fixture();self.assertEqual(apply_c(v,["blocked"]),v)
    def test_other_fail(self):
        v,_,_=self.fixture();v["criteria"]["country"]="FAIL"
        with self.assertRaises(ValueError):apply_c(v,[])
    def test_duplicate(self):
        for p in ({(1,2),(1,3)},{(1,2),(4,2)}):
            with self.assertRaises(ValueError):assert_unique(p)
    def test_unique(self):
        assert_unique({(1,2),(3,4)})
    def test_missing_raw(self):
        v,n,s=self.fixture()
        reasons=blockers(v,n,s,[n],[s],True,None,False,"SINGLE_DECLARED_TYPE_NOMINAL_ONLY")
        self.assertIn("RAW_CONNECTOR_NOT_PROVEN",reasons)
    def test_competition_fault_existing(self):
        v,n,s=self.fixture();s["recent_fault"]=1
        other=dict(s,id=3,connector_pk="4")
        reasons=blockers(v,n,s,[n],[s,other],True,None,True,"SINGLE_DECLARED_TYPE_NOMINAL_ONLY")
        for x in ("INDEPENDENT_CONNECTOR_UNIQUENESS_NOT_PROVEN","RECENT_FAULT_EXCLUSION","V4_MATCH_ALREADY_EXISTS"):
            self.assertIn(x,reasons)
    def test_ac_not_generalized(self):
        v,n,s=self.fixture();n["mode"]=s["mode"]="AC"
        reasons=blockers(v,n,s,[n],[s],True,None,False,"SINGLE_DECLARED_TYPE_NOMINAL_ONLY")
        self.assertIn("OUTSIDE_APPROVED_POWER_SCOPE",reasons)
    def test_global_uniqueness(self):
        v,n,s=self.fixture()
        self.assertIn("IDENTITY_OR_GLOBAL_UNIQUENESS",blockers(v,n,s,[n],[s],False,None,False,"SINGLE_DECLARED_TYPE_NOMINAL_ONLY"))
if __name__=="__main__":unittest.main()
