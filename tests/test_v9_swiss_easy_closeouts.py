import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.swiss_easy_closeouts import AGR, SOC_REPORT, SOC, run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source


class SwissEasyCloseoutsTest(unittest.TestCase):
    def test_preserved_atlas_pagination_and_direct_filter(self):
        path = Path(__file__).resolve().parents[1] / "scripts/collect_swiss_atlas_cpo.py"
        spec = importlib.util.spec_from_file_location("fixture_atlas_pagination", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        def pages(url, key, **kwargs):
            if "page%5Bnumber%5D=1" in url:
                return 200, {"data": [{"id": "S1"}], "meta": {"more_available": True}}
            return 200, {"data": [{"id": "S2"}], "meta": {"more_available": False}}
        module.api_call = pages
        self.assertEqual([x["id"] for x in module.station_pages("CH*SOC", "fixture")], ["S1", "S2"])
        module.api_call = lambda *a, **k: (503, {})
        with self.assertRaises(SystemExit):
            module.station_pages("CH*SOC", "fixture")
        payload = {"data": [
            {"id": "direct", "attributes": {"is_roaming": False}, "relationships": {"emp": {"data": {"id": "C"}}, "cpo": {"data": {"id": "C"}}}},
            {"id": "roaming", "attributes": {"is_roaming": True}, "relationships": {"emp": {"data": {"id": "E"}}, "cpo": {"data": {"id": "C"}}}},
        ]}
        self.assertEqual([x["detailId"] for x in module.direct_tariffs(payload)], ["direct"])

    def soc_runner(self, command, **kwargs):
        spec = importlib.util.spec_from_file_location("fixture_soc_atlas", command[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.extract_public_key = lambda: "fixture"
        module.station_pages = lambda operator, key: [{"id": "soc-station-1", "attributes": {"name": "SOCAR", "evse_ids": ["CH*SOC*E1"], "evse_operator": "CH*SOC", "charge_points": [{"power": 50, "plug": "CCS", "evse_ids": ["CH*SOC*E1"]}]}}]
        module.api_call = lambda *args, **kw: (200, {"data": [], "included": []})
        old_cwd, old_argv = Path.cwd(), sys.argv
        try:
            os.chdir(kwargs["cwd"])
            sys.argv = command[1:]
            module.main()
            return SimpleNamespace(returncode=0)
        finally:
            os.chdir(old_cwd)
            sys.argv = old_argv

    def test_archived_inputs_and_historical_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            monta = root / "monta.json"
            monta.write_text(json.dumps({"data": [{"evse_id": "CH*AGR*E158594", "currency": "CHF", "price_kw": 0.7308}]}))
            out = root / "out"
            out.mkdir()
            run(out, runner=self.soc_runner, monta_fixture=monta)
            report = validate_output(out)
            self.assertEqual(report["operatorId"], "CH*SOC")
            self.assertIn("CH*AGR*E158594", [row["evseId"] for row in json.loads((out / AGR).read_text())["evses"]])
            self.assertEqual(json.loads((out / SOC).read_text())["summary"]["stationCount"], 1)
            payload = json.loads((out / SOC).read_text())
            payload["stations"][0]["chargePoints"][0]["status"] = 429
            (out / SOC).write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "request incomplete"):
                validate_output(out)

    def test_technical_failure_does_not_finalize(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            monta = root / "monta.json"
            monta.write_text('{"data": []}')
            out = root / "out"
            out.mkdir()
            with self.assertRaisesRegex(RuntimeError, "SOC second pass failed"):
                run(out, runner=lambda *a, **k: SimpleNamespace(returncode=1), monta_fixture=monta)
            self.assertFalse((out / SOC_REPORT).exists())

    def test_orchestrator_isolated_output(self):
        source = next(row for row in read_sources() if row["id"] == "CH:easy_closeouts")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            monta = root / "monta.json"
            monta.write_text('{"data": []}')
            def adapter_runner(command, **kwargs):
                out = Path(command[command.index("--out") + 1])
                run(out, runner=self.soc_runner, monta_fixture=monta)
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(source, root / "artifacts", attempts=1, runner=adapter_runner)["status"], "ok")


if __name__ == "__main__":
    unittest.main()
