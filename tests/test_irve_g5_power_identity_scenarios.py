import unittest
from scripts.audit_irve_g5_power_identity_scenarios import independent_unique,scenario_flags,tariff_gate
class ScenarioTests(unittest.TestCase):
    def n(self,i=1,p="CCS",kw=60):
        return dict(id=i,plug=p,mode="DC",kw=kw,evse_normalized="ABC")
    def s(self,i=1,p="CCS",kw=90,pk="1"):
        return dict(id=i,plug=p,mode="DC",kw=kw,evse_pk="E",connector_pk=pk,reference_normalized="ABC")
    def test_above(self):
        self.assertTrue(all(scenario_flags(60,90).values()))
    def test_below(self):
        self.assertEqual(list(scenario_flags(60,30).values()),[False,False,True])
        self.assertEqual(list(scenario_flags(100,90).values()),[False,True,True])
    def test_relative_and_absolute(self):
        self.assertFalse(scenario_flags(300,280)["B_ABOVE_OR_LIMITED_BELOW"])
        self.assertFalse(scenario_flags(60,50)["B_ABOVE_OR_LIMITED_BELOW"])
    def test_unique_without_power(self):
        n,s=self.n(),self.s()
        self.assertTrue(independent_unique(s,n,[n],[s]))
    def test_sibling_competes_despite_power(self):
        n,s=self.n(),self.s()
        self.assertFalse(independent_unique(s,n,[n],[s,self.s(2,kw=60,pk="2")]))
    def test_unknown_plug_competes(self):
        n,s=self.n(),self.s()
        self.assertFalse(independent_unique(s,n,[n,self.n(2,None)],[s]))
    def test_mismatching_id(self):
        n,s=self.n(),self.s();s["reference_normalized"]="XYZ"
        self.assertFalse(independent_unique(s,n,[n],[s]))
    def test_free(self):
        self.assertEqual(tariff_gate(dict(isChargingFree=True))[0],"DIRECT_SIMPLE_FREE")
    def test_energy(self):
        self.assertEqual(tariff_gate(dict(priceComponents=[dict(__typename="ConsumptionRate",formattedValue="€0.50/kWh")]))[0],"DIRECT_SIMPLE_ENERGY_OR_FLAT")
    def test_power(self):
        self.assertEqual(tariff_gate(dict(complexPricingDetail={"restrictions":[{"minPower":50}]}))[0],"EXPLICIT_POWER_OR_ELECTRICAL_CONDITION")
    def test_complex(self):
        self.assertEqual(tariff_gate(dict(complexPricingDetail={"restrictions":[{"durationRestrictions":{"minDurationSeconds":60}}]}))[0],"COMPLEX_RESTRICTIONS_REVIEW")
    def test_unknown(self):
        self.assertEqual(tariff_gate(dict(priceComponents=[dict(__typename="Other",formattedValue="€1")]))[0],"UNKNOWN_COMPONENT_TYPE")
    def test_time(self):
        self.assertEqual(tariff_gate(dict(priceComponents=[dict(__typename="TimeRate",formattedValue="€1/min")]))[0],"TIME_BASED_PRICE_REVIEW")
if __name__=="__main__":unittest.main()
