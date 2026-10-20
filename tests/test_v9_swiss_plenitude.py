"""Preserved Swiss Plenitude finalizer with exact EVSE and 75 kW boundary."""

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
            {"EvseID": "CH*PLN*EH000510*1", "ChargingFacilities": [{"power": 110}]},
            {"EvseID": "CH*PLN*EH000510*3", "ChargingFacilities": [{"power": 22}]},
            {"EvseID": "CH*PLN*EFIXTURE75", "ChargingFacilities": [{"power": 75}], "ConnectorType": "CCS"},
            {"EvseID": "CH*OTHER*E1"},
        ]}
        cwd = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            with patch("urllib.request.urlopen", return_value=Response(json.dumps(fixture).encode())), patch("builtins.print"):
                runpy.run_path(str(ROOT / "scripts/finalize_swiss_plenitude_official.py"), run_name="__main__")
        finally:
            os.chdir(cwd)
        return SimpleNamespace(returncode=0)


class SwissPlenitudeMigrationTests(unittest.TestCase):
    def test_exact_atlas_mapping_and_boundary_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root / "source", "swiss_plenitude", runner=FixtureRunner())
            payload = validate_output(root / "source", "swiss_plenitude")
            self.assertEqual({row["evseId"] for row in payload["evses"]}, {"CH*PLN*EH000510*1", "CH*PLN*EH000510*3"})
            self.assertEqual([row["evseId"] for row in payload["unresolved"]], ["CH*PLN*EFIXTURE75"])
            spec = next(row for row in read_sources() if row["id"] == "CH:plenitude_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "swiss_plenitude", runner=FixtureRunner())
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_failure_and_corrupt_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "Historical swiss_plenitude method failed"):
                run(root / "failed", "swiss_plenitude", runner=FixtureRunner(fail=True))
            run(root / "source", "swiss_plenitude", runner=FixtureRunner())
            (root / "source/data/switzerland/plenitude-official-direct-tariffs.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Swiss Plenitude"):
                validate_output(root / "source", "swiss_plenitude")


if __name__ == "__main__":
    unittest.main()
