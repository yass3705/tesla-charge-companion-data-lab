import copy
import hashlib
import json
import unittest
from pathlib import Path

from v9_rebuild.canonical import normalize_driveco_evse


ARCHIVE = Path(__file__).resolve().parents[1] / "data/operator_direct/driveco_evse_tariffs.json"


class DrivecoCanonicalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = ARCHIVE.read_bytes()
        cls.payload = json.loads(raw)
        cls.sha = hashlib.sha256(raw).hexdigest()

    def test_archived_scope_and_missing_tariffs(self):
        first = normalize_driveco_evse(self.payload, artifact_sha256=self.sha)
        reordered = copy.deepcopy(self.payload)
        reordered["resolved"].reverse()
        reordered["unresolved"].reverse()
        second = normalize_driveco_evse(reordered, artifact_sha256="b" * 64)
        for section in ("cpos", "stations", "evses", "connectors", "offers"):
            self.assertEqual([row["id"] for row in first[section]], [row["id"] for row in second[section]])
        offers = {offer["sourceEvseId"]: offer for offer in first["offers"]}
        self.assertTrue(all(row["evseId"] in offers for row in self.payload["resolved"]))
        self.assertTrue(all(row["evseId"] not in offers for row in self.payload["unresolved"]))
        self.assertTrue(all(offer["calculationStatus"] == "not_evaluated" for offer in offers.values()))
        self.assertTrue(all(connector["officialConnectorId"] is None for connector in first["connectors"]))
        self.assertTrue(all(connector["plugType"] is None for connector in first["connectors"]))
        self.assertEqual({cpo["name"] for cpo in first["cpos"]}, {"DRIVECO", "DRIVECO Partner Network"})

    def test_missing_identity_and_fee_semantics_fail_closed(self):
        for field, value in (("evseId", ""), ("networkClass", "unknown"), ("feeSemantics", None)):
            altered = copy.deepcopy(self.payload)
            altered["resolved"][0][field] = value
            with self.assertRaises(ValueError):
                normalize_driveco_evse(altered, artifact_sha256=self.sha)


if __name__ == "__main__":
    unittest.main()
