"""Prove the historical fixed-tariff audit depends on obsolete YAML references."""

import json
import os
import runpy
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from v9_rebuild.electroverse import ROOT


class RetiredAuditTests(unittest.TestCase):
    def test_workflow_reference_changes_old_audit_result_without_data_change(self):
        script = ROOT / "scripts/audit_fixed_tariff_refresh.py"
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            data = base / "data/operator_direct/example_official.json"
            data.parent.mkdir(parents=True)
            data.write_text(json.dumps({"country": "FR", "pricePerKwh": 0.5,
                                        "sourceUrl": "https://example.invalid/archived"}))
            (base / ".github/workflows").mkdir(parents=True)
            (base / "reports").mkdir()
            old = Path.cwd()
            try:
                os.chdir(base)
                with redirect_stdout(StringIO()):
                    runpy.run_path(str(script), run_name="__main__")
                first = json.loads((base / "reports/fixed-tariff-refresh-audit.json").read_text())
                (base / ".github/workflows/old.yml").write_text("path: data/operator_direct/example_official.json\n")
                with redirect_stdout(StringIO()):
                    runpy.run_path(str(script), run_name="__main__")
                second = json.loads((base / "reports/fixed-tariff-refresh-audit.json").read_text())
            finally:
                os.chdir(old)
            self.assertFalse(first["unmanaged"][0]["workflowManaged"])
            self.assertTrue(second["managed"][0]["workflowManaged"])
            self.assertEqual(data.read_text(), json.dumps({"country": "FR", "pricePerKwh": 0.5,
                                                           "sourceUrl": "https://example.invalid/archived"}))


if __name__ == "__main__":
    unittest.main()
