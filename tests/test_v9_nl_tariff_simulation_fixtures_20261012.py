import importlib.util
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
SPEC=importlib.util.spec_from_file_location("dotnl_fixtures",ROOT/"scripts/v9_nl_direct_tariff_simulation_fixtures_20261012.py")
m=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

class FrozenDotnlSimulationFixturesTest(unittest.TestCase):
    def test_group_multiplicity_conserves_active_connectors(self):
        fixture={
          "generatedAt":"2026-10-11T10:32:38Z",
          "tariffs":{"t1":{"type":"AD_HOC_PAYMENT","currency":"EUR","elements":[{"priceComponents":[{"type":"ENERGY","priceInclVat":0.3,"stepSize":1}]}]}},
          "stations":[{"stationId":"NL:A:1","partyId":"A","coordinates":{"latitude":52.0,"longitude":5.0},
            "evses":[{"evseId":"NL*A*E1","status":"AVAILABLE","connectors":[
             {"id":"c1","standard":"IEC_62196_T2","powerKw":11,"tariffKeys":["t1"]},
             {"id":"c2","standard":"IEC_62196_T2","powerKw":22,"tariffKeys":["t1"]}
            ]}]}]
        }
        out=m.fixtures(fixture)
        self.assertEqual(out["compiledConnectors"],2)
        self.assertEqual(out["uniquePowerConnectorTariffGroups"],2)
        self.assertEqual(out["noTariffReference"],0)
        self.assertEqual(sorted(g["powerKw"] for g in out["groups"]),[11,22])
        self.assertFalse(out["publishedToTcc"])

    def test_price_missing_does_not_become_free(self):
        fixture={"generatedAt":"2026-10-11T10:32:38Z","tariffs":{},"stations":[
         {"stationId":"NL:A:1","partyId":"A","coordinates":{"latitude":52,"longitude":5},
          "evses":[{"status":"AVAILABLE","evseId":"A1","connectors":[
           {"standard":"IEC_62196_T2","powerKw":22,"tariffKeys":[]},
           {"standard":"IEC_62196_T2_COMBO","powerKw":150,"tariffKeys":["not-in-catalog"]}
          ]}]}]}
        with self.assertRaisesRegex(ValueError,"fixture reconciliation"):
            m.fixtures(fixture)

if __name__=="__main__":
    unittest.main()
