import copy
import gzip
import hashlib
import json
import unittest
from pathlib import Path

from v9_rebuild.canonical_germany_catalog import normalize_germany_catalog


def fixture():
    return {"schemaVersion": "0.6.0", "countryCode": "DE",
            "dataset": "germany-national-non-tesla-catalog-staging-direct-cpo",
            "scope": {"bnetzaIsNationalBaseline": True, "tariffsRankable": False},
            "sites": [{"id": "bnetza-site:fixture", "countryCode": "DE", "operator": "Fixture",
                       "coordinates": {"latitude": 52.5, "longitude": 13.4},
                       "evseIds": ["DE*FIX*E1", "DE*FIX*E2"], "maxConnectionPowerKw": 150,
                       "declaredChargePoints": 8, "pricing": {"rawAfirTariffs": [{"fixture": 99}]}}]}


class GermanyCatalogTest(unittest.TestCase):
    def normalize(self, payload):
        return normalize_germany_catalog(payload, artifact_sha256="a" * 64)

    def test_preserves_inventory_without_inferred_topology_or_prices(self):
        source = fixture()
        original = copy.deepcopy(source)
        result = self.normalize(source)
        self.assertEqual(source, original)
        self.assertEqual(result["stations"][0]["rawSourceFields"], source["sites"][0])
        self.assertEqual({r["officialEvseId"] for r in result["evses"]}, {"DE*FIX*E1", "DE*FIX*E2"})
        self.assertEqual(result["connectors"], [])
        self.assertEqual(result["offers"], [])
        self.assertTrue(all("powerKw" not in r for r in result["evses"]))

    def test_missing_evse_and_tariff_never_remove_station(self):
        source = fixture()
        source["sites"][0]["evseIds"] = []
        source["sites"][0]["pricing"] = None
        result = self.normalize(source)
        self.assertEqual(len(result["stations"]), 1)
        self.assertEqual(result["evses"], [])

    def test_stable_keys_and_distinct_station_scopes(self):
        source = fixture()
        other = copy.deepcopy(source["sites"][0])
        other["id"] = "bnetza-site:other"
        source["sites"].append(other)
        first = self.normalize(source)
        source["sites"].reverse()
        for row in source["sites"]:
            row["evseIds"].reverse()
        second = self.normalize(source)
        for section in ("cpos", "stations", "evses"):
            self.assertEqual([r["id"] for r in first[section]], [r["id"] for r in second[section]])
        self.assertEqual(len({r["id"] for r in first["evses"]}), 4)

    def test_rejects_invalid_identity_and_country(self):
        for field, value in [("id", "unknown"), ("countryCode", "FR"), ("evseIds", [None])]:
            source = fixture()
            source["sites"][0][field] = value
            with self.assertRaises(ValueError):
                self.normalize(source)
        source = fixture()
        source["sites"].append(copy.deepcopy(source["sites"][0]))
        with self.assertRaises(ValueError):
            self.normalize(source)

    def test_real_archive_preserves_all_source_sites_and_fields(self):
        raw = Path("data/national/germany_non_tesla_catalog_staging_direct_cpo.json.gz").read_bytes()
        source = json.loads(gzip.decompress(raw))
        result = normalize_germany_catalog(source, artifact_sha256=hashlib.sha256(raw).hexdigest())
        by_id = {row["id"]: row for row in source["sites"]}
        self.assertEqual({r["sourceStationId"] for r in result["stations"]}, set(by_id))
        for row in result["stations"]:
            self.assertEqual(row["rawSourceFields"], by_id[row["sourceStationId"]])
        self.assertEqual(len(result["evses"]), sum(len(set(r["evseIds"])) for r in source["sites"]))
        self.assertEqual(result["connectors"], [])
        self.assertEqual(result["offers"], [])


if __name__ == "__main__":
    unittest.main()
