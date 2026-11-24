import unittest
from scripts.audit_irve_g5_v5_residual_exact import category,diagnose
from scripts.audit_electroverse_g5_real_matching import CRITERION_ORDER
class ResidualTests(unittest.TestCase):
    def check(self,**kw):
        c={k:"PASS" for k in CRITERION_ORDER}
        c.update(kw.pop("criteria",{}))
        opts=dict(c_review="C_HELD",c_blockers=[],nmatch=False,smatch=False,source_price=True,recent_fault=False,raw_n="CCS",raw_s="CCS",nplug="CCS",splug="CCS")
        opts.update(kw)
        return diagnose(c,**opts)
    def test_allocations(self):
        self.assertEqual([category(n,s) for n,s in ((True,True),(True,False),(False,True),(False,False))],["BOTH_ALREADY_MATCHED","NATIONAL_ALREADY_MATCHED","SOURCE_ALREADY_MATCHED","BOTH_UNMATCHED"])
    def test_alternative(self):
        self.assertEqual(self.check(nmatch=True,criteria={"plug":"FAIL"})[0],"ALTERNATIVE_ALREADY_RESOLVED")
    def test_occupied(self):
        self.assertEqual(self.check(smatch=True)[0],"SOURCE_OCCUPIED_NO_REASSIGNMENT")
    def test_missing_price(self):
        self.assertEqual(self.check(source_price=False)[0],"NO_PRICE_PAYLOAD_IN_CACHE")
    def test_fault(self):
        self.assertEqual(self.check(recent_fault=True)[0],"TECHNICAL_EXCLUSION_REVIEW")
    def test_identity(self):
        self.assertEqual(self.check(criteria={"evse_uniqueness":"FAIL"})[0],"IDENTITY_OR_UNIQUENESS_REVIEW")
    def test_plug(self):
        self.assertEqual(self.check(splug="CHADEMO",criteria={"plug":"FAIL"})[0],"TECHNICAL_CONTRADICTION_REVIEW")
    def test_unknown(self):
        self.assertEqual(self.check(splug=None,criteria={"plug":"MISSING"})[0],"NOMENCLATURE_REVIEW")
    def test_power(self):
        self.assertEqual(self.check(criteria={"power":"FAIL"})[0],"POWER_REVIEW_NO_RELAXATION")
    def test_multiple_labels(self):
        _,labels=self.check(splug="CHADEMO",criteria={"current":"FAIL","power":"FAIL","tariff_scope":"NOT_EVALUATED"})
        for key in ("NORMALIZED_PLUG_CONTRADICTION","CURRENT_CONTRADICTION","POWER_CONTRADICTION_V5","SCOPE_OR_CARDINALITY_UNPROVEN","C_AUDITED_HELD"):
            self.assertIn(key,labels)
if __name__=="__main__":unittest.main()
