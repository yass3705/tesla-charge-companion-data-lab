import copy
import hashlib
import json
import unittest
from pathlib import Path

from v9_rebuild.canonical import normalize_belib


ARCHIVE = Path(__file__).resolve().parents[1] / "data/national/belib_stations_paris.json"


class CanonicalBelibTest(unittest.TestCase):
    def test_archived_physical_scope_and_stable_keys(self):
        raw = ARCHIVE.read_bytes()
        source = json.loads(raw)
        first = normalize_belib(source, artifact_sha256=hashlib.sha256(raw).hexdigest())
        reordered = copy.deepcopy(source)
        reordered["stations"].reverse()
        second = normalize_belib(reordered, artifact_sha256="b" * 64)
        for section in ("cpos", "stations", "evses", "connectors", "offers"):
            self.assertEqual([row["id"] for row in first[section]], [row["id"] for row in second[section]])
        original_evses = {evse for station in source["stations"] for config in station["configurations"] for evse in config["evseIds"]}
        self.assertEqual({row["officialEvseId"] for row in first["evses"]}, original_evses)
        self.assertTrue(all(row["officialConnectorId"] is None for row in first["connectors"]))
        connector_owner = {row["id"]: row["evseId"] for row in first["connectors"]}
        self.assertTrue(all(connector_owner[offer["scope"]["connectorId"]] == offer["scope"]["evseId"] for offer in first["offers"]))
        self.assertTrue(all(offer["calculationStatus"] == "not_evaluated" for offer in first["offers"]))
        self.assertEqual(first["stations"][0]["networkBrand"], "Belib'")
        self.assertEqual(first["cpos"][0]["sourceOperatorId"], "TOTALENERGIES")

    def test_missing_configuration_and_foreign_offer_rejected(self):
        source = json.loads(ARCHIVE.read_bytes())
        source["stations"][0]["configurations"][0]["evseIds"] = None
        with self.assertRaisesRegex(ValueError, "configuration schema"):
            normalize_belib(source, artifact_sha256="a" * 64)


if __name__ == "__main__":
    unittest.main()
