import unittest
from scripts.replay_g6_fr_simple import oracle,fixtures
class TestSimpleReplay(unittest.TestCase):
    def test_decimal_fraction(self):
        self.assertEqual(oracle({"energy":"0.45","flat":"1.00"},"23.456"),{"energy":"10.555200","flat":"1.000000","total":"11.555200"})
    def test_one_wh(self):
        self.assertEqual(oracle({"energy":"0.29","flat":"0"},"0.001")["total"],"0.000290")
    def test_fee_once(self):
        self.assertEqual(oracle({"energy":"0.48","flat":"3.00"},"10")["total"],"7.800000")
    def test_sessions(self):
        f=fixtures();self.assertEqual(len(f),6);self.assertEqual(len({r["id"] for r in f}),6)
        self.assertTrue(all(x["charging"]+x["parking"]==x["duration"] for x in f))
