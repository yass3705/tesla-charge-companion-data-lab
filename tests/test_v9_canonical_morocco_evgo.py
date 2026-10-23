import hashlib
import json
import unittest
from pathlib import Path

from v9_rebuild.canonical_morocco_evgo import normalize_morocco_evgo


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "reports/morocco/evgo/latest-production-stations.json"


class MoroccoEvgoCanonicalTest(unittest.TestCase):
    def test_archived_topology_keeps_native_identity_without_inferred_power_or_price(self):
        raw = ARCHIVE.read_bytes()
        payload = json.loads(raw)
        canonical = normalize_morocco_evgo(payload, artifact_sha256=hashlib.sha256(raw).hexdigest())
        self.assertEqual(canonical["source"]["id"], "MA:evgo")
        self.assertEqual(len(canonical["stations"]), len(payload["stations"]))
        self.assertEqual(len(canonical["evses"]), sum(len(s["evses"]) for s in payload["stations"]))
        self.assertEqual(canonical["offers"], [])
        self.assertTrue(all(e["officialEvseId"] is None and e["sourceEvseId"] for e in canonical["evses"]))
        self.assertTrue(all(c["powerKw"] is None and c["officialConnectorId"] is None
                            for c in canonical["connectors"]))
        self.assertEqual(canonical, normalize_morocco_evgo(payload, artifact_sha256=hashlib.sha256(raw).hexdigest()))

    def test_missing_native_connector_identity_fails(self):
        payload = json.loads(ARCHIVE.read_bytes())
        payload["stations"][0]["evses"][0]["connectors"][0].pop("id")
        with self.assertRaisesRegex(ValueError, "connector identity"):
            normalize_morocco_evgo(payload, artifact_sha256="a" * 64)


if __name__ == "__main__":
    unittest.main()
