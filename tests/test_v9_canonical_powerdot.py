"""Archived Powerdot identities remain source-scoped and raw-only."""
import gzip
import hashlib
import json
import unittest
from pathlib import Path

from v9_rebuild.canonical_powerdot import normalize_powerdot


ARCHIVE = Path(__file__).resolve().parents[1] / "data/national/powerdot_direct_france.json.gz"
SHA = "a" * 64


def fixture():
    return {"generatedAt": "2026-10-01T00:00:00Z",
            "source": {"sourceType": "direct_cpo_public_adhoc_api", "operator": "Power Dot France"},
            "chargers": [{"ok": False, "chargerName": "failed"},
                         {"ok": True, "location": {"countryCode": "FR", "uid": "location-1",
                                                     "name": "Fixture", "latitude": 48.8, "longitude": 2.3},
                          "charger": {"chargerName": "charger-1", "connectors": [
                              {"connectorNumber": 1, "evseNumber": 1, "physicalReference": "plug-1",
                               "maxPowerKw": 22, "tariff": {"id": "tariff-1", "elements": []}},
                              {"connectorNumber": 2, "evseNumber": 1, "physicalReference": None,
                               "maxPowerKw": 22, "tariff": None}]},
                          "irvePdcIds": ["FR*PDC*source-unmapped"]}]}


class PowerdotCanonicalTests(unittest.TestCase):
    def test_fixture_exact_scope_and_unknown_official_identity(self):
        result = normalize_powerdot(fixture(), artifact_sha256=SHA)
        self.assertEqual([len(result[name]) for name in ("stations", "evses", "connectors", "offers")],
                         [1, 1, 2, 1])
        evse = result["evses"][0]
        self.assertIsNone(evse["officialEvseId"])
        self.assertEqual(evse["rawSourceFields"]["irvePdcIdsUnmapped"], ["FR*PDC*source-unmapped"])
        offer = result["offers"][0]
        self.assertEqual(offer["scope"]["connectorId"],
                         next(row["id"] for row in result["connectors"] if row["sourceConnectorId"] == "plug-1"))
        self.assertEqual(offer["calculationStatus"], "not_evaluated")
        self.assertEqual(offer["rawOffer"], {"id": "tariff-1", "elements": []})
        self.assertIsNone(next(row for row in result["connectors"]
                               if row["sourceConnectorId"] is None)["officialConnectorId"])

    def test_bad_power_and_duplicate_source_connector_rejected(self):
        bad = fixture()
        bad["chargers"][1]["charger"]["connectors"][0]["maxPowerKw"] = -1
        with self.assertRaisesRegex(ValueError, "power"):
            normalize_powerdot(bad, artifact_sha256=SHA)
        duplicate = fixture()
        duplicate["chargers"][1]["charger"]["connectors"][1]["connectorNumber"] = 1
        with self.assertRaises(ValueError):
            normalize_powerdot(duplicate, artifact_sha256=SHA)

    def test_full_archived_source_technical_integrity(self):
        raw = ARCHIVE.read_bytes()
        payload = json.loads(gzip.decompress(raw))
        result = normalize_powerdot(payload, artifact_sha256=hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["source"]["artifactSha256"], hashlib.sha256(raw).hexdigest())
        self.assertTrue(all(row["officialEvseId"] is None for row in result["evses"]))
        self.assertTrue(all(row["calculationStatus"] == "not_evaluated" for row in result["offers"]))
        connector_ids = {row["id"] for row in result["connectors"]}
        self.assertTrue(all(row["scope"]["connectorId"] in connector_ids for row in result["offers"]))


if __name__ == "__main__":
    unittest.main()
