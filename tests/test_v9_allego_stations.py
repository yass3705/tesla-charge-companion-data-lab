"""Offline execution of Allego's preserved three-step DXP station chain."""

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.allego_stations import DATA, SCRIPTS, run, validate_output
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
try:
    import selenium  # noqa: F401
except ModuleNotFoundError:
    selenium = types.ModuleType("selenium")
    selenium.webdriver = types.ModuleType("selenium.webdriver")
    chrome = types.ModuleType("selenium.webdriver.chrome")
    options = types.ModuleType("selenium.webdriver.chrome.options")
    options.Options = object
    sys.modules.update({"selenium": selenium, "selenium.webdriver": selenium.webdriver,
                        "selenium.webdriver.chrome": chrome, "selenium.webdriver.chrome.options": options})

import allego_dxp_national as dxp  # noqa: E402
import allego_normalize_v8 as normalize  # noqa: E402
import allego_coordinate_fallbacks_v8 as fallback  # noqa: E402


EVSE = {"evseId": "FRALLEGO8001301", "stationId": "FRSITEFIXTURE", "stationName": "Fixture Allego",
        "address": "Rue Test", "coordinates": [48.0, 2.0], "powerKwPublished": 150.0,
        "powerKw": 150.0, "kind": "DC", "source": "allego-data-gouv"}


class OfflineRunner:
    def __init__(self, fail_at=None):
        self.fail_at = fail_at
        self.seen = []

    def __call__(self, command, **kwargs):
        name = Path(command[1]).name
        self.seen.append(name)
        if name == self.fail_at:
            return SimpleNamespace(returncode=2)
        prior = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            if name == SCRIPTS[0]:
                def resolved(row, key):
                    return {**row, "dxpStatus": 200, "isOwnNetwork": True,
                            "allDirectRateCandidatesEurPerKwh": [0.39], "feeCandidates": [],
                            "directEurPerKwh": 0.39, "rankableDirect": True, "blockingReason": None}
                with patch.object(dxp, "capture_public_client_key", return_value="fixture-key"), \
                     patch.object(dxp, "fetch_inventory", return_value=([EVSE], 1)), \
                     patch.object(dxp, "resolve_evse", side_effect=resolved), patch("builtins.print"):
                    dxp.main()
            elif name == SCRIPTS[1]:
                with patch("builtins.print"):
                    normalize.main()
            else:
                with patch("builtins.print"):
                    fallback.main()
        finally:
            os.chdir(prior)
        return SimpleNamespace(returncode=0)


class AllegoStationMigrationTests(unittest.TestCase):
    def test_real_chain_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = OfflineRunner()
            run(root / "source", runner=runner)
            self.assertEqual(tuple(runner.seen), SCRIPTS)
            payload = validate_output(root / "source")
            self.assertEqual(payload["evses"][0]["evseId"], EVSE["evseId"])
            self.assertEqual(payload["stations"][0]["evses"][0], payload["evses"][0])
            spec = next(row for row in read_sources() if row["id"] == "FR:allego_stations")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), runner=OfflineRunner())
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)

    def test_failure_keeps_partial_out_of_final_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            with self.assertRaisesRegex(RuntimeError, "allego_normalize_v8"):
                run(out, runner=OfflineRunner(fail_at=SCRIPTS[1]))
            self.assertTrue((out / DATA).is_file())

    def test_missing_fallback_station_does_not_reject_current_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            run(out, runner=OfflineRunner())
            self.assertEqual(validate_output(out)["coordinateFallbacksApplied"], [])


if __name__ == "__main__":
    unittest.main()
