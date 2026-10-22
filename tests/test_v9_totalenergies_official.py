"""Offline replay of the preserved TotalEnergies parser and artifact gate."""

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from v9_rebuild import totalenergies_official as adapter
from v9_rebuild.orchestrator import read_sources, run_source


def fixture_runner(*, missing_price=False, http_error=False):
    def run(command, **_):
        spec = importlib.util.spec_from_file_location("totalenergies_fixture", command[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        pages = {
            "stationPricing": "0,52 € TTC/kWh jusqu'à 50 kW 0,62 € TTC/kWh plus de 50 kW 5 mars 2025 nous ne faisons pas de frais de session",
            "stationIdle": "45 minutes 0,50 € / min tant que votre véhicule reste branché",
            "chargePlus": "160 000 3,90 € 15% 50kW hors Corse 19,90 €",
            "chargePlusHome": "19,90 €",
            "zenPoints": "<table><tr><td>TotalEnergies</td><td>RELAIS DE SILLY</td><td>1 rue</td><td>92100</td><td>BOULOGNE-BILLANCOURT</td><td>50</td><td>FR*HPC*1</td></tr></table>",
            "cityAmp": "5€/mois 0,45 0,40 0,54 0,07 30 minutes 8h à 20h 20h à 8h hors station-service",
            "cpoEmsp": "CPO eMSP les tarifs fixes par un eMSP peuvent être différents",
        }
        if missing_price:
            pages["stationPricing"] = pages["stationPricing"].replace("0,52", "0,53")
        def fetch(url):
            key = next(k for k, v in module.SOURCES.items() if v == url)
            return (503 if http_error and key == "cityAmp" else 200), pages[key]
        previous = sys.argv
        try:
            sys.argv = command[1:]
            with patch.object(module, "fetch", side_effect=fetch), redirect_stdout(io.StringIO()):
                module.main()
        except RuntimeError:
            return subprocess.CompletedProcess(command, 1)
        finally:
            sys.argv = previous
        return subprocess.CompletedProcess(command, 0)
    return run


class TotalEnergiesOfficialTests(unittest.TestCase):
    def test_small_inventory_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            adapter.run(base / "direct", runner=fixture_runner())
            result = adapter.validate_output(base / "direct")
            self.assertEqual(result["zenEligibleInventory"]["officialTableRowCount"], 1)
            self.assertIsNone(result["mobilityProvider"]["chargePlus"]["card"]["currentPromoPurchaseEur"])
            self.assertEqual(result["stationValidationSamples"][0]["evseIdsSample"], ["FR*HPC*1"])
            source = next(s for s in read_sources() if s["id"] == "FR:totalenergies_official")
            def process(command, **_):
                adapter.run(Path(command[-1]), runner=fixture_runner())
                return subprocess.CompletedProcess(command, 0)
            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_missing_marker_and_http_error_reject_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for label, runner in (("marker", fixture_runner(missing_price=True)), ("http", fixture_runner(http_error=True))):
                with self.assertRaisesRegex(RuntimeError, "failed"):
                    adapter.run(base / label, runner=runner)
                self.assertFalse((base / label / adapter.OUTPUT).exists())


if __name__ == "__main__":
    unittest.main()
