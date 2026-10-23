import copy
import gzip
import hashlib
import json
import unittest
from pathlib import Path

from v9_rebuild.canonical import normalize_midhope_verified


ARCHIVE = Path(__file__).resolve().parents[1] / "data/national/uk_connected_kerb_midhope_verified_v9.json.gz"


class MidhopeCanonicalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = ARCHIVE.read_bytes()
        cls.payload = json.loads(gzip.decompress(raw))
        cls.sha = hashlib.sha256(raw).hexdigest()

    def test_archived_exact_identity_and_oracle_input_preserved(self):
        first = normalize_midhope_verified(self.payload, artifact_sha256=self.sha)
        modified = copy.deepcopy(self.payload)
        modified["sources"][0]["locations"][0]["evses"].reverse()
        second = normalize_midhope_verified(modified, artifact_sha256="b" * 64)
        for section in ("stations", "evses", "connectors", "offers"):
            self.assertEqual([row["id"] for row in first[section]], [row["id"] for row in second[section]])
        connectors = {row["id"]: row for row in first["connectors"]}
        evses = {row["id"]: row for row in first["evses"]}
        for offer in first["offers"]:
            raw = offer["rawOffer"]
            connector = connectors[offer["scope"]["connectorId"]]
            evse = evses[offer["scope"]["evseId"]]
            self.assertEqual(raw["connectorIds"], [connector["officialConnectorId"]])
            self.assertEqual(raw["evseIds"], [evse["officialEvseId"]])
            self.assertEqual(offer["calculationStatus"], "not_evaluated")
            self.assertIsNone(connector["powerKw"])

    def test_wrong_connector_scope_rejected(self):
        altered = copy.deepcopy(self.payload)
        offer = altered["sources"][0]["locations"][0]["evses"][0]["connectors"][0]["validatedV9Offer"]
        offer["connectorIds"] = ["another-connector"]
        with self.assertRaisesRegex(ValueError, "scope"):
            normalize_midhope_verified(altered, artifact_sha256=self.sha)


if __name__ == "__main__":
    unittest.main()
