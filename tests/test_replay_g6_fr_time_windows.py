import unittest
from decimal import Decimal
from scripts.replay_g6_fr_time_windows import oracle,contains,minute
class WindowTests(unittest.TestCase):
    def setUp(self):
        self.base=dict(energy=Decimal("0.4"),time=Decimal("0.1"),parking=Decimal("0.2"),flat=Decimal("1"))
        self.windows={(23*60,7*60):dict(time=Decimal("0.05"),parking=Decimal("0.1"),flat=Decimal("2"))}
    def test_wrap(self):self.assertTrue(contains((1380,420),0));self.assertFalse(contains((1380,420),420))
    def test_minute(self):self.assertEqual(minute("23:00:00"),1380)
    def test_crossing(self):
        f=dict(startAt="2026-11-25T21:45:00+00:00",duration=60,charging=30,parking=30)
        r=oracle(self.base,self.windows,f)
        self.assertEqual(r["time"],"2.250000");self.assertEqual(r["parking"],"3.000000");self.assertEqual(r["flat"],"1.000000")
    def test_dst(self):
        f=dict(startAt="2026-03-29T00:30:00+00:00",duration=60,charging=30,parking=30)
        self.assertEqual(oracle(self.base,self.windows,f)["time"],"1.500000")
    def test_missing_not_zero(self):
        f=dict(startAt="2026-11-25T23:00:00+00:00",duration=60,charging=30,parking=30)
        self.assertNotEqual(oracle(self.base,self.windows,f),oracle(self.base,self.windows,f,replace_missing=True))
    def test_bad_precision(self):
        with self.assertRaises(ValueError):minute("23:00:01")
