"""AIL and EBS preserved finalizers on reduced archived evidence."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from v9_rebuild.cwd_script import run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source


ARCHIVES = {
    "swiss_ail": ("docs/switzerland-small-cpo-national-context-2026-09-28.json", "CH*AIL"),
    "swiss_ebs": ("docs/switzerland-ecarup-targeted-national-queries-2026-09-28.json", "CH*EBS"),
}


class ReducedRunner:
    def __init__(self, method, fail=False):
        self.method = method
        self.fail = fail

    def __call__(self, command, **kwargs):
        if self.fail:
            return subprocess.CompletedProcess(command, 2)
        archive, operator = ARCHIVES[self.method]
        path = Path(kwargs["cwd"]) / archive
        fixture = json.loads(path.read_text())
        rows = fixture["operators"][operator]
        if self.method == "swiss_ail":
            fixture["operators"][operator] = rows[:2]
            fixture["operators"][operator][1]["evse"]["ChargingFacilities"] = [{"power": 50}]
        else:
            fixture["operators"][operator] = [rows[0], rows[2]]
        path.write_text(json.dumps(fixture))
        return subprocess.run(command, **kwargs)


class ArchivedSwissFinalizerTests(unittest.TestCase):
    def test_two_historical_methods_and_orchestrator(self):
        for method, source_id in (("swiss_ail", "CH:ail_emoti"), ("swiss_ebs", "CH:ebs_ecarup")):
            with self.subTest(method=method), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                run(root / "source", method, runner=ReducedRunner(method))
                payload = validate_output(root / "source", method)
                self.assertEqual(payload["counts"]["nationalEvseCount"], 2)
                self.assertEqual(payload["counts"]["unresolvedEvseCount"], 1)
                self.assertEqual(payload["counts"]["pricedEvseCount"], 1)
                spec = next(row for row in read_sources() if row["id"] == source_id)
                def outer(command, **kwargs):
                    run(Path(command[command.index("--out") + 1]), method, runner=ReducedRunner(method))
                    return subprocess.CompletedProcess(command, 0)
                self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_failures_and_corrupt_output(self):
        for method in ARCHIVES:
            with self.subTest(method=method), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with self.assertRaisesRegex(RuntimeError, f"Historical {method} method failed"):
                    run(root / "failed", method, runner=ReducedRunner(method, fail=True))
                run(root / "source", method, runner=ReducedRunner(method))
                from v9_rebuild.cwd_script import METHODS
                (root / "source" / METHODS[method][1]).write_text("{}")
                with self.assertRaises(ValueError):
                    validate_output(root / "source", method)


if __name__ == "__main__":
    unittest.main()
