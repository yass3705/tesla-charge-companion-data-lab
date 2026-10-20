"""Preserved Swiss Fastned finalizer on a reduced national-feed fixture."""

import io
import json
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.cwd_script import run, validate_output
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class FixtureRunner:
    def __init__(self, corrupt=False):
        self.corrupt = corrupt

    def __call__(self, command, **kwargs):
        fixture = {"stations": [
            {"OperatorID": "CH*FASTNED", "EvseID": "CH*FASTNED*E1", "ChargingStationId": "S1"},
            {"OperatorID": "CH*OTHER", "EvseID": "CH*OTHER*E1"},
        ]}
        body = b"invalid" if self.corrupt else json.dumps(fixture).encode()
        cwd = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            with patch("urllib.request.urlopen", return_value=Response(body)), patch("builtins.print"):
                runpy.run_path(str(ROOT / "scripts/finalize_swiss_fastned_official.py"), run_name="__main__")
        except (ValueError, json.JSONDecodeError):
            return SimpleNamespace(returncode=2)
        finally:
            os.chdir(cwd)
        return SimpleNamespace(returncode=0)


class SwissFastnedMigrationTests(unittest.TestCase):
    def test_exact_owner_output_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root / "source", "swiss_fastned", runner=FixtureRunner())
            payload = validate_output(root / "source", "swiss_fastned")
            self.assertEqual([row["evseId"] for row in payload["evses"]], ["CH*FASTNED*E1"])
            spec = next(row for row in read_sources() if row["id"] == "CH:fastned_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "swiss_fastned", runner=FixtureRunner())
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_failure_and_corrupt_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "Historical swiss_fastned method failed"):
                run(root / "failed", "swiss_fastned", runner=FixtureRunner(corrupt=True))
            run(root / "source", "swiss_fastned", runner=FixtureRunner())
            (root / "source/data/switzerland/fastned-official-direct-tariffs.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Swiss Fastned"):
                validate_output(root / "source", "swiss_fastned")


if __name__ == "__main__":
    unittest.main()
