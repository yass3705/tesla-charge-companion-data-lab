import unittest
from scripts.audit_g66b2_active_alignment import active_compact,compare_lanes
class ActiveTest(unittest.TestCase):
    def test_exact_filter_preserves_keys(self):
        rows=[["s","n","a",1,2,"op",3,0,[["group1","IRVE · Type 2 22 kW","AC",22,2,[],["a","b"]],["group2","IRVE · CCS 50 kW","DC",50,2,[],["a","c"]]],"date","op"]]
        r=active_compact(rows,{"a","c"})
        self.assertEqual(r[0][6],2); self.assertEqual(r[0][8][0][0],"group1");self.assertEqual(r[0][8][0][6],["a"]);self.assertEqual(r[0][8][1][6],["a","c"]); self.assertEqual(rows[0][6],3)
    def test_no_invented_active(self):
        with self.assertRaises(ValueError): active_compact([],{"unknown"})
    def test_empty_station_removed(self):
        self.assertEqual(active_compact([["s","n","a",1,2,"op",1,0,[["g","IRVE · EF 3 kW","AC",3,1,[],["a"]]],"d","op"]],set()),[])
    def test_lane_changed_target(self):
        n={"stations":[{"id":"s","sourceStationId":"A","cpoId":"x"}],"evses":[{"id":"e","stationId":"s","officialEvseId":"E"}],"connectors":[]}
        m={"matches":[{"offerId":"o","nationalEvseId":"e","nationalStationId":"s","nationalConnectorId":None}],"unmatched":[]}
        n2=dict(n,stations=[dict(n["stations"][0],sourceStationId="B")])
        self.assertEqual(compare_lanes(m,m,n,n2,("offerId",),"Direct")[0]["state"],"CHANGED_TARGET_REVIEW")
if __name__=="__main__": unittest.main()
