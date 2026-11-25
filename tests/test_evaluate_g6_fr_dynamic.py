import unittest
from decimal import Decimal
from datetime import date
from scripts.evaluate_g6_fr_dynamic import session,envelope,fixtures,MAX
class DynamicTests(unittest.TestCase):
    def setUp(self):
        self.f=dict(startAt="2026-11-25T22:59:45Z",seconds=60,chargeSeconds=30,parkSeconds=30,energy="3.1")
        self.base={k:Decimal(v) for k,v in dict(energy="0.5",time="0",parking="0",flat="0").items()}
    def test_fractional_seconds(self):self.assertEqual(session(self.f)[1:4],(60,30,30))
    def test_inconsistent_minutes(self):
        with self.assertRaises(ValueError):session(dict(self.f,duration=2))
    def test_missing_zone(self):
        with self.assertRaises(ValueError):session(dict(self.f,startAt="2026-11-25T22:59:45"))
    def test_bad_split(self):
        with self.assertRaises(ValueError):session(dict(self.f,parkSeconds=31))
    def test_limit(self):
        with self.assertRaises(ValueError):session(dict(self.f,seconds=MAX+1,chargeSeconds=MAX+1,parkSeconds=0))
    def test_zero_charge_energy(self):
        with self.assertRaises(ValueError):session(dict(self.f,chargeSeconds=0,parkSeconds=60))
    def test_constant(self):
        state,parts=envelope((self.base,[],None),self.f,"TIME_BASED",False)
        self.assertEqual((state,parts["total"]),("DIAGNOSTIC_RATE_AGREEMENT","1.550000"))
    def test_reachable_threshold(self):
        rule=({"DURATION_BASED"},None,None,None,59,{"energy":Decimal("0.6")})
        self.assertEqual(envelope((self.base,[rule],None),self.f,"DURATION_BASED",False)[0],"INCALCULABLE_SEMANTICS")
    def test_unreachable_threshold(self):
        rule=({"DURATION_BASED"},None,None,None,61,{"energy":Decimal("0.6")})
        self.assertEqual(envelope((self.base,[rule],None),self.f,"DURATION_BASED",False)[0],"DIAGNOSTIC_RATE_AGREEMENT")
    def test_date_gap(self):
        rule=({"DATE_BASED"},date(2026,11,25),date(2026,11,26),None,0,{"energy":Decimal("0.5")})
        self.assertEqual(envelope((self.base,[rule],None),self.f,"DATE_BASED",False)[0],"DATE_APPLICABILITY_REVIEW")
    def test_cross_midnight(self):
        rule=({"TIME_BASED"},None,None,(0,60),0,{"energy":Decimal("0.6")})
        self.assertEqual(envelope((self.base,[rule],None),self.f,"TIME_BASED",False)[0],"INCALCULABLE_SEMANTICS")
    def test_missing_component(self):
        rule=({"TIME_BASED"},None,None,(0,60),0,{"parking":Decimal("0")})
        self.assertEqual(envelope((self.base,[rule],None),self.f,"TIME_BASED",False)[0],"INCALCULABLE_SEMANTICS")
    def test_fixtures(self):
        for f in fixtures():session(f)
