import unittest
from scripts.audit_irve_g5_restriction_replay import classify, normalize, RECOGNIZED
class RestrictionReplayTests(unittest.TestCase):
    def p(self, kinds, **fields):
        return {"priceComponents":[{"__typename":"ConsumptionRate","formattedValue":"€0.5/kWh"}],
                "complexPricingDetail":{"restrictions":[{"restrictionTypes":kinds,**fields}]}}
    def check(self,kinds,**fields):
        return classify(self.p(kinds,**fields))
    def test_duration_alias(self):
        p=self.p(["DURATION_BASED"],durationRestrictions={"minDurationSeconds":60,"maxDurationSeconds":None})
        self.assertEqual(classify(p)[0],RECOGNIZED)
        self.assertEqual(p["complexPricingDetail"]["restrictions"][0]["restrictionTypes"],["DURATION_BASED"])
    def test_time_alias(self):
        self.assertEqual(self.check(["TIME_BASED"],timeRestrictions={"startTime":"07:00","endTime":"20:00:00"})[0],RECOGNIZED)
    def test_both(self):
        self.assertEqual(self.check(["TIME_BASED","DURATION_BASED"],timeRestrictions={"startTime":"07:00","endTime":"20:00"},durationRestrictions={"maxDurationSeconds":60})[0],RECOGNIZED)
    def test_inverted_duration(self):
        self.assertIn("durationRestrictions:NON_INCREASING_DURATION_BOUNDS",self.check(["DURATION_BASED"],durationRestrictions={"minDurationSeconds":61,"maxDurationSeconds":60})[1])
    def test_duration_bool_float(self):
        for x in (True,-1,1.5):
            self.assertIn("durationRestrictions:INVALID_DURATION_SECONDS",self.check(["DURATION_BASED"],durationRestrictions={"minDurationSeconds":x})[1])
    def test_missing_duration(self):
        self.assertIn("durationRestrictions:MISSING_OR_INVALID_FIELD",self.check(["DURATION_BASED"])[1])
    def test_orphan_field(self):
        self.assertIn("durationRestrictions:TYPE_FIELD_CARDINALITY",self.check([],durationRestrictions={"minDurationSeconds":0})[1])
    def test_duplicate_type(self):
        self.assertIn("durationRestrictions:TYPE_FIELD_CARDINALITY",self.check(["DURATION","DURATION_BASED"],durationRestrictions={"minDurationSeconds":0})[1])
    def test_unknown_type(self):
        self.assertIn("UNKNOWN_RESTRICTION_TYPE:OTHER",self.check(["DURATION_BASED","OTHER"],durationRestrictions={"minDurationSeconds":0})[1])
    def test_invalid_time(self):
        for x in ("25:00","07:60","07:00:60",None,"7:00"):
            self.assertIn("timeRestrictions:INVALID_OR_MISSING_CLOCK_BOUND",self.check(["TIME_BASED"],timeRestrictions={"startTime":x,"endTime":"20:00"})[1])
    def test_equal_time(self):
        self.assertIn("timeRestrictions:EQUAL_CLOCK_BOUNDS_AMBIGUOUS",self.check(["TIME_BASED"],timeRestrictions={"startTime":"07:00","endTime":"07:00:00"})[1])
    def test_overnight_not_calculated(self):
        p=self.p(["TIME_BASED"],timeRestrictions={"startTime":"20:00","endTime":"07:00"})
        self.assertEqual(classify(p)[0],RECOGNIZED)
        self.assertIn("OVERNIGHT_WINDOW",normalize(p)[2][0]["notes"][0])
    def test_unknown_field(self):
        self.assertIn("durationRestrictions:UNKNOWN_RESTRICTION_FIELD",self.check(["DURATION_BASED"],durationRestrictions={"minDurationSeconds":0,"other":0})[1])
    def test_power_unchanged(self):
        p=self.p(["DURATION_BASED"],durationRestrictions={"minDurationSeconds":0})
        p["complexPricingDetail"]["restrictions"][0]["minPower"]=50
        self.assertEqual(classify(p)[0],"POWER_CONDITION_REVIEW")
if __name__=="__main__":unittest.main()
