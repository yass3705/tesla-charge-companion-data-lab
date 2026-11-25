import unittest
from scripts.replay_g6_fr_unrestricted_time import oracle,fixtures
class TestTimeReplay(unittest.TestCase):
    rates={"energy":"0.30","time":"0.03","parking":"0.05","flat":"0.60"}
    def test_charge_only(self):
        self.assertEqual(oracle(self.rates,fixtures()[0]),{"energy":"3.000000","time":"0.900000","parking":"0.000000","flat":"0.600000","total":"4.500000"})
    def test_fractional_minutes(self):
        self.assertEqual(oracle(self.rates,fixtures()[2])["total"],"0.976500")
    def test_parking_only(self):
        self.assertEqual(oracle(self.rates,fixtures()[3])["total"],"1.600000")
    def test_phase_separation(self):
        f={"energy":"10","charging":"30","parking":"15"}
        self.assertEqual(oracle(self.rates,f)["total"],"5.250000")
    def test_sessions(self):
        from decimal import Decimal as D
        self.assertEqual(len(fixtures()),7)
        self.assertTrue(all(D(x["charging"])+D(x["parking"])==D(x["duration"]) for x in fixtures()))
