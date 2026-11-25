import unittest
from decimal import Decimal
from scripts.replay_g6_fr_duration import oracle,scenarios
class DurationTests(unittest.TestCase):
    def setUp(self):
        self.rates=dict(energy=Decimal("0.40"),time=Decimal(0),parking=Decimal(0),flat=Decimal(0))
        self.bands=[("time",600,None,Decimal("0.10")),("flat",0,1,Decimal("1"))]
    def test_before(self):self.assertEqual(oracle(self.rates,self.bands,599,599,0,10)["total"],"4.000000")
    def test_at(self):self.assertEqual(oracle(self.rates,self.bands,600,600,0,10)["total"],"5.000000")
    def test_after(self):self.assertEqual(oracle(self.rates,self.bands,601,601,0,10)["total"],"5.001667")
    def test_parking_not_charge(self):self.assertEqual(oracle(self.rates,self.bands,600,0,600,0)["total"],"0.000000")
    def test_exclusive_flat(self):self.assertEqual(oracle(self.rates,self.bands,1,1,0,0)["flat"],"0.000000")
    def test_boundaries(self):
        ss={x["seconds"] for x in scenarios(self.bands)}
        self.assertTrue({1,599,600,601}.issubset(ss))
