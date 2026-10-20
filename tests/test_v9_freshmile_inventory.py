"""Freshmile strict CPO inventory and regional pruning on frozen CSV fixtures."""

import csv
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from v9_rebuild.freshmile_inventory import BASE, FINAL, run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source


def rows():
    common = {"nom_operateur": "Freshmile", "nom_station": "Fixture Freshmile",
              "adresse_station": "1 rue Test 75001 Paris", "coordonneesXY": "[2.35,48.85]",
              "puissance_nominale": "22", "prise_type_2": "true", "paiement_acte": "true",
              "tarification": ""}
    return [{**common, "id_station_itinerance": "FRFR1P00001", "id_pdc_itinerance": "FRFR1E00001",
             "nom_amenageur": "Private fixture"},
            {**common, "id_station_itinerance": "FRFR1P00002", "id_pdc_itinerance": "FRFR1E00002",
             "nom_amenageur": "Bordeaux Metropole"},
            {**common, "id_station_itinerance": "FROTHP00003", "id_pdc_itinerance": "FROTHE00003",
             "nom_amenageur": "Private fixture"}]


class FreshmileMigrationTests(unittest.TestCase):
    def fixture(self, root, source_rows=None):
        path = root / "freshmile.csv"
        source_rows = rows() if source_rows is None else source_rows
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=source_rows[0].keys())
            writer.writeheader()
            writer.writerows(source_rows)
        return path

    def test_historical_chain_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.fixture(root)
            run(root / "source", input_csv=fixture)
            final = validate_output(root / "source")
            self.assertEqual(final["stats"]["stationCount"], 1)
            self.assertEqual(final["stats"]["excludedRegionalStationCount"], 1)
            self.assertEqual(final["stations"][0]["chargePoints"][0]["evseId"], "FRFR1E00001")
            spec = next(row for row in read_sources() if row["id"] == "FR:freshmile_inventory")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), input_csv=fixture)
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_empty_scope_and_sha_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.fixture(root, [rows()[2]])
            run(root / "source", input_csv=fixture)
            self.assertEqual(validate_output(root / "source")["stations"], [])
            (root / "source" / FINAL).write_bytes(b"bad")
            with self.assertRaises((OSError, gzip.BadGzipFile)):
                validate_output(root / "source")

    def test_missing_csv_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "inventory failed"):
                run(root / "source", input_csv=root / "missing.csv")
            self.assertFalse((root / "source" / FINAL).exists())


if __name__ == "__main__":
    unittest.main()
