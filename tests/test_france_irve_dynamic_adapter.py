#!/usr/bin/env python3
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import france_irve_dynamic_adapter as adapter  # noqa: E402


FIELDS = [
    "id_station_itinerance", "id_pdc_itinerance", "etat_pdc",
    "occupation_pdc", "horodatage",
]


class FranceIrveDynamicAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "dynamic.csv"

    def write_rows(self, rows):
        with self.path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)

    def test_occupancy_is_never_exported(self):
        self.write_rows([{
            "id_station_itinerance": "FR*EXA*S1",
            "id_pdc_itinerance": "FR*EXA*E1",
            "etat_pdc": "en_service",
            "occupation_pdc": "occupé",
            "horodatage": "2026-08-28T08:00:00Z",
        }])
        payload = adapter.normalize_dynamic(str(self.path))
        self.assertEqual(payload["records"][0]["status"], "in_service")
        self.assertNotIn("occupation_pdc", payload["records"][0])
        self.assertFalse(payload["rules"]["occupationPdcUsed"])

    def test_newest_duplicate_wins(self):
        self.write_rows([
            {
                "id_station_itinerance": "FR*EXA*S1",
                "id_pdc_itinerance": "FR*EXA*E1",
                "etat_pdc": "hors_service",
                "occupation_pdc": "",
                "horodatage": "2026-08-28T07:00:00Z",
            },
            {
                "id_station_itinerance": "FR*EXA*S1",
                "id_pdc_itinerance": "FR*EXA*E1",
                "etat_pdc": "en_service",
                "occupation_pdc": "",
                "horodatage": "2026-08-28T08:00:00Z",
            },
        ])
        payload = adapter.normalize_dynamic(str(self.path))
        self.assertEqual(payload["records"][0]["status"], "in_service")
        self.assertEqual(payload["summary"]["newerDuplicateSelected"], 1)

    def test_same_timestamp_conflict_is_omitted(self):
        self.write_rows([
            {
                "id_station_itinerance": "FR*EXA*S1",
                "id_pdc_itinerance": "FR*EXA*E1",
                "etat_pdc": "hors_service",
                "occupation_pdc": "",
                "horodatage": "2026-08-28T08:00:00Z",
            },
            {
                "id_station_itinerance": "FR*EXA*S1",
                "id_pdc_itinerance": "FR*EXA*E1",
                "etat_pdc": "en_service",
                "occupation_pdc": "",
                "horodatage": "2026-08-28T08:00:00Z",
            },
        ])
        payload = adapter.normalize_dynamic(str(self.path))
        self.assertEqual(payload["records"], [])
        self.assertEqual(payload["summary"]["sameTimestampConflicts"], 1)

    def test_unknown_state_is_not_exported(self):
        self.write_rows([{
            "id_station_itinerance": "FR*EXA*S1",
            "id_pdc_itinerance": "FR*EXA*E1",
            "etat_pdc": "inconnu",
            "occupation_pdc": "libre",
            "horodatage": "2026-08-28T08:00:00Z",
        }])
        payload = adapter.normalize_dynamic(str(self.path))
        self.assertEqual(payload["records"], [])
        self.assertEqual(payload["summary"]["unknownState"], 1)


if __name__ == "__main__":
    unittest.main()
