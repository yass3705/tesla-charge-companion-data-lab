import unittest
from scripts.g66b3_quote_gate import fixture,result
from scripts.audit_g66b3_dynamic_gate import user_session
class GateTest(unittest.TestCase):
    def setUp(self):self.s=user_session("2026-11-26T14:37:19+01:00",973,211,"8.963")
    def test_exact_seconds(self):
        f=fixture(self.s);self.assertEqual(f["seconds"],1184);self.assertEqual(f["startAt"],"2026-11-26T13:37:19+00:00")
    def test_reject_fee_exclusion(self):
        with self.assertRaises(ValueError):fixture(dict(self.s,includeCongestionFees=False))
    def test_reject_missing_fee(self):
        with self.assertRaises(ValueError):fixture({k:v for k,v in self.s.items() if k!="includeCongestionFees"})
    def test_reject_missing_offset(self):
        with self.assertRaises(ValueError):fixture(dict(self.s,startAt="2026-11-26T14:00:00"))
    def test_reject_wrong_zone(self):
        with self.assertRaises(ValueError):fixture(dict(self.s,timeZone="UTC"))
    def test_reject_wrong_split(self):
        with self.assertRaises(ValueError):fixture(dict(self.s,seconds=1))
    def test_reject_bool_seconds(self):
        with self.assertRaises(ValueError):fixture(dict(self.s,chargeSeconds=True))
    def test_reject_energy_without_charge(self):
        with self.assertRaises(ValueError):fixture(user_session(self.s["startAt"],0,211,"1"))
    def test_no_amount_on_failure(self):
        q=result("SCOPE_REFUSED","wrong");self.assertIsNone(q["estimateEur"]);self.assertFalse(q["publicationEligible"])
if __name__=="__main__":unittest.main()
