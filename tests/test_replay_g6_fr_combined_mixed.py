import unittest,copy
from scripts.replay_g6_fr_combined_mixed import simplify
def comp(t,v):return {"__typename":t,"formattedValue":v}
E=comp("ConsumptionRate","Consumption rate: €0.53 kWh")
def restriction(types,components,lo=None,hi=None,start=None,end=None):
    return dict(restrictionTypes=types,priceComponents=components,dateRestrictions=None,weekdayRestrictions=None,durationRestrictions={"minDurationSeconds":lo,"maxDurationSeconds":hi} if "DURATION_BASED" in types else None,timeRestrictions={"startTime":start,"endTime":end} if "TIME_BASED" in types else None)
def raw():
    return dict(isChargingFree=False,priceComponents=[E,comp("TimeRate","Time rate: €0.00/min"),comp("VAT","VAT rate: 0%"),comp("ParkingTimeRate","Time rate: €0.00/min"),comp("ConnectionFee","Connection fee: €0.00")],complexPricingDetail=dict(currency="EUR",restrictions=[restriction([], [E]),restriction(["TIME_BASED","DURATION_BASED"],[E,comp("ParkingTimeRate","Time rate: €0.10/min")],600,None,"20:00:00","08:00:00"),restriction(["DURATION_BASED"],[E],None,600),restriction(["TIME_BASED","DURATION_BASED"],[E,comp("ParkingTimeRate","Time rate: €0.20/min")],600,None,"08:00:00","20:00:00")]))
class MixedTests(unittest.TestCase):
    def test_redundancy(self):
        a=raw();before=copy.deepcopy(a);_,_,w,p=simplify(a);self.assertEqual(a,before);self.assertEqual(p["thresholdSeconds"],600);self.assertEqual(len(w),2)
    def test_changed_rate(self):
        a=raw();a["complexPricingDetail"]["restrictions"][2]["priceComponents"]=[comp("ConsumptionRate","Consumption rate: €0.54 kWh")]
        with self.assertRaises(ValueError):simplify(a)
    def test_gap(self):
        a=raw();a["complexPricingDetail"]["restrictions"][3]["timeRestrictions"]["startTime"]="09:00:00"
        with self.assertRaises(ValueError):simplify(a)
    def test_different_threshold(self):
        a=raw();a["complexPricingDetail"]["restrictions"][3]["durationRestrictions"]["minDurationSeconds"]=601
        with self.assertRaises(ValueError):simplify(a)
    def test_omitted_positive(self):
        a=raw();a["priceComponents"][1]=comp("TimeRate","Time rate: €0.05/min")
        with self.assertRaises(ValueError):simplify(a)
