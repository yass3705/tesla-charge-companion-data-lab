"""Preserved Swiss Lidl finalizer on a reduced national-feed fixture."""

import json
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_v9_swiss_fastned import Response
from v9_rebuild.cwd_script import run, validate_output
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source


class FixtureRunner:
    def __init__(self, fail=False):
        self.fail = fail

    def __call__(self, command, **kwargs):
        if self.fail:
            return SimpleNamespace(returncode=2)
        fixture = {"stations": [
            {"OperatorID": "CH*LDL", "EvseID": "CH*LDL*E1", "ChargingFacilities": [{"power": 22}]},
            {"OperatorID": "CH*LDL", "EvseID": "CH*LDL*E2", "ChargingFacilities": [{"power": 50}]},
            {"OperatorID": "CH*LDL", "EvseID": "CH*LDL*E3", "ChargingFacilities": []},
            {"OperatorID": "CH*OTHER", "EvseID": "CH*OTHER*E1"},
        ]}
        cwd = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            with patch("urllib.request.urlopen", return_value=Response(json.dumps(fixture).encode())), patch("builtins.print"):
                runpy.run_path(str(ROOT / "scripts/finalize_swiss_lidl_official.py"), run_name="__main__")
        finally:
            os.chdir(cwd)
        return SimpleNamespace(returncode=0)


class SwissLidlMigrationTests(unittest.TestCase):
    def test_exact_power_and_missing_power(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root / "source", "swiss_lidl", runner=FixtureRunner())
            payload = validate_output(root / "source", "swiss_lidl")
            self.assertEqual([row["evseId"] for row in payload["evses"]], ["CH*LDL*E1", "CH*LDL*E2", "CH*LDL*E3"])
            self.assertEqual(payload["evses"][0]["energyType"], "AC")
            self.assertEqual(payload["evses"][1]["energyType"], "DC")
            self.assertIsNone(payload["evses"][2]["directWebPricePerKwh"])
            spec = next(row for row in read_sources() if row["id"] == "CH:lidl_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "swiss_lidl", runner=FixtureRunner())
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_failure_and_corrupt_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "Historical swiss_lidl method failed"):
                run(root / "failed", "swiss_lidl", runner=FixtureRunner(fail=True))
            run(root / "source", "swiss_lidl", runner=FixtureRunner())
            (root / "source/data/switzerland/lidl-official-direct-tariffs.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Swiss Lidl"):
                validate_output(root / "source", "swiss_lidl")


if __name__ == "__main__":
    unittest.main()
