import copy
import gzip
import hashlib
import json
import unittest
from pathlib import Path

from v9_rebuild.canonical import normalize_atlante_italy


ARCHIVE = Path(__file__).resolve().parents[1] / "data/national/atlante_direct_stations_italy_latest.json.gz"


class CanonicalAtlanteItalyTest(unittest.TestCase):
    def test_archived_exact_scope_and_stable_ids(self):
        raw = ARCHIVE.read_bytes()
        source = json.loads(gzip.decompress(raw))
        first = normalize_atlante_italy(source, artifact_sha256=hashlib.sha256(raw).hexdigest())
        reordered = copy.deepcopy(source)
        reordered["locations"].reverse()
        second = normalize_atlante_italy(reordered, artifact_sha256="b" * 64)
        for section in ("cpos", "stations", "evses", "connectors", "offers"):
            self.assertEqual([row["id"] for row in first[section]], [row["id"] for row in second[section]])
        source_evses = {item["evseId"] for station in source["locations"] for item in station["connectors"]}
        self.assertEqual({row["officialEvseId"] for row in first["evses"]}, source_evses)
        owners = {row["id"]: row["evseId"] for row in first["connectors"]}
        self.assertTrue(all(owners[offer["scope"]["connectorId"]] == offer["scope"]["evseId"] for offer in first["offers"]))
        self.assertTrue(all(row["officialConnectorId"] is None for row in first["connectors"]))
        self.assertTrue(all(row["calculationStatus"] == "not_evaluated" for row in first["offers"]))

    def test_mismatched_tariff_identifier_rejected(self):
        source = json.loads(gzip.decompress(ARCHIVE.read_bytes()))
        source["locations"][0]["connectors"][0]["tariffs"][0]["identifiers"]["evseId"] = "another-EVSE"
        with self.assertRaisesRegex(ValueError, "connector scope"):
            normalize_atlante_italy(source, artifact_sha256="a" * 64)


if __name__ == "__main__":
    unittest.main()
