"""Frozen Bump source and compiled rules retain exact EVSE scope."""
import copy
import unittest

from scripts.build_v9_canonical_batch import read_route
from v9_rebuild.canonical_bump import normalize_bump_exact
from v9_rebuild.canonical_registry import BY_SOURCE


class BumpCanonicalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload, cls.sha, _ = read_route(BY_SOURCE["FR:bump_direct_exact"], "FR:bump_direct_exact")

    def test_full_archive_preserves_scope_and_quarantine(self):
        result = normalize_bump_exact(self.payload, artifact_sha256=self.sha)
        source_points = {p["idPdcItinerance"] for st in self.payload["source"]["stations"]
                         for p in st["points"]}
        self.assertEqual({row["sourceEvseId"] for row in result["evses"]}, source_points)
        self.assertEqual(result["connectors"], [])
        self.assertTrue(all(row["officialEvseId"] == row["sourceEvseId"]
                            for row in result["evses"]))
        self.assertTrue(all(offer["scope"]["connectorId"] is None and
                            offer["calculationStatus"] == "not_evaluated" and
                            "pricing" not in offer for offer in result["offers"]))
        self.assertEqual(len(result["offers"]), len({offer["sourceEvseId"] for offer in result["offers"]}))
        self.assertEqual(result, normalize_bump_exact(self.payload, artifact_sha256=self.sha))

    def test_missing_and_mismatched_compiled_scope_fail(self):
        source = copy.deepcopy(self.payload)
        source["compiled"]["directOffers"][0]["evseIds"][0] = "FRUNKNOWN"
        with self.assertRaises(ValueError):
            normalize_bump_exact(source, artifact_sha256=self.sha)
        source = copy.deepcopy(self.payload)
        source["compiled"]["sourceEvidence"]["sourceGeneratedAt"] = "other"
        with self.assertRaises(ValueError):
            normalize_bump_exact(source, artifact_sha256=self.sha)

    def test_smaller_valid_archive_has_no_volume_gate(self):
        source = copy.deepcopy(self.payload)
        source["source"]["stations"] = source["source"]["stations"][:1]
        ids = {p["idPdcItinerance"] for p in source["source"]["stations"][0]["points"]}
        source["compiled"]["directOffers"] = [
            {**offer, "evseIds": [identity for identity in offer["evseIds"] if identity in ids]}
            for offer in source["compiled"]["directOffers"]]
        source["compiled"]["directOffers"] = [offer for offer in source["compiled"]["directOffers"] if offer["evseIds"]]
        source["compiled"]["quarantinedSourceRankableEvse"] = [
            row for row in source["compiled"]["quarantinedSourceRankableEvse"] if row["evseId"] in ids]
        result = normalize_bump_exact(source, artifact_sha256=self.sha)
        self.assertEqual(len(result["stations"]), 1)


if __name__ == "__main__":
    unittest.main()
