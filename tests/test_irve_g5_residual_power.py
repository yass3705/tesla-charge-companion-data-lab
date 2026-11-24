import unittest
from scripts.audit_irve_g5_residual_power import metrics,raw_observation
class ResidualPowerTests(unittest.TestCase):
    def test_bands(self):
        for d,label in [(5,"<=5"),(5.01,"(5,15]"),(15,"(5,15]"),(15.01,"(15,30]"),(30,"(15,30]"),(50,"(30,50]"),(50.01,">50")]:
            self.assertEqual(metrics(100,100+d)["absolute_band"],label)
    def test_relative(self):
        self.assertEqual(metrics(50,65)["relative_pct_of_irve"],"30.000000")
        self.assertEqual(metrics(350,365)["relative_band"],"<=5%")
    def test_direction(self):
        self.assertEqual(metrics(320,380)["direction"],"SOURCE_ABOVE")
        self.assertEqual(metrics(350,300)["direction"],"SOURCE_BELOW")
    def test_candidate_search_only(self):
        self.assertTrue(metrics(150,165)["within_dc_candidate_search_band"])
        self.assertFalse(metrics(150,166)["within_dc_candidate_search_band"])
    def test_invalid(self):
        for a,b in [(0,10),(10,0),(10,10),(-1,10)]:
            with self.assertRaises(ValueError):metrics(a,b)
    def test_raw(self):
        self.assertEqual(raw_observation(["320"],320)[0],"RAW_NOMINAL_REPRODUCED")
    def test_watts(self):
        self.assertEqual(raw_observation(["320000"],320)[0],"RAW_UNIT_CONVERSION_REPRODUCED")
    def test_rounding(self):
        self.assertEqual(raw_observation(["150.04"],150)[0],"RAW_ONE_DECIMAL_ROUNDING_REPRODUCED")
    def test_conflict(self):
        self.assertEqual(raw_observation(["150","160"],150)[0],"RAW_PROJECTION_DIFFERENT")
if __name__=="__main__":unittest.main()
