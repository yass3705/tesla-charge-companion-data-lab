"""Offline execution and validation of the preserved Greenspot method."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v9_rebuild import greenspot
from v9_rebuild.orchestrator import read_sources, run_source


ROW = {"id_pdc_itinerance": "FR*GSP*E1", "coordonneesXY": [2.0, 48.0],
       "id_station_itinerance": "FR*GSP*S1"}


def offline_runner(command, **_):
    name = "greenspot_fixture"
    spec = importlib.util.spec_from_file_location(name, command[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    detail = {"evseId": "FR*GSP*E1", "simpleTariff": {"components": []}}
    site = {"key": "48.000000,2.000000", "expected": ["FRGSPE1"],
            "missing": [], "details": [detail], "error": None}
    with patch.object(module, "fetch_irve_rows", return_value=([ROW], {"total": 1})), \
         patch.object(module, "query_site", return_value=site), \
         patch.object(sys, "argv", command[1:]):
        module.main()
    return subprocess.CompletedProcess(command, 0)


class GreenspotMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            greenspot.run(base / "direct", runner=offline_runner)
            payload = greenspot.validate_output(base / "direct")
            self.assertEqual([row["evseKey"] for row in payload["records"]], ["FRGSPE1"])
            self.assertEqual(payload["records"][0]["directTariff"], {"components": []})
            source = next(row for row in read_sources() if row["id"] == "FR:greenspot")

            def process(command, **_):
                greenspot.run(Path(command[-1]), runner=offline_runner)
                return subprocess.CompletedProcess(command, 0)

            result = run_source(source, base / "artifacts", runner=process)
            self.assertEqual(result["status"], "ok")
            self.assertTrue((base / "artifacts" / result["artifact"]).is_file())

    def test_error_and_corruption_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            def fail(command, **_):
                return subprocess.CompletedProcess(command, 1)
            with self.assertRaisesRegex(RuntimeError, "method failed"):
                greenspot.run(base / "failed", runner=fail)
            greenspot.run(base / "valid", runner=offline_runner)
            report = base / "valid" / greenspot.REPORT
            body = json.loads(report.read_text())
            body["siteErrors"] = 1
            report.write_text(json.dumps(body))
            with self.assertRaises(ValueError):
                greenspot.validate_output(base / "valid")


if __name__ == "__main__":
    unittest.main()
