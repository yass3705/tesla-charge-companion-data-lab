import unittest
from decimal import Decimal
from scripts.replay_g6_fr_combined_windows import historical_rates,segments,oracle,envelope,fixtures
class CombinedTests(unittest.TestCase):
    def setUp(self):
        self.base=dict(energy=Decimal("0.4"),time=Decimal(0),parking=Decimal(0),flat=Decimal(1))
        self.w={(1380,420):dict(plain={},bands=[("time",1800,None,Decimal("0.1"))])}
        self.f=dict(startAt="2026-11-25T21:45:00+00:00",seconds=3600,chargeSeconds=1800,parkSeconds=1800,energy="12")
    def test_lower(self):self.assertEqual(historical_rates(self.base,self.w[(1380,420)],1799)["time"],0)
    def test_at(self):self.assertEqual(historical_rates(self.base,self.w[(1380,420)],1800)["time"],Decimal("0.1"))
    def test_segments(self):self.assertEqual(segments(self.w,self.f),[(0,900,None),(900,3600,(1380,420))])
    def test_charge(self):self.assertEqual(oracle(self.base,{},self.w,self.f,segments(self.w,self.f))["time"],"1.500000")
    def test_flat_once(self):self.assertEqual(oracle(self.base,{},self.w,self.f,segments(self.w,self.f))["flat"],"1.000000")
    def test_ambiguity(self):
        lo,hi=envelope(self.base,{},self.w,self.f,segments(self.w,self.f));self.assertLess(lo["time"],hi["time"])
    def test_excluded(self):
        w={(1380,420):dict(plain={},bands=[("time",1080000,None,Decimal("0.1"))])}
        self.assertTrue(all(ex==[1080000] for f,ex in fixtures(w)))
