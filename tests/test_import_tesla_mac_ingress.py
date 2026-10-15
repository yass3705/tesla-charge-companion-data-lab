import hashlib
import json
import unittest
from pathlib import Path

from scripts.import_tesla_mac_ingress import validate, INGRESS, INGRESS_PATH

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data/tesla/mac/history"
CURRENT = ROOT / "data/tesla/mac/catalogue.json"


def ready(raw, run, date):
    return {"schemaVersion": 1, "status": "ready", "sourceRepository": INGRESS,
            "cataloguePath": INGRESS_PATH, "catalogueCommit": "a" * 40,
            "catalogueSha256": hashlib.sha256(raw).hexdigest(), "catalogueBytes": len(raw),
            "stationCount": len(json.loads(raw)), "sourcePublishedAt": date + "T12:00:00Z",
            "lot": "representative-historic", "updaterRunId": run,
            "countryDates": {code: date for code in ("BE", "CH", "DE", "ES", "FR", "GB", "IT", "LU", "MA", "NL", "PT")},
            "countriesUpdated": ["DE"], "provenance": "historic Mac-published bytes", "sucComparison": "unavailable"}


class ImportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first = (HISTORY / "c37e7717d4a19036b49e6c129c2bd00485b900f6.json").read_bytes()
        cls.second = CURRENT.read_bytes()

    def test_two_historic_catalogues_and_rollback_pin(self):
        prior = {"stationCount": 1178, "countryDates": ready(self.first, 1, "2026-10-08")["countryDates"]}
        first = validate(ready(self.first, 1, "2026-10-08"), self.first, prior, self.first)
        second = validate(ready(self.second, 2, "2026-10-09"), self.second, first, self.first)
        self.assertEqual((first["stationCount"], second["stationCount"]), (1178, 1179))
        self.assertEqual(first["catalogueSha256"], "cac26eb46010c01b9cf09a82511cb9be436f1b23d3579f1ca0706ba4f6b26c7e")
        self.assertEqual(second["catalogueSha256"], "363af2e80f05a01015889f2be1ece4055c74c3f75d1b804fca66f51d01ef57c5")
        self.assertEqual(len(json.loads(self.first)), 1178)  # old pin remains usable

    def test_wrong_hash_and_incomplete_catalogue_preserve_prior(self):
        prior = {"stationCount": 1178, "countryDates": ready(self.first, 1, "2026-10-08")["countryDates"]}
        item = ready(self.second, 2, "2026-10-09")
        item["catalogueSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            validate(item, self.second, prior, self.first)
        item = ready(self.first, 2, "2026-10-09")
        item["stationCount"] = 1179
        with self.assertRaisesRegex(ValueError, "incomplete"):
            validate(item, self.first, prior, self.first)

    def test_older_run_and_date_rollback_rejected(self):
        prior = {"stationCount": 1178, "updaterRunId": 3,
                 "countryDates": ready(self.first, 1, "2026-10-09")["countryDates"]}
        with self.assertRaisesRegex(ValueError, "Older Mac run"):
            validate(ready(self.second, 2, "2026-10-10"), self.second, prior, self.first)
        prior["updaterRunId"] = 1
        with self.assertRaisesRegex(ValueError, "date rollback"):
            validate(ready(self.second, 2, "2026-10-08"), self.second, prior, self.first)


if __name__ == "__main__":
    unittest.main()
