"""Offline tests of both historical AVIA Picoty PAN processors."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from v9_rebuild.avia_picoty_extract import run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source

CSV = ("id_station_itinerance,id_pdc_itinerance,nom_operateur,nom_enseigne,nom_station,puissance_nominale,tarification\n"
       "FR*PY2*P000001,FR*PY2*E000001,Picoty,AVIA VOLT,Fixture AVIA,50,\n"
       "FR*OTHER*P1,FR*OTHER*E1,Other,Other,Other site,50,\n")


class AviaPicotyExtractMigrationTests(unittest.TestCase):
    def test_exact_pan_extract_and_compact_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv = root / "fixture.csv"
            csv.write_text(CSV)
            out = root / "source"
            run(out, input_csv=csv)
            payload = validate_output(out)
            self.assertEqual(payload["counts"]["stationCount"], 1)
            self.assertEqual(payload["stations"][0]["pdcIds"], ["FR*PY2*E000001"])
            self.assertEqual(payload["stations"][0]["evses"][0]["panRaw"]["nom_operateur"], "Picoty")
            spec = next(row for row in read_sources() if row["id"] == "FR:avia_picoty_extract")
            def runner(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), input_csv=csv)
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, root / "artifacts", runner=runner)["status"], "ok")

    def test_empty_scope_is_valid_and_corrupt_index_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv = root / "fixture.csv"
            csv.write_text("id_station_itinerance,id_pdc_itinerance\nFR*OTHER*P1,FR*OTHER*E1\n")
            out = root / "source"
            run(out, input_csv=csv)
            self.assertEqual(validate_output(out)["stations"], [])
            index = out / "data/national/avia_volt_picoty_station_index.json"
            obj = json.loads(index.read_text())
            obj["counts"]["stationCount"] = 99
            index.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError, "contract invalid"):
                validate_output(out)

    def test_missing_input_rejected_without_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                run(Path(tmp) / "out", input_csv=Path(tmp) / "missing.csv")


if __name__ == "__main__":
    unittest.main()
