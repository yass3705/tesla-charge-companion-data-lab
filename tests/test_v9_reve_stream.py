"""REVE stream runs offline with real historical cursor and merge logic."""

import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from v9_rebuild import reve_stream
from v9_rebuild.orchestrator import read_sources, run_source


class StreamRunner:
    def __init__(self, fail=None):
        self.fail = fail
        self.calls = []
        self.future = False

    def __call__(self, command, **kwargs):
        spec = importlib.util.spec_from_file_location("reve_stream_fixture", command[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        folder = Path(kwargs["env"]["REVE_DATA_DIR"])
        for key, name in (("DATA", ""), ("PROBE", "live_tariff_status_probe.json"),
                          ("STATE", reve_stream.FILES[0]), ("TARIFF_STORE", reve_stream.FILES[1]),
                          ("STATUS_STORE", reve_stream.FILES[2]), ("LAST_RUN", reve_stream.FILES[3])):
            setattr(module, key, folder / name if name else folder)
        old_datetime = module.datetime
        if self.future:
            class FutureDateTime(datetime):
                @classmethod
                def now(cls, tz=None):
                    return old_datetime.now(tz) + timedelta(hours=2)
            module.datetime = FutureDateTime

        def response(_key, endpoint, page):
            kind = "tariff" if "tariffs" in endpoint else "status"
            self.calls.append((kind, page))
            if self.fail == (kind, page):
                return {"status": 503, "headers": {}, "payload": None,
                        "transportExitCode": 0, "stderrPreview": None, "bodyPreview": None}
            row = {"connector_id": f"ES*RVE*C{page}"} if kind == "tariff" else {"evse_id": f"ES*RVE*E{page}"}
            total = 4 if kind == "tariff" else 3
            return {"status": 200, "headers": {"total-pages": str(total), "total-count": str(total)},
                    "payload": [row], "transportExitCode": 0, "stderrPreview": None, "bodyPreview": None}

        with patch.object(module, "api_get", side_effect=response), \
             patch.dict(os.environ, {"REVE_API_KEY": "local-fixture"}), redirect_stdout(io.StringIO()):
            code = module.collect()
        return subprocess.CompletedProcess(command, code)


class ReveStreamMigrationTests(unittest.TestCase):
    def test_incomplete_checkpoint_then_exact_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            runner = StreamRunner()
            with self.assertRaisesRegex(ValueError, "incomplete"):
                reve_stream.run(base / "first", base / "checkpoint", runner=runner)
            first = reve_stream.validate_checkpoint(base / "checkpoint")
            self.assertIsNotNone(first)
            state = json.loads((first / reve_stream.FILES[0]).read_text())
            self.assertEqual((state["nextTariffPage"], state["nextStatusPage"]), (4, 3))
            self.assertTrue((base / "first" / reve_stream.DATA / reve_stream.FILES[0]).is_file())
            runner.future = True
            reve_stream.run(base / "second", base / "checkpoint", runner=runner)
            self.assertTrue(reve_stream.validate_output(base / "second")["complete"])
            self.assertEqual(runner.calls, [("tariff", 1), ("tariff", 2), ("tariff", 3),
                                            ("status", 1), ("status", 2), ("tariff", 4), ("status", 3)])

    def test_failure_retains_pages_and_sha_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            runner = StreamRunner(fail=("tariff", 2))
            with self.assertRaisesRegex(RuntimeError, "checkpoint retained"):
                reve_stream.run(base / "failed", base / "checkpoint", runner=runner)
            folder = reve_stream.validate_checkpoint(base / "checkpoint")
            state = json.loads((folder / reve_stream.FILES[0]).read_text())
            self.assertEqual(state["tariffPagesCollected"], [1])
            self.assertEqual(state["nextTariffPage"], 2)
            runner.fail = None
            runner.future = True
            with self.assertRaisesRegex(ValueError, "incomplete"):
                reve_stream.run(base / "resume", base / "checkpoint", runner=runner)
            self.assertNotIn(("tariff", 1), runner.calls[2:])
            folder = reve_stream.validate_checkpoint(base / "checkpoint")
            (folder / reve_stream.FILES[0]).write_text("{}")
            with self.assertRaisesRegex(ValueError, "SHA"):
                reve_stream.validate_checkpoint(base / "checkpoint")

    def test_orchestrator_never_publishes_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            spec = next(row for row in read_sources() if row["id"] == "ES:reve_stream")
            runner = StreamRunner()
            def process(command, **_):
                try:
                    reve_stream.run(Path(command[command.index("--out") + 1]),
                                    Path(command[command.index("--checkpoint") + 1]), runner=runner)
                    return subprocess.CompletedProcess(command, 0)
                except (RuntimeError, ValueError):
                    return subprocess.CompletedProcess(command, 1)
            with patch.dict(os.environ, {"REVE_API_KEY": "local-fixture"}):
                first = run_source(spec, base / "artifacts", attempts=1, runner=process)
                self.assertEqual(first["status"], "failed")
                self.assertFalse(list((base / "artifacts/objects/ES_reve_stream").glob("*/data")))
                runner.future = True
                second = run_source(spec, base / "artifacts", attempts=1, runner=process)
                self.assertEqual(second["status"], "ok")
                self.assertTrue((base / "artifacts" / second["artifact"]).is_file())


if __name__ == "__main__":
    unittest.main()
