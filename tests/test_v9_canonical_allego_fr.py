"""Frozen Allego France archive: preserve exact EVSE and raw tariff scope."""
import copy
import gzip
import hashlib
import json
import unittest
from pathlib import Path

from v9_rebuild.canonical_allego_fr import normalize_allego_fr


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/national/allego_direct_stations_france.json.gz"


class AllegoFranceCanonicalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = SOURCE.read_bytes()
        cls.sha = hashlib.sha256(raw).hexdigest()
        cls.archive = json.loads(gzip.decompress(raw))

    def test_full_archive_preserves_source_identity_without_price_promotion(self):
        result = normalize_allego_fr(self.archive, artifact_sha256=self.sha)
        source_evses = {evse["evseId"] for station in self.archive["stations"]
                        for evse in station["evses"]}
        self.assertEqual({evse["sourceEvseId"] for evse in result["evses"]}, source_evses)
        self.assertTrue(all(evse["officialEvseId"] == evse["sourceEvseId"]
                            for evse in result["evses"]))
        self.assertEqual(result["connectors"], [])
        self.assertTrue(all(offer["scope"]["connectorId"] is None and
                            offer["calculationStatus"] == "not_evaluated" and
                            "pricing" not in offer for offer in result["offers"]))
        self.assertEqual(result["source"]["artifactSha256"], self.sha)
        self.assertEqual(result, normalize_allego_fr(self.archive, artifact_sha256=self.sha))

    def test_identity_errors_fail_without_volume_threshold(self):
        one = copy.deepcopy(self.archive)
        one["stations"] = [one["stations"][0]]
        one["stations"][0]["evses"] = one["stations"][0]["evses"][:1]
        self.assertEqual(len(normalize_allego_fr(one, artifact_sha256=self.sha)["evses"]), 1)
        bad = copy.deepcopy(one)
        bad["stations"][0]["evses"][0]["stationId"] = "OTHER"
        with self.assertRaises(ValueError):
            normalize_allego_fr(bad, artifact_sha256=self.sha)
        bad = copy.deepcopy(one)
        bad["stations"][0]["evses"].append(copy.deepcopy(bad["stations"][0]["evses"][0]))
        with self.assertRaises(ValueError):
            normalize_allego_fr(bad, artifact_sha256=self.sha)
        with self.assertRaises(ValueError):
            normalize_allego_fr(one, artifact_sha256="0")


if __name__ == "__main__":
    unittest.main()
