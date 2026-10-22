"""Rebuild the Electra residual audit without assigning unproven tariffs."""

import gzip
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from v9_rebuild import electra_residual_audit as audit
from v9_rebuild.orchestrator import read_sources, run_source


class ElectraResidualAuditTests(unittest.TestCase):
    def test_real_archived_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = next(row for row in read_sources() if row["id"] == "FR:electra_residual_audit")
            result = run_source(source, base / "artifacts", attempts=1)
            self.assertEqual(result["status"], "ok", result)
            report_path = base / "artifacts" / result["artifact"]
            artifact_root = report_path.parents[3]
            report = audit.validate_output(artifact_root)
            self.assertEqual(report["counts"]["total"], report["counts"]["unsupported"] + report["counts"]["heterogeneous"])
            self.assertEqual(report["triage"]["eligibleForAutomaticPublication"], 0)
            self.assertEqual(sum(1 for p in artifact_root.rglob("*") if p.is_file()), 5)

            cases_path = artifact_root / audit.CASES
            with gzip.open(cases_path, "rt", encoding="utf-8") as handle:
                archive = json.load(handle)
            self.assertTrue(archive["cases"])
            archive["cases"][0]["triage"]["decision"] = "publish_unproven_tariff"
            with gzip.open(cases_path, "wt", encoding="utf-8") as handle:
                json.dump(archive, handle)
            manifest_path = artifact_root / audit.PROVENANCE
            manifest = json.loads(manifest_path.read_text())
            manifest["outputSha256"][audit.CASES.as_posix()] = audit.sha256(cases_path)
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "provenance invalid"):
                audit.validate_output(artifact_root)

    def test_script_failure_is_not_publishable(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            def fail(command, **_):
                return subprocess.CompletedProcess(command, 1)
            with self.assertRaisesRegex(RuntimeError, "failed"):
                audit.run(base, runner=fail)
            self.assertFalse((base / audit.REPORT).exists())


if __name__ == "__main__":
    unittest.main()
