"""Offline execution of the two archived Moroccan public-map methods."""

import io
import json
import os
import runpy
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild import morocco_inventory
from v9_rebuild.orchestrator import read_sources, run_source


FASTVOLT = {"carte": {"components": [{"chargers": [
    {"charger_id": "FV-1", "charger_name": "A", "geo_coordinates": "33.5,-7.5", "ccs_count": 1},
    {"charger_id": "TEST-2", "charger_name": "Test", "geo_coordinates": "33.5,-7.5", "ccs_count": 1},
]}]}}
KILOWATT = [
    {"id": "KW-1", "name": "A", "location": {"latitude": 33.5, "longitude": -7.5},
     "connectors": [{"type": "CCS", "power": 50}]},
    {"id": "KW-2", "name": "Test", "location": {"latitude": 33.5, "longitude": -7.5},
     "connectors": []},
]


class Response(io.BytesIO):
    status = 200
    headers = {"Content-Type": "application/json"}


def offline_runner(command, **kwargs):
    method = "fastvolt" if "fastvolt" in command[1] else "kilowatt"

    def urlopen(request, **_):
        url = request.full_url
        payload = (FASTVOLT if method == "fastvolt" else
                   {"count": 1} if url.endswith("connectors-count") else KILOWATT)
        return Response(json.dumps(payload).encode())

    old = Path.cwd()
    stdout = io.StringIO()
    try:
        os.chdir(kwargs["cwd"])
        with patch("urllib.request.urlopen", side_effect=urlopen), redirect_stdout(stdout):
            runpy.run_path(command[1], run_name="__main__")
    finally:
        os.chdir(old)
    return SimpleNamespace(returncode=0, stdout=stdout.getvalue())


class MoroccoInventoryTests(unittest.TestCase):
    def test_archived_methods_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for method in morocco_inventory.METHODS:
                with self.subTest(method=method):
                    out = base / method
                    morocco_inventory.run(out, method, runner=offline_runner)
                    report = morocco_inventory.validate_output(out, method)
                    rows = report["chargers" if method == "fastvolt" else "stations"]
                    self.assertEqual([r["production_candidate"] for r in rows], [True, False])
                    self.assertEqual(rows[0]["charger_id" if method == "fastvolt" else "id"],
                                     "FV-1" if method == "fastvolt" else "KW-1")
                    self.assertTrue(all(r["site_brand"] is None for r in rows))
                    spec = next(x for x in read_sources() if x["id"] == f"MA:{method}_inventory")

                    def process(command, **_):
                        morocco_inventory.run(Path(command[command.index("--out") + 1]),
                                              method, runner=offline_runner)
                        return SimpleNamespace(returncode=0)

                    self.assertEqual(run_source(spec, base / f"{method}-artifact", runner=process)["status"], "ok")

    def test_failures_and_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "failure"
            failed = lambda *_args, **_kwargs: SimpleNamespace(returncode=2, stdout="")
            with self.assertRaises(RuntimeError):
                morocco_inventory.run(out, "fastvolt", runner=failed)
            self.assertFalse((out / morocco_inventory.METHODS["fastvolt"][1]).exists())
            morocco_inventory.run(out, "fastvolt", runner=offline_runner)
            path = out / morocco_inventory.METHODS["fastvolt"][1]
            report = json.loads(path.read_text())
            report["summary"]["charger_count"] = 999
            path.write_text(json.dumps(report))
            with self.assertRaises(ValueError):
                morocco_inventory.validate_output(out, "fastvolt")


if __name__ == "__main__":
    unittest.main()
