import gzip
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.swiss_avia_guest import NATIONAL, OUTPUT, REPORT, run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source


def national_file(root):
    target = root / NATIONAL
    target.parent.mkdir(parents=True)
    national = {"Operators": [{"OperatorID": "CH*AVI", "ChargingStations": [{"ChargingStationId": "AVIA-1", "Evses": [{"EvseID": "CH*AVI*EKOS002242118CH*1*1", "Accessibility": "Free publicly accessible"}]}]}]}
    target.write_bytes(gzip.compress(json.dumps(national).encode(), mtime=0))
    return target


def fixture_runner(command, **kwargs):
    spec = importlib.util.spec_from_file_location("fixture_avia_collector", command[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.KEY = "fixture"
    module.OUT = Path("data/switzerland/avia-guest-direct-tariffs.json")
    module.SLEEP = 0
    module.FAILURE_RETRY_PASSES = 0
    location = {"id": "location-1"}
    module.map_locations = lambda: ([location], [])
    module.detail = lambda lid: {"locationId": "AVIA-1", "locationName": "Archived AVIA", "evses": [{"id": "internal-1", "evseId": "CH*AVI*EKOS002242118CH*1*1", "connectors": [{"evseConnectorId": "connector-1", "max_electric_power": 50}]}]}
    module.simulate = lambda lid, evse, conn: {"simulatedLocationPricing": [{"pricePerKwh": {"amountInclVat": 0.65, "currency": "CHF"}}]}
    old = Path.cwd()
    try:
        os.chdir(kwargs["cwd"])
        return SimpleNamespace(returncode=module.main())
    finally:
        os.chdir(old)


class SwissAviaGuestTest(unittest.TestCase):
    def test_collector_and_reconciliation_run_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            national = national_file(root / "source")
            out = root / "out"
            out.mkdir()
            run(out, national, runner=fixture_runner)
            report = validate_output(out)
            self.assertEqual(report["counts"]["matchedNationalEvseCount"], 1)
            self.assertEqual(json.loads((out / OUTPUT).read_text())["connectors"][0]["evseId"], "CH*AVI*EKOS002242118CH*1*1")
            self.assertTrue((out / REPORT).is_file())
            data = json.loads((out / OUTPUT).read_text())
            data["failures"] = [{"stage": "simulate"}]
            (out / OUTPUT).write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "incomplete"):
                validate_output(out)

    def test_no_results_is_not_a_volume_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            national = national_file(root / "source")
            out = root / "out"
            out.mkdir()
            def empty_runner(command, **kwargs):
                spec = importlib.util.spec_from_file_location("fixture_avia_empty", command[1])
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.KEY = "fixture"
                module.OUT = OUTPUT
                module.map_locations = lambda: ([], [])
                old = Path.cwd()
                try:
                    os.chdir(kwargs["cwd"])
                    return SimpleNamespace(returncode=module.main())
                finally:
                    os.chdir(old)
            run(out, national, runner=empty_runner)
            self.assertEqual(validate_output(out)["counts"]["missingNationalEvseCount"], 1)

    def test_technical_failure_rejects_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            national = national_file(root / "source")
            out = root / "out"
            out.mkdir()
            with self.assertRaisesRegex(RuntimeError, "collector failed"):
                run(out, national, runner=lambda *a, **k: SimpleNamespace(returncode=1))
            self.assertFalse((out / REPORT).exists())

    def test_national_sha_and_partial_map_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            national = national_file(root / "source")
            out = root / "out"
            out.mkdir()
            run(out, national, runner=fixture_runner)
            (out / NATIONAL).write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                validate_output(out)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            national = national_file(root / "source")
            out = root / "out"
            out.mkdir()
            def partial_runner(command, **kwargs):
                spec = importlib.util.spec_from_file_location("fixture_avia_partial", command[1])
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.KEY = "fixture"
                module.OUT = OUTPUT
                module.map_locations = lambda: ([], [{"stage": "map", "error": "HTTP 503"}])
                old = Path.cwd()
                try:
                    os.chdir(kwargs["cwd"])
                    return SimpleNamespace(returncode=module.main())
                finally:
                    os.chdir(old)
            with self.assertRaisesRegex(RuntimeError, "collector failed"):
                run(out, national, runner=partial_runner)
            self.assertFalse((out / REPORT).exists())

    def test_orchestrator_with_preserved_secret_name(self):
        spec = next(row for row in read_sources() if row["id"] == "CH:avia_guest")
        def adapter_runner(command, **kwargs):
            out = Path(command[command.index("--out") + 1])
            national = Path(command[command.index("--national") + 1])
            run(out, national, runner=fixture_runner)
            return SimpleNamespace(returncode=0)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"AVIA_APIM_SUBSCRIPTION_KEY": "fixture"}):
            result = run_source(spec, Path(tmp), attempts=1, runner=adapter_runner)
            self.assertEqual(result["status"], "ok")


if __name__ == "__main__":
    unittest.main()
