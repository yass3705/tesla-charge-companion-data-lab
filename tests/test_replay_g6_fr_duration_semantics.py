import unittest
from scripts.replay_g6_fr_duration_semantics import delayed_oracle
class DelayedTests(unittest.TestCase):
    def test_connected(self):self.assertEqual(str(delayed_oracle("CONNECTED_TIME",600,"0.10",dict(chargeSeconds=1800,parkSeconds=1200))),"4.000000")
    def test_parking(self):self.assertEqual(str(delayed_oracle("PARKING_TIME",600,"0.10",dict(chargeSeconds=1800,parkSeconds=1200))),"2.000000")
    def test_threshold_in_parking(self):self.assertEqual(str(delayed_oracle("PARKING_TIME",2400,"0.10",dict(chargeSeconds=1800,parkSeconds=1200))),"1.000000")
    def test_charge(self):self.assertEqual(str(delayed_oracle("TIME",600,"0.10",dict(chargeSeconds=1800,parkSeconds=1200))),"2.000000")
    def test_before(self):self.assertEqual(str(delayed_oracle("TIME",600,"0.10",dict(chargeSeconds=599,parkSeconds=0))),"0.000000")
