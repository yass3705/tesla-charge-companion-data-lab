import unittest
from scripts.audit_irve_g5_tariff_schema import classify,walk
class SchemaTests(unittest.TestCase):
    def p(self,**kw):
        return dict(priceComponents=[{"__typename":"ConsumptionRate","formattedValue":"€0.50/kWh"}],**kw)
    def test_speed(self):
        self.assertEqual(classify(self.p(speed="RAPID"))[0],"DIRECT_SIMPLE_NO_OBSERVED_POWER_CONDITION")
    def test_unknown(self):
        self.assertEqual(classify(self.p(mystery=1))[0],"UNKNOWN_OR_CONFLICTING_SCHEMA_REVIEW")
    def test_power(self):
        self.assertEqual(classify(self.p(complexPricingDetail={"restrictions":[{"minPower":50}]}))[0],"POWER_CONDITION_REVIEW")
    def test_time(self):
        p={"priceComponents":[{"__typename":"TimeRate","formattedValue":"€0.1/min"}]}
        self.assertEqual(classify(p)[0],"DIRECT_CONDITIONAL_NO_OBSERVED_POWER_CONDITION")
    def test_duration(self):
        p=self.p(complexPricingDetail={"restrictions":[{"restrictionTypes":["DURATION"],"durationRestrictions":{"minDurationSeconds":60},"priceComponents":[{"__typename":"ParkingTimeRate","formattedValue":"€0.1/min"}]}]})
        self.assertEqual(classify(p)[0],"DIRECT_CONDITIONAL_NO_OBSERVED_POWER_CONDITION")
    def test_unknown_restriction(self):
        self.assertEqual(classify(self.p(complexPricingDetail={"restrictions":[{"restrictionTypes":["X"]}]}))[0],"UNKNOWN_OR_CONFLICTING_SCHEMA_REVIEW")
    def test_free(self):
        self.assertEqual(classify({"isChargingFree":True,"speed":"FAST"})[0],"DIRECT_FREE_NO_OBSERVED_POWER_CONDITION")
    def test_power_text(self):
        self.assertEqual(classify({"priceComponents":[{"__typename":"ConsumptionRate","formattedValue":"€0.5/kWh above 50 kW"}]})[0],"POWER_CONDITION_REVIEW")
    def test_inventory(self):
        self.assertIn(("connector.priceComponents[].__typename","str"),list(walk(self.p())))
if __name__=="__main__":unittest.main()
