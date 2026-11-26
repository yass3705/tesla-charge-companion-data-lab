import unittest
from scripts.unify_g6_fr_dynamic import rank,engine_agrees,PASS,extra_fixtures
from scripts.evaluate_g6_fr_dynamic import session
class UnifiedTests(unittest.TestCase):
    def row(self,n,amount,decision=PASS):return dict(national_id=n,source_id="S"+n,estimate_eur=amount,decision=decision)
    def test_exclusion_and_ties(self):
        r=[self.row("B","1"),self.row("A","1"),self.row("C","0","INCALCULABLE_SEMANTICS"),self.row("D","0")]
        top,n=rank(r,"10")
        self.assertEqual(n,3);self.assertEqual([x["national_id"] for x in top],["D","A","B"])
        self.assertEqual(rank(list(reversed(r)),"10")[0],top)
    def test_limit(self):
        top,n=rank([self.row(str(i),str(i)) for i in range(30)],"10")
        self.assertEqual((len(top),n),(20,30))
    def test_zero_energy(self):self.assertEqual(rank([self.row("A","2")],"0")[0][0]["estimate_cost_per_km"],"")
    def test_cost_per_km(self):self.assertEqual(rank([self.row("A","10")],"20")[0][0]["estimate_cost_per_km"],"0.090000")
    def test_invalid_estimate(self):
        for v in ("NaN","-1","Infinity",""):
            with self.assertRaises(ValueError):rank([self.row("A",v)],"10")
    def test_engine_guard(self):
        p=dict(energy="1",time="0",parking="0",flat="0",total="1")
        r=dict(p,complete=True,currency="EUR")
        self.assertTrue(engine_agrees(p,r))
        self.assertFalse(engine_agrees(p,dict(r,complete=False)))
        self.assertFalse(engine_agrees(p,dict(r,total="1.1")))
    def test_fixtures(self):
        for f in extra_fixtures():session(f)
