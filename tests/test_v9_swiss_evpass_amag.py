"""autoSense, CHEVP, and Shell/evpass historic Swiss finalizers."""

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


SOURCES = {
    "swiss_autosense": ("CH:autosense_amag", "CH*AUTOSENSE"),
    "swiss_chevp": ("CH:chevp_evpass", "CHEVP"),
    "swiss_shell_evpass": ("CH:shell_evpass", "CH*SHE"),
}


class FixtureRunner:
    def __init__(self, method, fail=False):
        self.method = method
        self.fail = fail

    def __call__(self, command, **kwargs):
        if self.fail:
            return SimpleNamespace(returncode=2)
        _, operator = SOURCES[self.method]
        eid = (lambda n: operator + (f"E{n}" if operator == "CHEVP" else f"*E{n}"))
        first = {"EvseID": eid(1), "ChargingFacilities": [{"power": 22}],
                 "ChargingStationNames": [{"value": "AMAG Charging Station Fixture"}]}
        second = {"EvseID": eid(2), "ChargingFacilities": [],
                  "ChargingStationNames": [{"value": "Other operator site"}]}
        fixture = {"stations": [{"OperatorID": operator, "OperatorName": "evpass" if operator == "CHEVP" else operator,
                                  "EVSEs": [first, second]},
                                 {"OperatorID": "CH*OTHER", "EVSEs": [{"EvseID": "CH*OTHER*E1"}]}]}
        cwd = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            with patch("urllib.request.urlopen", return_value=Response(json.dumps(fixture).encode())), patch("builtins.print"):
                runpy.run_path(str(ROOT / METHODS[self.method][0]), run_name="__main__")
        finally:
            os.chdir(cwd)
        return SimpleNamespace(returncode=0)


class SwissEvpassAmagTests(unittest.TestCase):
    def test_exact_owner_and_missing_conditions(self):
        for method, (source_id, operator) in SOURCES.items():
            with self.subTest(method=method), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                run(root / "source", method, runner=FixtureRunner(method))
                payload = validate_output(root / "source", method)
                self.assertEqual(payload["counts"], {"nationalEvseCount": 2, "pricedEvseCount": 1, "unresolvedEvseCount": 1})
                if method == "swiss_autosense":
                    self.assertNotEqual(payload["evses"][0]["standardPricePerKwh"], payload["evses"][0]["conditionalEligibleBrandPricePerKwh"])
                if method == "swiss_shell_evpass":
                    self.assertIsNone(payload["evses"][1]["pricePerKwh"])
                spec = next(row for row in read_sources() if row["id"] == source_id)
                def outer(command, **kwargs):
                    run(Path(command[command.index("--out") + 1]), method, runner=FixtureRunner(method))
                    return SimpleNamespace(returncode=0)
                self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_failure_and_corrupt_output(self):
        for method in SOURCES:
            with self.subTest(method=method), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with self.assertRaisesRegex(RuntimeError, f"Historical {method} method failed"):
                    run(root / "failed", method, runner=FixtureRunner(method, fail=True))
                run(root / "source", method, runner=FixtureRunner(method))
                (root / "source" / METHODS[method][1]).write_text("{}")
                with self.assertRaises(ValueError):
                    validate_output(root / "source", method)


if __name__ == "__main__":
    unittest.main()
