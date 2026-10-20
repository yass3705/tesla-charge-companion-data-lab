"""IWB Basel exact residual overlay on reduced archived national context."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from v9_rebuild.cwd_script import METHODS, run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source


class ReducedRunner:
    def __init__(self, fail=False):
        self.fail = fail

    def __call__(self, command, **kwargs):
        if self.fail:
            return subprocess.CompletedProcess(command, 2)
        archive = Path(kwargs["cwd"]) / "docs/switzerland-iwb-owner-reconciliation-2026-09-28.json"
        data = json.loads(archive.read_text())
        first, second = data["classes"]["public_unpriced"][:2]
        first["address"]["City"] = "Basel"
        first["chargingFacilities"] = [{"power": 22, "powertype": "AC_3_PHASE"}]
        second["address"]["City"] = "Liestal"
        data["classes"] = {"public_unpriced": [first, second], "owner_not_seen_in_atlas": []}
        data["classCounts"] = {"priced_exact": 0, "restricted_no_auth": 0, "public_unpriced": 2, "owner_not_seen_in_atlas": 0}
        data["nationalOwnerEvseCount"] = 2
        archive.write_text(json.dumps(data))
        return subprocess.run(command, **kwargs)


class SwissIwbMigrationTests(unittest.TestCase):
    def test_exact_basel_scope_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root / "source", "swiss_iwb", runner=ReducedRunner())
            payload = validate_output(root / "source", "swiss_iwb")
            self.assertEqual(payload["overlayCount"], 1)
            self.assertEqual(payload["evses"][0]["city"], "Basel")
            spec = next(row for row in read_sources() if row["id"] == "CH:iwb_basel")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "swiss_iwb", runner=ReducedRunner())
                return subprocess.CompletedProcess(command, 0)
            self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_failure_and_corrupt_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "Historical swiss_iwb method failed"):
                run(root / "failed", "swiss_iwb", runner=ReducedRunner(fail=True))
            run(root / "source", "swiss_iwb", runner=ReducedRunner())
            (root / "source" / METHODS["swiss_iwb"][1]).write_text("{}")
            with self.assertRaises(ValueError):
                validate_output(root / "source", "swiss_iwb")


if __name__ == "__main__":
    unittest.main()
