import unittest
from decimal import Decimal as D
from scripts.g66b5a_planner_gate import planner_session
from scripts.g66b5b_clock_gate import spans,clock_quote
def session(start="2026-11-26T20:50:00Z"):
    return dict(protocol="planner-v1",startAt=start,timeZone="Europe/Paris",energy="12.000000",durationMinutes="30.000000",chargingMinutes="20.000000",postChargeMinutes="10.000000",includeCongestionFees=True,chargeTimeline=[dict(offsetMinutes="0.000000",durationMinutes="10.000000",energyKwh="8.000000"),dict(offsetMinutes="10.000000",durationMinutes="10.000000",energyKwh="4.000000")])
def rates(e=".4"):return dict(energy=D(e),time=D("0"),parking=D("0"),flat=D("0"))
class Clock(unittest.TestCase):
    def test_energy_not_uniform(self):
        s=session();f=planner_session(s);r=spans(s,f)
        before=sum(x[4] for x in r if x[3]<1320)
        after=sum(x[4] for x in r if x[3]>=1320)
        self.assertAlmostEqual(before,D(8));self.assertAlmostEqual(after,D(4))
    def test_conflicting_model(self):
        s=session();f=planner_session(s);base=rates()
        state,parts,seg,rules,models=clock_quote((base,[],(base,base,{}, {(1320,360):rates(".3")})),s,f,"TIME_BASED")
        self.assertEqual(state,"INCALCULABLE_SEMANTICS");self.assertIsNone(parts)
        totals={v["total"] for v in models.values()}
        self.assertIn("4.400000",totals);self.assertIn("4.800000",totals)
    def test_identical_models(self):
        s=session();f=planner_session(s);base=rates()
        state,p,*_=clock_quote((base,[],(base,base,{}, {(1320,360):base})),s,f,"TIME_BASED")
        self.assertEqual(state,"MODEL_AGREEMENT");self.assertEqual(p["total"],"4.800000")
    def test_spring_gap(self):
        s=session("2026-03-29T00:50:00Z");r=spans(s,planner_session(s));m={x[3] for x in r}
        self.assertIn(119,m);self.assertIn(180,m);self.assertNotIn(120,m)
    def test_autumn_fold(self):
        s=session("2026-10-25T00:50:00Z");r=spans(s,planner_session(s));m=[x[3] for x in r]
        self.assertIn(179,m);self.assertIn(120,m);self.assertGreater(m.index(120),m.index(179))
    def test_midnight(self):
        s=session("2026-11-26T22:50:00Z");r=spans(s,planner_session(s));self.assertEqual(len({x[2] for x in r}),2)
    def test_unknown_allocation(self):
        s=session();s["energy"]="12.000001"
        with self.assertRaisesRegex(ValueError,"ENERGY_RECONCILIATION"):spans(s,planner_session(s))
    def test_date_gap(self):
        s=session();f=planner_session(s);base=rates()
        from datetime import date
        state,*_=clock_quote((base,[],(base,[(date(2026,1,1),date(2026,1,2),None,base)])),s,f,"DATE_BASED")
        self.assertEqual(state,"DATE_APPLICABILITY_REVIEW")
if __name__=="__main__":unittest.main()
