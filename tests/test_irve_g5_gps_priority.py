import unittest,json
from scripts.audit_irve_g5_gps_priority import shortlist,priority,perfect,classify_site,explicit_ids,gitblob
def p(k=22,t="TYPE2",m="AC"):return {"kw":k,"plug":t,"mode":m}
class TestPriority(unittest.TestCase):
    def test_shortlist(self):
        x={"allocation":"BOTH_UNMATCHED","criteria":json.dumps({"evse_uniqueness":"PASS"}),"diagnostic":"[]"}
        self.assertTrue(shortlist(x));self.assertTrue(priority(x,{"national_pdc_count":"2","source_evse_count":"2"}))
        self.assertFalse(priority(x,{"national_pdc_count":"2","source_evse_count":"3"}))
    def test_occupied(self):self.assertFalse(shortlist({"allocation":"OCCUPIED","criteria":"{}","diagnostic":"[]"}))
    def test_perfect(self):self.assertEqual(perfect({"a":{"x"},"b":{"y"}}),{"a":"x","b":"y"})
    def test_no_perfect(self):self.assertIsNone(perfect({"a":{"x"},"b":{"x"}}))
    def test_unique(self):self.assertEqual(classify_site({"a":[p(22)],"b":[p(50)]},{"x":[p(22)],"y":[p(50)]})[0],"UNIQUE_TECHNICAL_BIJECTION")
    def test_multiple(self):self.assertEqual(classify_site({"a":[p()],"b":[p()]},{"x":[p()],"y":[p()]})[0],"MULTIPLE_TECHNICAL_BIJECTIONS")
    def test_missing_competes(self):self.assertEqual(classify_site({"a":[p(22)],"b":[p(50)]},{"x":[p(None)],"y":[p(None)]})[0],"MULTIPLE_TECHNICAL_BIJECTIONS")
    def test_no_relaxation(self):self.assertEqual(classify_site({"a":[p()]},{"x":[p(23)]})[0],"NO_COMPLETE_TECHNICAL_BIJECTION")
    def test_group_count(self):self.assertEqual(classify_site({"a":[p()]},{"x":[p()],"y":[p()]})[0],"GROUP_COUNT_DIFFERS")
    def test_id_fields(self):self.assertEqual(explicit_ids({"evseId":"FR*XX*E1","price":1,"name":"FRYYE2"}),{"evseId":{"FRXXE1"}})
    def test_blob(self):self.assertEqual(gitblob(b""),"e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")
