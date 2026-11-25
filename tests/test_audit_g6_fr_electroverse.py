import unittest
from scripts.audit_g6_fr_electroverse import inspect_tariff,parse_components

def component(t,v):return {"__typename":t,"formattedValue":v}
def simple():
    return {"pk":1,"kilowatts":22,"speed":"FAST","standard":{"name":"IEC_62196_T2"},"isChargingFree":False,
        "priceComponents":[component("ConsumptionRate","Consumption rate: €0.40 kWh"),component("TimeRate","Time rate: €0.00/min"),component("ParkingTimeRate","Time rate: €0.00/min"),component("ConnectionFee","Connection fee: €0.60"),component("VAT","VAT rate: 0%")],
        "complexPricingDetail":{"currency":"EUR","restrictions":[{"restrictionTypes":[],"dateRestrictions":None,"timeRestrictions":None,"durationRestrictions":None,"weekdayRestrictions":None,"priceComponents":[component("ConsumptionRate","Consumption rate: €0.40 kWh")]}]}}
class TestG6Audit(unittest.TestCase):
    def test_simple_fixture(self):
        r=inspect_tariff(simple());self.assertEqual(r["audit_status"],"SIMPLE_ENERGY_FLAT_ORACLE_CANDIDATE");self.assertEqual(r["fixture_10kwh_eur_unrounded"],"4.60")
    def test_date_not_silently_ignored(self):
        c=simple();r=c["complexPricingDetail"]["restrictions"][0];r.update(restrictionTypes=["DATE_BASED"],dateRestrictions={"startDate":"2025-04-07","endDate":None})
        a=inspect_tariff(c);self.assertIn("DATE_APPLICABILITY_AND_BOUNDARY_REVIEW",a["reasons"]);self.assertEqual(a["fixture_10kwh_eur_unrounded"],"")
    def test_free_positive_conflict(self):
        c=simple();c["isChargingFree"]=True;self.assertIn("FREE_FLAG_POSITIVE_PRICE_CONTRADICTION",inspect_tariff(c)["reasons"])
    def test_no_default_currency(self):
        c=simple();c["complexPricingDetail"]["currency"]=None;self.assertIn("CURRENCY_NOT_PROVEN_EUR",inspect_tariff(c)["reasons"])
    def test_units_strict(self):
        a,e=parse_components([component("ConsumptionRate","Consumption rate: €0.40/min")],"BASE");self.assertFalse(a);self.assertTrue(e)
    def test_unrestricted_conflict(self):
        c=simple();c["complexPricingDetail"]["restrictions"][0]["priceComponents"][0]["formattedValue"]="Consumption rate: €0.70 kWh";self.assertIn("BASE_UNRESTRICTED_RULE_DISAGREEMENT",inspect_tariff(c)["reasons"])
    def test_parking_not_ignored(self):
        c=simple();c["priceComponents"][2]["formattedValue"]="Time rate: €0.20/min";self.assertIn("CHARGING_PARKING_CLOCK_AND_ROUNDING_REVIEW",inspect_tariff(c)["reasons"])
    def test_missing_base_dimension(self):
        c=simple();c["priceComponents"].pop();self.assertIn("BASE_COMPONENTS_INCOMPLETE",inspect_tariff(c)["reasons"])
