import unittest
from decimal import Decimal as D
from scripts.g66b5e_dynamic_gate import zero_result,ZERO,UNCLASSIFIED
from scripts.g66b3_quote_gate import result
from scripts.unify_g6_fr_dynamic import PASS
from scripts.audit_g66b5d_residual_evidence import FEE
class DynamicZeroTests(unittest.TestCase):
    def fixture(self):
        session={"includeCongestionFees":False,"energy":"1.000000"}
        common=dict(scope={"tariff_signature":"x"},nationalId="n",lineage={"codeSha":"x"},congestionEvidence=UNCLASSIFIED)
        orig={**result(FEE,FEE),**common,"session":session}
        parts=dict(energy="1",time="0",parking="0",flat="0",total="1")
        inc={**result(PASS,parts=parts,canonical=parts),**common,"session":{**session,"includeCongestionFees":True}}
        return orig,inc,{"time":{D(0)},"parking":{D(0)}},{"charging":"10","parking":"2"}
    def test_exact(self):
        o,i,p,f=self.fixture();r=zero_result(i,o,p,f)
        self.assertEqual(r["congestionEvidence"],ZERO);self.assertEqual(r["estimateEur"],"1");self.assertFalse(r["publicationEligible"]);self.assertEqual(r["session"],o["session"])
    def test_positive_rate(self):
        o,i,p,f=self.fixture();p["time"].add(D(".1"));self.assertIsNone(zero_result(i,o,p,f))
    def test_positive_component(self):
        o,i,p,f=self.fixture();i["components"]["parking"]="0.01";self.assertIsNone(zero_result(i,o,p,f))
    def test_different_session(self):
        o,i,p,f=self.fixture();i["session"]["energy"]="2";self.assertIsNone(zero_result(i,o,p,f))
    def test_different_scope(self):
        o,i,p,f=self.fixture();i["nationalId"]="other";self.assertIsNone(zero_result(i,o,p,f))
    def test_refused_included(self):
        o,i,p,f=self.fixture();i["decision"]="INCALCULABLE_SEMANTICS";self.assertIsNone(zero_result(i,o,p,f))
    def test_unknown_schema(self):
        o,i,p,f=self.fixture();o["congestionEvidence"]="UNKNOWN_RAW_SCHEMA";self.assertIsNone(zero_result(i,o,p,f))
if __name__=="__main__":unittest.main()
