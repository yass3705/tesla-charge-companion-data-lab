"""Real archived-input reliability audit with isolated output and signed inputs."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v9_rebuild import france_treated_audit as audit
from v9_rebuild.orchestrator import read_sources, run_source


class FranceTreatedAuditTests(unittest.TestCase):
    def test_real_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = next(row for row in read_sources() if row["id"] == "FR:treated_reliability")
            result = run_source(source, base / "artifacts", attempts=1)
            self.assertEqual(result["status"], "ok", result)
            report = base / "artifacts" / result["artifact"]
            artifact_root = report.parents[2]
            payload = audit.validate_output(artifact_root)
            self.assertEqual(payload["country"], "FR")
            self.assertTrue(payload["decision"]["treatedDoesNotMean100PercentPriced"])
            self.assertEqual(sum(1 for path in artifact_root.rglob("*") if path.is_file()), 3)
            report.write_text(json.dumps({"country": "FR"}))
            with self.assertRaisesRegex(ValueError, "provenance invalid"):
                audit.validate_output(artifact_root)

    def test_script_failure_keeps_no_published_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fail(command, **_):
                return subprocess.CompletedProcess(command, 1)
            with patch.object(audit, "inputs", return_value=[audit.SCRIPT, audit.CANON, audit.REGISTRY]):
                with self.assertRaisesRegex(RuntimeError, "failed"):
                    audit.run(Path(tmp), runner=fail)
            self.assertFalse((Path(tmp) / audit.REPORT).exists())


if __name__ == "__main__":
    unittest.main()
