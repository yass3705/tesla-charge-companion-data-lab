"""EWO eCarUp exact same-operator public connector reconciliation."""

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
        archive = Path(kwargs["cwd"]) / "data/switzerland/ecarup-public-stations.json"
        source = json.loads(archive.read_text())
        station = next(row for row in source["stations"]
                       if (row.get("ContactDetails") or {}).get("OperatorName") == "Elektrizitätswerk Obwalden"
                       and any(c.get("AccessType") == 0 and (c.get("Price") or {}).get("EnergyPrice") is not None
                               for c in row.get("Connectors", [])))
        source["stations"] = [station]
        archive.write_text(json.dumps(source))
        fixture = {"stations": [{"OperatorID": "CH*EWO", "EVSEs": [
            {"EvseID": "CH*EWO*E1", "GeoCoordinates": {"Google": f"{station['Latitude']} {station['Longitude']}"}},
            {"EvseID": "CH*EWO*E2", "GeoCoordinates": {"Google": "0 0"}},
        ]}, {"OperatorID": "CH*OTHER", "EVSEs": [{"EvseID": "CH*OTHER*E1"}]}]}
        cwd = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            with patch("urllib.request.urlopen", return_value=Response(json.dumps(fixture).encode())), patch("builtins.print"):
                runpy.run_path(str(ROOT / METHODS["swiss_ewo"][0]), run_name="__main__")
        finally:
            os.chdir(cwd)
        return SimpleNamespace(returncode=0)


class SwissEwoTests(unittest.TestCase):
    def test_exact_connector_and_unresolved_station(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root / "source", "swiss_ewo", runner=FixtureRunner())
            payload = validate_output(root / "source", "swiss_ewo")
            self.assertEqual(payload["counts"], {"nationalEvseCount": 2, "resolvedEvseCount": 1, "unresolvedEvseCount": 1})
            self.assertEqual(payload["evses"][0]["evseId"], "CH*EWO*E1")
            self.assertEqual(payload["unresolved"][0]["evseId"], "CH*EWO*E2")
            spec = next(row for row in read_sources() if row["id"] == "CH:ewo_ecarup")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "swiss_ewo", runner=FixtureRunner())
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_failure_and_corrupt_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "Historical swiss_ewo method failed"):
                run(root / "failed", "swiss_ewo", runner=FixtureRunner(fail=True))
            run(root / "source", "swiss_ewo", runner=FixtureRunner())
            (root / "source" / METHODS["swiss_ewo"][1]).write_text("{}")
            with self.assertRaises(ValueError):
                validate_output(root / "source", "swiss_ewo")


if __name__ == "__main__":
    unittest.main()
