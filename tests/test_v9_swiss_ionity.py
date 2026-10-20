"""Preserved Swiss IONITY national/official connector reconciliation."""

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
        official = json.loads((ROOT / "data/switzerland/ionity-official-direct-tariffs.json").read_text())
        location = official["locations"][0]
        fixture = {"stations": [
            {"EvseID": "CH*IOY*E1", "ChargingStationId": "S1",
             "GeoCoordinates": {"Google": f"{location['latitude']} {location['longitude']}"},
             "ChargingFacilities": [{"power": 350}]},
            {"EvseID": "CH*IOY*E2", "ChargingStationId": "S2",
             "GeoCoordinates": {"Google": "0 0"}, "ChargingFacilities": [{"power": 350}]},
            {"EvseID": "CH*OTHER*E1"},
        ]}
        cwd = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            with patch("urllib.request.urlopen", return_value=Response(json.dumps(fixture).encode())), patch("builtins.print"):
                runpy.run_path(str(ROOT / "scripts/finalize_swiss_ionity_national.py"), run_name="__main__")
        finally:
            os.chdir(cwd)
        return SimpleNamespace(returncode=0)


class SwissIonityMigrationTests(unittest.TestCase):
    def test_exact_power_match_and_unresolved_evse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root / "source", "swiss_ionity", runner=FixtureRunner())
            payload = validate_output(root / "source", "swiss_ionity")
            self.assertEqual([row["evseId"] for row in payload["evses"]], ["CH*IOY*E1"])
            self.assertEqual([row["evseId"] for row in payload["unresolved"]], ["CH*IOY*E2"])
            spec = next(row for row in read_sources() if row["id"] == "CH:ionity_national")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "swiss_ionity", runner=FixtureRunner())
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_failure_and_corrupt_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "Historical swiss_ionity method failed"):
                run(root / "failed", "swiss_ionity", runner=FixtureRunner(fail=True))
            run(root / "source", "swiss_ionity", runner=FixtureRunner())
            (root / "source/data/switzerland/ionity-official-national-direct-tariffs.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Swiss IONITY"):
                validate_output(root / "source", "swiss_ionity")


if __name__ == "__main__":
    unittest.main()
