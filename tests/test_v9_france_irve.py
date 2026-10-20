"""Offline national IRVE static, dynamic and exact-ID audit chain."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from v9_rebuild.france_irve import INPUT, STATIC, run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source

STATIC_CSV = ("id_station_itinerance,id_pdc_itinerance,nom_station,latitude,longitude,nom_operateur,puissance_nominale,prise_type_combo_ccs\n"
              "FR*ABC*S01,FR*ABC*E01,Fixture,48.85,2.35,Fixture CPO,50,true\n")
DYNAMIC_CSV = ("id_pdc_itinerance,etat_pdc,horodatage\n"
               "FR*ABC*E01,en_service,2026-10-20T00:00:00Z\n")


class FranceIRVEMigrationTests(unittest.TestCase):
    def fixtures(self, root: Path) -> tuple[Path, Path]:
        static = root / "static.csv"
        dynamic = root / "dynamic.csv"
        static.write_text(STATIC_CSV, encoding="utf-8")
        dynamic.write_text(DYNAMIC_CSV, encoding="utf-8")
        return static, dynamic

    def test_complete_chain_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            static, dynamic = self.fixtures(root)
            run(root / "source", static_csv=static, dynamic_csv=dynamic)
            manifest = validate_output(root / "source")
            self.assertEqual(manifest["stationCount"], 1)
            self.assertEqual(manifest["pdcCount"], 1)
            spec = next(row for row in read_sources() if row["id"] == "FR:irve_national")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), static_csv=static, dynamic_csv=dynamic)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")

    def test_corrupt_sha_and_failed_dynamic_do_not_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            static, dynamic = self.fixtures(root)
            run(root / "last_good", static_csv=static, dynamic_csv=dynamic)
            prior = (root / "last_good" / STATIC / "manifest.json").read_bytes()
            (root / "last_good" / INPUT / "static.csv").write_text("corrupt", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "static IRVE technical contract"):
                validate_output(root / "last_good")
            dynamic.write_text("bad-header\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Historical national IRVE chain failed"):
                run(root / "failed", static_csv=static, dynamic_csv=dynamic)
            self.assertEqual((root / "last_good" / STATIC / "manifest.json").read_bytes(), prior)


if __name__ == "__main__":
    unittest.main()
