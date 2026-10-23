import copy
import gzip
import hashlib
import json
import unittest
from pathlib import Path

from v9_rebuild.canonical import normalize_ozecar


ARCHIVE = Path(__file__).resolve().parents[1] / "data/ozecar/france/ozecar-france-current.json.gz"


class OzecarCanonicalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = ARCHIVE.read_bytes()
        cls.payload = json.loads(gzip.decompress(raw))
        cls.sha = hashlib.sha256(raw).hexdigest()

    def test_archived_identity_and_unresolved_evses(self):
        first = normalize_ozecar(self.payload, artifact_sha256=self.sha)
        reversed_payload = copy.deepcopy(self.payload)
        reversed_payload["records"].reverse()
        second = normalize_ozecar(reversed_payload, artifact_sha256="b" * 64)
        for section in ("stations", "evses", "connectors", "offers"):
            self.assertEqual([row["id"] for row in first[section]], [row["id"] for row in second[section]])
        evses = {row["id"]: row for row in first["evses"]}
        offer_evses = {evses[offer["scope"]["evseId"]]["sourceEvseId"] for offer in first["offers"]}
        self.assertTrue(all(row["evseKey"] not in offer_evses for row in self.payload["records"] if not row["live"]["resolved"]))
        self.assertTrue(all(offer["scope"]["connectorId"] is None for offer in first["offers"]))
        self.assertTrue(all(offer["calculationStatus"] == "not_evaluated" for offer in first["offers"]))
        self.assertTrue(all(row["officialConnectorId"] is None and row["powerKw"] is None for row in first["connectors"]))
        self.assertTrue(all(isinstance(row["latitude"], float) and isinstance(row["longitude"], float) for row in first["stations"]))

    def test_cross_evse_offer_and_country_rejected(self):
        bad = copy.deepcopy(self.payload)
        bad["records"][0]["live"]["evse"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "scope"):
            normalize_ozecar(bad, artifact_sha256=self.sha)
        bad = copy.deepcopy(self.payload)
        bad["records"][0]["irve"]["nom_operateur"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "operator"):
            normalize_ozecar(bad, artifact_sha256=self.sha)


if __name__ == "__main__":
    unittest.main()
