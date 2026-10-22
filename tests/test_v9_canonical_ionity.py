import copy
import gzip
import hashlib
import json
import unittest
from pathlib import Path

from v9_rebuild.canonical import normalize_ionity


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "FR": "data/national/ionity_direct_stations_france.json.gz",
    "IT": "data/national/ionity_direct_stations_italy.json.gz",
    "DE": "data/national/ionity_direct_stations_germany.json.gz",
    "GB": "data/national/ionity_direct_stations_uk.json.gz",
}


class CanonicalIonityTest(unittest.TestCase):
    def test_archived_sources_and_scope(self):
        for country, name in FILES.items():
            with self.subTest(country=country):
                raw = (ROOT / name).read_bytes()
                source = json.loads(gzip.decompress(raw))
                result = normalize_ionity(source, artifact_sha256=hashlib.sha256(raw).hexdigest())
                self.assertEqual(len(result["stations"]), len(source["locations"]))
                self.assertEqual(len(result["connectors"]), sum(len(x["connectors"]) for x in source["locations"]))
                self.assertTrue(all(c["officialConnectorId"] is None for c in result["connectors"]))
                self.assertTrue(all(e["officialEvseId"] is None or e["officialEvseId"] == e["sourceEvseId"] for e in result["evses"]))
                self.assertTrue(all(o["scope"]["connectorId"] for o in result["offers"]))

    def test_missing_price_keeps_connector_and_reordering_stable(self):
        raw = (ROOT / FILES["FR"]).read_bytes()
        source = json.loads(gzip.decompress(raw))
        source["locations"] = [copy.deepcopy(source["locations"][0])]
        source["locations"][0]["connectors"] = source["locations"][0]["connectors"][:2]
        source["locations"][0]["connectors"][0].pop("pricePerKwhEur", None)
        first = normalize_ionity(source, artifact_sha256="a" * 64)
        self.assertEqual(len(first["connectors"]), 2)
        self.assertEqual(len(first["offers"]), 1)
        source["locations"][0]["connectors"].reverse()
        second = normalize_ionity(source, artifact_sha256="b" * 64)
        for section in ("stations", "evses", "connectors", "offers"):
            self.assertEqual(first[section], second[section])

    def test_foreign_cpo_and_bad_sha_rejected(self):
        raw = (ROOT / FILES["FR"]).read_bytes()
        source = json.loads(gzip.decompress(raw))
        source["locations"] = [copy.deepcopy(source["locations"][0])]
        source["locations"][0]["cpoIdentifier"] = "FOREIGN"
        with self.assertRaisesRegex(ValueError, "ownership"):
            normalize_ionity(source, artifact_sha256="a" * 64)
        with self.assertRaisesRegex(ValueError, "SHA"):
            normalize_ionity(source, artifact_sha256="bad")


if __name__ == "__main__":
    unittest.main()
