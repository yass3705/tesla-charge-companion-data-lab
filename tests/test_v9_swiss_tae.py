"""TAE Matterhorn finalizer keeps out-of-scope EVSE explicitly unresolved."""

import json
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_v9_swiss_fastned import Response
from v9_rebuild.cwd_script import METHODS, run, validate_output
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source


class FixtureRunner:
    def __init__(self, fail=False):
        self.fail = fail

    def __call__(self, command, **kwargs):
        if self.fail:
            return SimpleNamespace(returncode=2)
        fixture = {"stations": [{"OperatorID": "CH*TAE", "EVSEs": [
            {"EvseID": "CH*TAE*E1", "ChargingFacilities": [{"power": 22}]},
            {"EvseID": "CH*TAE*E2", "ChargingFacilities": [{"power": 50}]},
        ]}, {"OperatorID": "CH*OTHER", "EVSEs": [{"EvseID": "CH*OTHER*E1"}]}]}
        cwd = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            with patch("urllib.request.urlopen", return_value=Response(json.dumps(fixture).encode())), patch("builtins.print"):
                runpy.run_path(str(ROOT / METHODS["swiss_tae"][0]), run_name="__main__")
        finally:
            os.chdir(cwd)
        return SimpleNamespace(returncode=0)


class SwissTaeTests(unittest.TestCase):
    def test_exact_terminal_power_and_unresolved_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root / "source", "swiss_tae", runner=FixtureRunner())
            payload = validate_output(root / "source", "swiss_tae")
            self.assertEqual(payload["counts"], {"nationalEvseCount": 2, "pricedEvseCount": 1, "unresolvedEvseCount": 1})
            self.assertEqual(payload["unresolved"][0]["evseId"], "CH*TAE*E2")
            self.assertEqual(payload["evses"][0]["maxPowerKw"], 22)
            spec = next(row for row in read_sources() if row["id"] == "CH:tae_matterhorn")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "swiss_tae", runner=FixtureRunner())
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_failure_and_corrupt_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "Historical swiss_tae method failed"):
                run(root / "failed", "swiss_tae", runner=FixtureRunner(fail=True))
            run(root / "source", "swiss_tae", runner=FixtureRunner())
            (root / "source" / METHODS["swiss_tae"][1]).write_text("{}")
            with self.assertRaises(ValueError):
                validate_output(root / "source", "swiss_tae")


if __name__ == "__main__":
    unittest.main()
