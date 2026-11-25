import unittest
from scripts.audit_irve_g5_final_tariff import homogeneity,unique_scope,verified
from scripts.audit_irve_g5_restriction_replay import classify
class TestTariff(unittest.TestCase):
 def test_homogeneous(self):self.assertEqual(homogeneity(["a","a"]),"SAME_RAW_SIGNATURE")
 def test_heterogeneous(self):self.assertEqual(homogeneity(["a","b"]),"DIFFERENT_RAW_SIGNATURES")
 def test_missing(self):self.assertEqual(homogeneity(["a",None]),"MISSING_OR_UNVERIFIED")
 def test_no_raw(self):self.assertFalse(verified({},None))
 def test_unique(self):
  x={"kw":22,"plug":"TYPE2","mode":"AC"};self.assertTrue(unique_scope(x,x,[x],[x]))
 def test_ambiguous(self):
  x={"kw":22,"plug":"TYPE2","mode":"AC"};self.assertFalse(unique_scope(x,x,[x,x],[x]))
 def test_date_held(self):
  c={"isChargingFree":False,"priceComponents":[{"__typename":"ConsumptionRate","formattedValue":"0.4 €/kWh"}],"complexPricingDetail":{"currency":"EUR","restrictions":[{"restrictionTypes":["DATE_BASED"],"dateRestrictions":{"startDate":"2026-01-01","endDate":"2026-12-31"}}]}};self.assertIn("UNKNOWN_RESTRICTION_TYPE:DATE_BASED",classify(c)[1])
