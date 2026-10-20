"""EWD and Migrol preserved national EVSE finalizers."""

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
    def __init__(self, method, fail=False):
        self.method = method
        self.fail = fail

    def __call__(self, command, **kwargs):
        if self.fail:
            return SimpleNamespace(returncode=2)
        prefix = "CH*EWD" if self.method == "swiss_ewd" else "CH*MIG"
        fixture = {"stations": [
            {"EvseID": prefix + "*E1", "ChargingFacilities": [{"power": 22}]},
            {"EvseID": prefix + "*E2", "ChargingFacilities": []},
            {"EvseID": "CH*OTHER*E1"},
        ]}
        cwd = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            with patch("urllib.request.urlopen", return_value=Response(json.dumps(fixture).encode())), patch("builtins.print"):
                runpy.run_path(str(ROOT / METHODS[self.method][0]), run_name="__main__")
        finally:
            os.chdir(cwd)
        return SimpleNamespace(returncode=0)


class SwissNationalRulesTests(unittest.TestCase):
    def test_exact_scope_and_orchestrator(self):
        for method, source_id in (("swiss_ewd", "CH:ewd_official"), ("swiss_migrol", "CH:migrol_official")):
            with self.subTest(method=method), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                run(root / "source", method, runner=FixtureRunner(method))
                payload = validate_output(root / "source", method)
                self.assertEqual(payload["counts"]["nationalEvseCount"], 2)
                if method == "swiss_migrol":
                    self.assertEqual(payload["counts"]["unresolvedEvseCount"], 1)
                    self.assertIsNone(payload["evses"][1]["pricePerKwh"])
                spec = next(row for row in read_sources() if row["id"] == source_id)
                def outer(command, **kwargs):
                    run(Path(command[command.index("--out") + 1]), method, runner=FixtureRunner(method))
                    return SimpleNamespace(returncode=0)
                self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_failure_and_corrupt_output(self):
        for method in ("swiss_ewd", "swiss_migrol"):
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
