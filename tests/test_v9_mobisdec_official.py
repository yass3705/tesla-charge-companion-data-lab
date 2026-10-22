"""Offline replay of the existing MobiSDEC page and IRVE CSV parser."""

import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from v9_rebuild import mobisdec_official as adapter
from v9_rebuild.orchestrator import read_sources, run_source


def fixture_runner(*, http_error=False, bad_schema=False, bad_price=False):
    def run(command, **_):
        spec = importlib.util.spec_from_file_location("mobisdec_fixture", command[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        mob = ("MobiSDEC SDEC ÉNERGIE service public 0,42 €/kWh 0,47 €/kWh 0,52 €/kWh "
               "0,57 €/kWh 0,62 €/kWh 10 € par badge QR code application Mobisdec Carte Bancaire "
               "recharge terminée depuis 15min 0,21 €/min minuit à 7h00 badges d’autres opérateurs")
        if bad_price:
            mob = mob.replace("0,42 €/kWh", "0,43 €/kWh")
        header = "id_station_itinerance,id_pdc_itinerance,nom_station,adresse_station,nom_operateur,puissance_nominale\n"
        csv = header + "FRS14P1,FRS14E1,TEST STATION,Caen,Load Stations,50\n"
        if bad_schema:
            csv = "wrong,columns\nvalue,value\n"
        def fetch(url, **_):
            if url == module.MOBISDEC_URL:
                return mob.encode(), 200
            if url == module.SDEC_MOBILITY_URL:
                return b"SDEC Energie Mobilite", (503 if http_error else 200)
            if url == module.SDEC_2026_PDF:
                raise RuntimeError("archived PDF endpoint retired")
            if url == module.DATASET_PAGE:
                return b"MOBISDEC Load Stations schema-irve-statique", 200
            if url == module.DATASET_CSV:
                return csv.encode(), 200
            raise AssertionError(url)
        previous = sys.argv
        previous_cwd = Path.cwd()
        try:
            sys.argv = command[1:]
            os.chdir(Path(command[1]).parents[1])
            with patch.object(module, "fetch_bytes", side_effect=fetch), \
                 patch.object(module, "render_html_bytes", return_value=(mob.encode(), 200)), \
                 redirect_stdout(io.StringIO()):
                module.main()
        except RuntimeError:
            return subprocess.CompletedProcess(command, 1)
        finally:
            sys.argv = previous
            os.chdir(previous_cwd)
        return subprocess.CompletedProcess(command, 0)
    return run


class MobiSDECOfficialTests(unittest.TestCase):
    def test_small_csv_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            adapter.run(base / "direct", runner=fixture_runner())
            result = adapter.validate_output(base / "direct")
            self.assertEqual(result["classification"]["officialTechnicalDatasetRows"], 1)
            self.assertEqual(result["technical"]["stationExamplesFromOfficialDataset"]["caen"]["id_pdc_itinerance"], "FRS14E1")
            self.assertIsNone(result["technical"]["stationExamplesFromOfficialDataset"]["bayeux"])
            source = next(s for s in read_sources() if s["id"] == "FR:mobisdec_official")
            def process(command, **_):
                adapter.run(Path(command[-1]), runner=fixture_runner())
                return subprocess.CompletedProcess(command, 0)
            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_http_schema_and_price_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for label, runner in (("http", fixture_runner(http_error=True)),
                                  ("schema", fixture_runner(bad_schema=True)),
                                  ("price", fixture_runner(bad_price=True))):
                with self.assertRaisesRegex(RuntimeError, "failed"):
                    adapter.run(base / label, runner=runner)
                self.assertFalse((base / label / adapter.OUTPUT).exists())


if __name__ == "__main__":
    unittest.main()
