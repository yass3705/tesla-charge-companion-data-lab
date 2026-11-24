import unittest
from scripts.audit_irve_g5_final_exact import owner_class,technical_review
class FinalExactTests(unittest.TestCase):
    def s(self,**kw):
        return dict(plug_raw="CCS",plug="CCS",mode="DC",kw=50,has_price=1,tariff_signature="x",**kw)
    def test_same_site_identical(self):
        self.assertEqual(owner_class({("L","1"):[self.s()],("L","2"):[self.s()]},{"L":{"lat":1,"lon":2}}),"SAME_LOCATION_DISTINCT_EVSE_PK_IDENTICAL_PAYLOAD")
    def test_different_site(self):
        self.assertEqual(owner_class({("L","1"):[self.s()],("K","2"):[self.s()]},{"L":{"lat":1,"lon":2},"K":{"lat":2,"lon":2}}),"DISTINCT_LOCATIONS_DIFFERENT_COORDS")
    def test_missing_coords(self):
        self.assertEqual(owner_class({("L","1"):[self.s()],("K","2"):[self.s()]},{"L":{"lat":None,"lon":2},"K":{"lat":2,"lon":2}}),"DISTINCT_LOCATIONS_COORDINATES_MISSING")
    def test_type3c(self):
        self.assertEqual(technical_review({"plug":"TYPE2","mode":"AC"},{"plug":None,"mode":None},[{"plug_flags":{"prisetype3":"true"},"supported_types":["Type 2"]}],{"standard":{"name":"IEC_62196_T3C"}}),"TYPE3C_DECLARED_OUTSIDE_TCC_SCOPE")
    def test_other_supported_profile(self):
        self.assertEqual(technical_review({"plug":"EF","mode":"AC"},{"plug":"TYPE2","mode":"AC"},[{"plug_flags":{},"supported_types":["EF","Type 2"]}],{"standard":{"name":"IEC_62196_T2"}}),"SOURCE_TYPE_EXISTS_ON_OTHER_IRVE_PROFILE")
    def test_chademo(self):
        self.assertEqual(technical_review({"plug":"CCS","mode":"DC"},{"plug":"CHADEMO","mode":"DC"},[{"plug_flags":{"prisetypechademo":"true"},"supported_types":["CCS"]}],{"standard":{"name":"CHADEMO"}}),"CHADEMO_DECLARED_OUTSIDE_TCC_SCOPE")
if __name__=="__main__":unittest.main()
