import unittest
from scripts.audit_irve_g5_address_gps import address_relation,address_fields,valid_coords,compatible
class TestAddressGPS(unittest.TestCase):
    def test_missing(self): self.assertEqual(address_relation(None,"12 rue A"),"MISSING")
    def test_accents(self): self.assertEqual(address_relation("12 rue École","12 rue ecole"),"EXACT_TOKEN_MATCH")
    def test_prefix(self): self.assertEqual(address_relation("11 avenue Jean Jaurès","11 avenue Jean Jaurès, 78390 Bois-d'Arcy, 78073"),"STREET_PREFIX_REVIEW_ONLY")
    def test_number(self): self.assertEqual(address_relation("11 rue A","12 rue A, 75000 Paris"),"DIFFERENT_OR_UNRESOLVED")
    def test_prefix_not_city(self): self.assertEqual(address_relation("11 rue A","11 rue A bis"),"DIFFERENT_OR_UNRESOLVED")
    def test_fields(self): self.assertEqual(address_fields({"tariff":{"evses":[{"address":"not site"}],"address":"site"},"metadata":{"city":"Paris"}}),{"tariff.address":"site","metadata.city":"Paris"})
    def test_coords(self): self.assertTrue(valid_coords((48.,2.)));self.assertFalse(valid_coords((None,2.)));self.assertFalse(valid_coords((91.,2.)))
    def test_missing_competitor(self): self.assertTrue(compatible({"plug":"TYPE2","mode":"AC","kw":22},{"plug":None,"mode":None,"kw":None}))
    def test_no_relaxation(self): self.assertFalse(compatible({"plug":"TYPE2","mode":"AC","kw":22},{"plug":"TYPE2","mode":"AC","kw":23}))
    def test_plug(self): self.assertFalse(compatible({"plug":"TYPE2","mode":"AC","kw":22},{"plug":"CCS","mode":"DC","kw":22}))
