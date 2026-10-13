import importlib.util
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sp=importlib.util.spec_from_file_location("agrigo",ROOT/"scripts/v9_nl_agrigo_site_tier_scope_20261012.py")
mod=importlib.util.module_from_spec(sp)
sp.loader.exec_module(mod)

class AGOTest(unittest.TestCase):
    def test_exact_60kw_boundary_does_not_assume_tier(self):
        self.assertIn("AMBIGUOUS",mod.classify("CCS",60.0))
        self.assertEqual(mod.classify("CCS",55),"DC_22_TO_UNDER_60_KW_CANDIDATE")
        self.assertEqual(mod.classify("CCS",120),"DC_OVER_60_KW_CANDIDATE")
        self.assertIn("CONTEXT_REQUIRED",mod.classify("TYPE_2",11))
        self.assertIn("CONTEXT_REQUIRED",mod.classify("TYPE_2",22))

    def test_nonactive_chademo_excluded_and_site_not_auto_priced(self):
        data={"generatedAt":"2026-10-12T10:56:00Z","stations":[{
            "partyId":"AGO","stationId":"NL:AGO:AAA",
            "coordinates":{"latitude":52.1,"longitude":5.1},
            "evses":[{"evseId":"NL*AGO*E1","status":"AVAILABLE","connectors":[
              {"id":"c1","standard":"IEC_62196_T2","powerKw":11},
              {"id":"c2","standard":"IEC_62196_T2_COMBO","powerKw":60},
              {"id":"c3","standard":"CHADEMO","powerKw":50}
            ]},{"evseId":"NL*AGO*E2","status":"UNKNOWN","connectors":[
              {"standard":"IEC_62196_T2","powerKw":22}
            ]}]
        }]}
        out=mod.inventory(data)
        self.assertEqual(out["totalActiveType2Ccs"],2)
        self.assertFalse(out["pricingAssigned"])
        self.assertFalse(out["publishedToTcc"])
        self.assertEqual(sum(x["active"] for x in out["byKindPower"]),2)
if __name__=="__main__":unittest.main()
