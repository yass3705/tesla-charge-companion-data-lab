import json
import unittest

from v9_rebuild.canonical import normalize_netherlands_dotnl


def station(station_id):
    return {"stationId": station_id, "countryCode": "NL", "partyId": "ABC",
            "operatorName": "Example CPO", "name": station_id,
            "coordinates": {"latitude": 52.0, "longitude": 5.0},
            "evses": [{"uid": "slot-1", "evseId": "NL*ABC*E1",
                       "connectors": [{"id": "1", "standard": "IEC_62196_T2",
                                       "powerType": "AC_3_PHASE", "powerKw": 22,
                                       "tariffKeys": ["NL:ABC:T1", "NL:ABC:ROAM", "NL:ABC:MISSING"]}]}]}


class NetherlandsDotnlCanonicalTests(unittest.TestCase):
    def test_official_identity_and_exact_raw_tariff_scope(self):
        tariff = {"tariffKey": "NL:ABC:T1", "countryCode": "NL", "partyId": "ABC",
                  "type": "REGULAR", "currency": "EUR", "elements": [{"priceComponents": [{"type": "ENERGY"}]}]}
        payload = {"schemaVersion": "1.0.0", "dataset": "dotnl", "stations": [station("S1"), station("S2")],
                   "tariffs": {"NL:ABC:T1": tariff,
                               "NL:ABC:ROAM": {**tariff, "type": "ROAMING"}}}
        result = normalize_netherlands_dotnl(payload, artifact_sha256="a" * 64)
        reordered = normalize_netherlands_dotnl({**payload, "stations": list(reversed(payload["stations"]))},
                                                 artifact_sha256="a" * 64)
        for section in ("stations", "evses", "connectors", "offers"):
            self.assertEqual(result[section], reordered[section])
        self.assertEqual(len({row["id"] for row in result["evses"]}), 2)
        self.assertEqual({row["officialEvseId"] for row in result["evses"]}, {"NL*ABC*E1"})
        self.assertEqual(result["connectors"][0]["officialConnectorId"], "1")
        self.assertEqual(len(result["offers"]), 2)
        self.assertEqual(result["offers"][0]["rawOffer"], {"tariffKey": "NL:ABC:T1"})
        self.assertEqual(result["tariffCatalog"]["NL:ABC:T1"], tariff)
        self.assertEqual(result["offers"][0]["calculationStatus"], "not_evaluated")
        self.assertNotIn("pricing", result["offers"][0])
        self.assertIn("NL:ABC:ROAM", result["connectors"][0]["rawSourceFields"]["tariffKeys"])
        changed = json.loads(json.dumps(payload))
        changed["stations"][0]["evses"][0]["connectors"][0]["id"] = ""
        with self.assertRaisesRegex(ValueError, "connector identity"):
            normalize_netherlands_dotnl(changed, artifact_sha256="a" * 64)


if __name__ == "__main__":
    unittest.main()
