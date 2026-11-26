import unittest
from datetime import datetime,date,timezone
from decimal import Decimal
from scripts.refine_g6_fr_dynamic import quote,intervals
class RefineTest(unittest.TestCase):
    def setUp(self):
        self.base={k:Decimal(v) for k,v in dict(energy="0.5",time="0",parking="0",flat="0").items()}
        self.f=dict(startAt="2026-11-25T22:59:30Z",seconds=60,chargeSeconds=30,parkSeconds=30,energy="3")
    def test_split(self):
        a=datetime.fromisoformat(self.f["startAt"])
        self.assertEqual([(x[0],x[1]) for x in intervals(a,60,30)],[(0,30),(30,60)])
    def test_unused_component(self):
        f=dict(self.f,seconds=30,chargeSeconds=30,parkSeconds=0)
        p=(None,None,(self.base,self.base,{}, {(1439,0):{"energy":Decimal(".5"),"parking":Decimal("1")}}))
        self.assertEqual(quote(p,f,"TIME_BASED")[0],"MODEL_AGREEMENT")
    def test_parking_start_vs_segment(self):
        p=(None,None,(self.base,self.base,{}, {(0,60):{"parking":Decimal("1")}}))
        self.assertEqual(quote(p,self.f,"TIME_BASED")[0],"INCALCULABLE_SEMANTICS")
    def test_energy_distribution(self):
        f=dict(self.f,chargeSeconds=60,parkSeconds=0)
        p=(None,None,(self.base,self.base,{}, {(0,60):{"energy":Decimal(".7")}}))
        self.assertEqual(quote(p,f,"TIME_BASED")[0],"MODEL_OR_ENERGY_ALLOCATION_REVIEW")
    def test_date_gap(self):
        r=(date(2026,11,25),date(2026,11,26),None,{"energy":Decimal(".5")})
        self.assertEqual(quote((None,None,(self.base,[r])),self.f,"DATE_BASED")[0],"DATE_APPLICABILITY_REVIEW")
    def test_old_version(self):
        f=dict(self.f,startAt="2026-11-25T10:00:00Z")
        r=[(date(2025,1,1),date(2026,1,1),None,{"energy":Decimal(".7")}), (date(2026,1,1),None,None,{"energy":Decimal(".5")})]
        self.assertEqual(quote((None,None,(self.base,r)),f,"DATE_BASED")[0],"MODEL_AGREEMENT")
