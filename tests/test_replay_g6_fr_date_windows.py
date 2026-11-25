import unittest
from datetime import date
from decimal import Decimal
from scripts.replay_g6_fr_date_windows import active,snapshot,quote
class DateTests(unittest.TestCase):
    def setUp(self):
        self.base=dict(energy=Decimal("0.4"),time=Decimal(0),parking=Decimal(0),flat=Decimal(1))
        self.edge=date(2026,11,26)
        self.rules=[(None,self.edge,None,{"energy":Decimal("0.4")}),(self.edge,None,None,{"energy":Decimal("0.6")})]
        self.f=dict(startAt="2026-11-25T22:45:00+00:00",duration=60,charging=60,parking=0,energy="12")
    def test_exclusive(self):self.assertFalse(active(self.rules[0],self.edge));self.assertTrue(active(self.rules[1],self.edge))
    def test_inclusive_conflict(self):
        with self.assertRaises(ValueError):snapshot(self.base,self.rules,self.edge,True)
    def test_empty(self):self.assertFalse(active((self.edge,self.edge,None,{}),self.edge))
    def test_snapshot(self):self.assertEqual(quote(self.base,self.rules,self.f)["total"],"5.800000")
    def test_dynamic(self):self.assertEqual(quote(self.base,self.rules,self.f,"dynamic")["total"],"7.600000")
    def test_flat_once(self):self.assertEqual(quote(self.base,self.rules,self.f,"dynamic")["flat"],"1.000000")
    def test_window(self):
        r=[(self.edge,None,(0,420),{"energy":Decimal("0.2")})]
        self.assertEqual(quote(self.base,r,self.f,"dynamic")["energy"],"3.000000")
