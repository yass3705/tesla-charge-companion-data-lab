import unittest
from scripts.audit_g6_fr_segment_rounding import segment_oracle,explain
class SegmentRounding(unittest.TestCase):
    def setUp(self):
        def r(scope,start,end):return dict(scope=scope,start=start,end=end,currency="EUR",pricePerKwh="0",chargePerMinute="0.04",idlePerMinute="0.04",connectionFee="0")
        self.rules=[r("allDay","00:00","24:00"),r("timeWindow","22:00","00:00"),r("timeWindow","00:00","07:00")]
        self.f=dict(startAt="2026-11-25T22:48:37Z",seconds=2460,chargeSeconds=1861,parkSeconds=599,energy="20.527")
    def test_exact_split(self):
        p,s=segment_oracle(self.rules,self.f)
        self.assertEqual([(x["startSecond"],x["endSecond"]) for x in s],[(0,683),(683,2460)])
        self.assertEqual(p["total"],"1.639999")
        self.assertEqual(p["time"],"1.240666")
    def test_explain(self):
        p,_=segment_oracle(self.rules,self.f)
        canonical=dict(p,time="1.240667",total="1.640000")
        self.assertTrue(explain(canonical,p,dict(p,complete=True,currency="EUR")))
        self.assertFalse(explain(canonical,p,dict(p,complete=True,currency="EUR",total="1.64")))
    def test_not_cent_equal(self):
        p,_=segment_oracle(self.rules,self.f)
        self.assertFalse(explain(dict(p,total="1.66"),p,dict(p,complete=True,currency="EUR")))
    def test_unknown_dimension(self):
        with self.assertRaises(ValueError):segment_oracle([dict(self.rules[0],energyStepWh=1000)],self.f)
