import unittest
from decimal import Decimal
from scripts.g66b5a_planner_gate import planner_session,invariant_envelope,congestion_evidence,PROOF
def s():
    return dict(protocol="planner-v1",startAt="2026-11-26T14:37:19.125Z",timeZone="Europe/Paris",energy="2.000000",durationMinutes="4.123456",chargingMinutes="3.123456",postChargeMinutes="1.000000",includeCongestionFees=True,chargeTimeline=[dict(offsetMinutes="0.000000",durationMinutes="1.123456",energyKwh="1.000000"),dict(offsetMinutes="1.123456",durationMinutes="2.000000",energyKwh="1.000000")])
def raw(time="0.00",parking="0.00"):
    return {"isChargingFree":False,"priceComponents":[{"__typename":t,"formattedValue":v} for t,v in (("ConsumptionRate","Consumption rate: €0.40 kWh"),("TimeRate","Time rate: €"+time+"/min"),("ParkingTimeRate","Time rate: €"+parking+"/min"),("ConnectionFee","Connection fee: €0.20"),("VAT","VAT rate: 0%"))],"complexPricingDetail":{"currency":"EUR","restrictions":[]}}
class Planner(unittest.TestCase):
    def test_fractional(self):self.assertEqual(planner_session(s())["charging"],"3.123456")
    def test_gap(self):
        a=s();a["chargeTimeline"][1]["offsetMinutes"]="1.123459"
        with self.assertRaises(ValueError):planner_session(a)
    def test_energy(self):
        a=s();a["energy"]="2.000005"
        with self.assertRaises(ValueError):planner_session(a)
    def test_missing_offset(self):
        with self.assertRaises(ValueError):planner_session(dict(s(),startAt="2026-11-26T14:37:19"))
    def test_empty(self):
        with self.assertRaises(ValueError):planner_session(dict(s(),chargeTimeline=[]))
    def test_congestion(self):
        self.assertEqual(congestion_evidence(raw()),PROOF)
        self.assertNotEqual(congestion_evidence(raw(time="0.01")),PROOF)
        self.assertNotEqual(congestion_evidence(raw(parking="0.01")),PROOF)
    def test_unknown(self):
        a=raw();a["priceComponents"][0]["extra"]=1
        self.assertNotEqual(congestion_evidence(a),PROOF)
    def test_fractional_oracle(self):
        prepared=({k:Decimal(v) for k,v in dict(energy=".4",time=".1",parking=".2",flat=".2").items()},[],None)
        state,parts=invariant_envelope(prepared,planner_session(s()),"NO_DECLARED_RESTRICTIONS")
        self.assertEqual(parts["total"],"1.512346")
    def test_ambiguous_duration(self):
        base={k:Decimal(v) for k,v in dict(energy=".4",time="0",parking="0",flat="0").items()}
        prepared=(base,[({"DURATION_BASED"},None,None,None,30,{"energy":Decimal(".5")})],None)
        self.assertEqual(invariant_envelope(prepared,planner_session(s()),"DURATION_BASED")[0],"INCALCULABLE_SEMANTICS")
    def test_clock_refused(self):self.assertIsNone(invariant_envelope(None,planner_session(s()),"TIME_BASED")[1])
if __name__=="__main__":unittest.main()
