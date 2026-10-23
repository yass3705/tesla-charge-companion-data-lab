import copy
import hashlib
import json
import unittest
from pathlib import Path

from v9_rebuild.canonical import normalize_zephyre_exact


ARCHIVE = Path(__file__).resolve().parents[1] / "data/operator_direct/zephyre_epowerdirect_exact_france_20260925.json"


class ZephyreCanonicalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = ARCHIVE.read_bytes()
        cls.payload = json.loads(raw)
        cls.sha = hashlib.sha256(raw).hexdigest()

    def test_archived_exact_scope_and_stable_identity(self):
        first = normalize_zephyre_exact(self.payload, artifact_sha256=self.sha)
        changed_order = copy.deepcopy(self.payload)
        changed_order["records"].reverse()
        second = normalize_zephyre_exact(changed_order, artifact_sha256="b" * 64)
        for section in ("stations", "evses", "connectors", "offers"):
            self.assertEqual([x["id"] for x in first[section]], [x["id"] for x in second[section]])
        evses = {x["id"]: x for x in first["evses"]}
        plugs = {x["id"]: x for x in first["connectors"]}
        for offer in first["offers"]:
            self.assertEqual(offer["sourceEvseId"], evses[offer["scope"]["evseId"]]["officialEvseId"])
            self.assertEqual(plugs[offer["scope"]["connectorId"]]["evseId"], offer["scope"]["evseId"])
            self.assertEqual(offer["calculationStatus"], "not_evaluated")
        self.assertTrue(all(x["sourceStationId"] is None for x in first["stations"]))
        self.assertTrue(all(x["officialConnectorId"] is None for x in first["connectors"]))

    def test_identity_and_country_errors_rejected(self):
        for field, value in (("evseId", "FR*OTHER*E1"), ("name", "")):
            altered = copy.deepcopy(self.payload)
            altered["records"][0][field] = value
            with self.assertRaises(ValueError):
                normalize_zephyre_exact(altered, artifact_sha256=self.sha)
        altered = copy.deepcopy(self.payload)
        altered["records"][0]["address"]["country"] = "DE"
        with self.assertRaises(ValueError):
            normalize_zephyre_exact(altered, artifact_sha256=self.sha)


if __name__ == "__main__":
    unittest.main()
