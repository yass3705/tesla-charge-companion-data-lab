"""AVIA Picoty historic inventory migration on a local IRVE fixture."""

import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.cwd_script import run, validate_output
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
import avia_picoty_national as historical  # noqa: E402

CSV = ("id_station_itinerance,id_pdc_itinerance,nom_operateur,nom_station,puissance_nominale,coordonneesXY,tarification\n"
       "FR*PY2*P000001,FR*PY2*E000001,Picoty,Fixture AVIA,50,\"[2.35, 48.85]\",\n"
       "FR*OTHER*P1,FR*OTHER*E1,Other,Other site,50,\"[2.36, 48.86]\",\n")
META = {"resources": [{"title": "consolidation de la dernière version du schéma IRVE",
                       "format": "csv", "url": "https://fixture.invalid/irve.csv"}]}


class FixtureRunner:
    def __init__(self, fail=False):
        self.fail = fail

    def __call__(self, command, **kwargs):
        if self.fail:
            return SimpleNamespace(returncode=2)
        previous = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            def download(url, dest):
                dest.write_text(CSV, encoding="utf-8")
            with patch.object(historical, "get_json", return_value=META), patch.object(historical, "download", side_effect=download), patch("builtins.print"):
                historical.main()
        finally:
            os.chdir(previous)
        return SimpleNamespace(returncode=0)


class AviaPicotyMigrationTests(unittest.TestCase):
    def test_fixture_runs_historical_collector_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root / "source", "avia_picoty_inventory", runner=FixtureRunner())
            payload = validate_output(root / "source", "avia_picoty_inventory")
            self.assertEqual(len(payload["stations"]), 1)
            self.assertEqual(payload["stations"][0]["evseIds"], ["FR*PY2*E000001"])
            self.assertIsNone(payload["stations"][0]["directEurPerKwh"])
            spec = next(row for row in read_sources() if row["id"] == "FR:avia_picoty_inventory")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "avia_picoty_inventory", runner=FixtureRunner())
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_failure_and_corrupt_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "Historical avia_picoty_inventory method failed"):
                run(root / "failed", "avia_picoty_inventory", runner=FixtureRunner(fail=True))
            run(root / "source", "avia_picoty_inventory", runner=FixtureRunner())
            path = root / "source/data/national/avia_picoty_direct_stations_france.json.gz"
            path.write_bytes(b"broken")
            with self.assertRaises((OSError, gzip.BadGzipFile)):
                validate_output(root / "source", "avia_picoty_inventory")


if __name__ == "__main__":
    unittest.main()
