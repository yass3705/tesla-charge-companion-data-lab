"""Four archived Swisscharge shards, checkpoint and exact merge, entirely offline."""

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from v9_rebuild import swisscharge
from v9_rebuild.orchestrator import read_sources, run_source


class HistoricalRunner:
    def __init__(self):
        self.calls = []
        self.fail_index = None

    def __call__(self, command, **_):
        index = int(command[command.index("--shard-index") + 1])
        self.calls.append(index)
        if index == self.fail_index:
            return subprocess.CompletedProcess(command, 2)
        module_spec = importlib.util.spec_from_file_location(f"swisscharge_fixture_{index}", command[1])
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        feed = {"operators": [{"EvseID": f"CH*SUI*E{number}"} for number in range(1, 5)]}

        def get(_opener, url, *_args, **_kwargs):
            if "session-start" in url:
                return 200, {}, b"{}"
            ref = parse_qs(urlsplit(url).query)["evsePhysicalReference"][0]
            if ref == "4":
                return 404, {}, b"not found"
            body = {"data": {"chargePoint": {"id": f"CP-{ref}"},
                    "evses": [{"physicalReference": ref, "tariff": {
                        "id": f"T-{ref}", "name": "Direct", "currency": "CHF",
                        "pricing": {"pricePerKwh": 0.4},
                        "restrictions": {"applyToAdHocUsers": True}}}]}}
            return 200, {}, json.dumps(body).encode()

        with patch.object(module, "download_json", return_value=feed), \
             patch.object(module, "opener", return_value=object()), \
             patch.object(module, "get", side_effect=get), \
             patch("sys.argv", command[1:]), redirect_stdout(io.StringIO()):
            result = module.main()
        return subprocess.CompletedProcess(command, result)


class SwisschargeTests(unittest.TestCase):
    def test_concurrent_shards_publish_one_complete_object(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)

            def synthetic_runner(command, **_):
                index = int(command[command.index("--shard-index") + 1])
                path = Path(command[command.index("--output") + 1])
                time.sleep((3 - index) * 0.01)
                tariff = {"id": f"T-{index}", "currency": "CHF", "pricePerKwh": 0.4}
                row = {"physicalReference": str(index + 1), "tariff": tariff}
                data = {"schemaVersion": 1, "source": {},
                        "scope": {"shardIndex": index, "shardCount": 4,
                                  "nationalEvseCount": 4, "evseCount": 1},
                        "summary": {"resolvedTariffEvseCount": 1,
                                    "unresolvedEvseCount": 0, "uniqueTariffCount": 1,
                                    "http200": 1, "http4xx": 0, "http5xx": 0,
                                    "transport": 0, "noTariff": 0},
                        "tariffsById": {tariff["id"]: tariff}, "evses": [row], "unresolved": []}
                path.write_text(json.dumps(data))
                return subprocess.CompletedProcess(command, 0)

            swisscharge.run(base / "complete", base / "checkpoints", runner=synthetic_runner)
            payload = swisscharge.validate_output(base / "complete")
            self.assertEqual(len(payload["evses"]), 4)
            self.assertEqual(len({row["physicalReference"] for row in payload["evses"]}), 4)

    def test_failure_preserves_three_shards_and_resume_merges_exactly(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            runner = HistoricalRunner()
            runner.fail_index = 2
            checkpoint = base / "checkpoints"
            with self.assertRaisesRegex(RuntimeError, "shard 2 failed"):
                swisscharge.run(base / "first", checkpoint, runner=runner, parallel=False)
            self.assertEqual(set(swisscharge.validate_checkpoint(checkpoint)), {0, 1, 3})
            self.assertFalse((base / "first" / swisscharge.DATA).exists())
            runner.fail_index = None
            runner.calls.clear()
            swisscharge.run(base / "resume", checkpoint, runner=runner, parallel=False)
            self.assertEqual(runner.calls, [2])
            payload = swisscharge.validate_output(base / "resume")
            self.assertEqual(payload["scope"]["nationalEvseCount"], 4)
            self.assertEqual(len(payload["evses"]), 3)
            self.assertEqual(payload["unresolvedByClass"]["notFound"][0]["physicalReference"], "4")
            self.assertEqual(payload["summary"]["http200"], 3)

    def test_bad_sha_and_incomplete_set_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            checkpoint = base / "checkpoints"
            swisscharge.run(base / "good", checkpoint, runner=HistoricalRunner(), parallel=False)
            shard = checkpoint / "shard-0.json"
            shard.write_text("{}")
            with self.assertRaisesRegex(ValueError, "SHA invalid"):
                swisscharge.validate_checkpoint(checkpoint)
            with self.assertRaises(ValueError):
                swisscharge.run(base / "bad", checkpoint, runner=HistoricalRunner(), parallel=False)
            report = base / "good" / swisscharge.DATA
            data = json.loads(report.read_text())
            data["evses"][0]["physicalReference"] = "other"
            report.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "differs from validated shards"):
                swisscharge.validate_output(base / "good")

    def test_orchestrator_keeps_checkpoint_outside_publishable_objects(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            spec = next(x for x in read_sources() if x["id"] == "CH:swisscharge_full")
            historical = HistoricalRunner()
            historical.fail_index = 1

            def process(command, **_):
                try:
                    swisscharge.run(Path(command[command.index("--out") + 1]),
                                    Path(command[command.index("--checkpoint") + 1]),
                                    runner=historical, parallel=False)
                    return subprocess.CompletedProcess(command, 0)
                except RuntimeError:
                    return subprocess.CompletedProcess(command, 2)

            result = run_source(spec, base / "artifacts", attempts=1, runner=process)
            self.assertEqual(result["status"], "failed")
            self.assertTrue((base / "artifacts/checkpoints/CH_swisscharge_full/shard-0.json").is_file())
            self.assertFalse(list((base / "artifacts/objects/CH_swisscharge_full").glob("*/data/swisscharge/swisscharge-tariffs.json")))
            historical.fail_index = None
            result = run_source(spec, base / "artifacts", attempts=1, runner=process)
            self.assertEqual(result["status"], "ok", result)
            self.assertEqual(historical.calls.count(0), 1)
            self.assertFalse((base / "artifacts/checkpoints/CH_swisscharge_full").exists())


if __name__ == "__main__":
    unittest.main()
