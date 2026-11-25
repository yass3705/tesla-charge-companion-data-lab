import unittest,copy
from scripts.replay_g6_fr_free import free_gate
def sample():
    return {"isChargingFree":True,"complexPricingDetail":{"currency":"EUR","restrictions":[]},"priceComponents":[{"__typename":t,"formattedValue":v} for t,v in [
        ("ConsumptionRate","Consumption rate: €0.00 kWh"),("TimeRate","Time rate: €0.00/min"),("ParkingTimeRate","Time rate: €0.00/min"),("ConnectionFee","Connection fee: €0.00"),("VAT","VAT rate: 0%")]]}
class TestFreeGate(unittest.TestCase):
    def test_complete_zero(self):
        self.assertEqual(free_gate(sample()),(True,"FREE_FLAG_EXPLICIT_ZERO_COMPONENTS"))
    def test_nonzero_each_component(self):
        for i in range(5):
            s=sample();c=s["priceComponents"][i];c["formattedValue"]=c["formattedValue"].replace("0.00","0.01").replace("0%","1%")
            self.assertFalse(free_gate(s)[0])
    def test_missing(self):
        s=sample();s["priceComponents"].pop();self.assertFalse(free_gate(s)[0])
    def test_duplicate(self):
        s=sample();s["priceComponents"].append(copy.deepcopy(s["priceComponents"][0]));self.assertFalse(free_gate(s)[0])
    def test_unknown(self):
        s=sample();s["priceComponents"][0]["extraFee"]=1;self.assertFalse(free_gate(s)[0])
    def test_restriction(self):
        s=sample();s["complexPricingDetail"]["restrictions"]=[{"restrictionTypes":["DATE_BASED"]}];self.assertFalse(free_gate(s)[0])
    def test_false_flag(self):
        s=sample();s["isChargingFree"]=False;self.assertFalse(free_gate(s)[0])
    def test_currency(self):
        s=sample();s["complexPricingDetail"]["currency"]="GBP";self.assertFalse(free_gate(s)[0])
