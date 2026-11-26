import unittest
from decimal import Decimal as D
from scripts.audit_g66b5d_residual_evidence import conservative_rates,zero_temporal,civil_samples,normalized_key
class ResidualTests(unittest.TestCase):
    def f(self,**kw):
        return dict(startAt="2026-11-26T12:00:00Z",duration="30",charging="20",parking="10",energy="5",**kw)
    def base(self):
        return dict(energy=D(".4"),time=D(0),parking=D(0),flat=D(0))
    def test_future_threshold(self):
        p=(self.base(),[({"DURATION_BASED"},None,None,None,1801,{"time":D(".2")})],None)
        r,_=conservative_rates(p,self.f());self.assertTrue(zero_temporal(r,self.f()))
    def test_reached_threshold(self):
        p=(self.base(),[({"DURATION_BASED"},None,None,None,1800,{"time":D(".2")})],None)
        r,_=conservative_rates(p,self.f());self.assertFalse(zero_temporal(r,self.f()))
    def test_clock_outside(self):
        p=(self.base(),[({"TIME_BASED"},None,None,(0,60),0,{"parking":D(".2")})],None)
        r,_=conservative_rates(p,self.f());self.assertTrue(zero_temporal(r,self.f()))
    def test_clock_cross(self):
        f={**self.f(),"startAt":"2026-11-26T12:59:30Z"}
        p=(self.base(),[({"TIME_BASED"},None,None,(840,900),0,{"parking":D(".2")})],None)
        r,_=conservative_rates(p,f);self.assertFalse(zero_temporal(r,f))
    def test_no_phase(self):
        r=self.base();r={k:{v} for k,v in r.items()};r["parking"]={D(".2")}
        self.assertTrue(zero_temporal(r,{**self.f(),"parking":"0"}))
    def test_date_never_excludes_positive(self):
        from datetime import date
        p=(self.base(),[({"DATE_BASED"},date(2027,1,1),None,None,0,{"time":D(".2")})],None)
        r,_=conservative_rates(p,self.f());self.assertFalse(zero_temporal(r,self.f()))
    def test_pair_only_toggle(self):
        q=dict(session=dict(includeCongestionFees=False,energy="5"),tariff_signature="sig")
        self.assertEqual(normalized_key(q),normalized_key({**q,"session":{**q["session"],"includeCongestionFees":True}}))
        self.assertNotEqual(normalized_key(q),normalized_key({**q,"session":{**q["session"],"energy":"6"}}))
if __name__=="__main__":unittest.main()
