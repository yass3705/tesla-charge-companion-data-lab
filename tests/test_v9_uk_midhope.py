"""Offline exact-socket Midhope migration checks."""

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from v9_rebuild.orchestrator import read_sources, run_source
from v9_rebuild.uk_midhope import OUTPUT, PROOF, RAW, REPORT, run, validate_output


class MidhopeMigrationTests(unittest.TestCase):
    def test_historical_builder_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "historical")
            payload = validate_output(root / "historical")
            self.assertEqual(payload["sources"][0]["locations"][0]["name"], "Midhope Road")
            self.assertTrue((root / "historical" / OUTPUT).is_file())
            self.assertTrue((root / "historical" / REPORT).is_file())
            spec = next(row for row in read_sources() if row["id"] == "GB:midhope_verified")

            def simulated_process(command, **kwargs):
                run(Path(command[command.index("--out") + 1]))
                return SimpleNamespace(returncode=0)

            result = run_source(spec, root / "artifacts", runner=simulated_process)
            self.assertEqual(result["status"], "ok")

    def test_missing_proof_corrupt_input_and_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "valid")
            (root / "valid" / PROOF).unlink()
            with self.assertRaises(OSError):
                validate_output(root / "valid")
            run(root / "corrupt")
            (root / "corrupt" / OUTPUT).write_bytes(b"broken")
            with self.assertRaises((OSError, gzip.BadGzipFile)):
                validate_output(root / "corrupt")
            run(root / "wrong_scope")
            path = root / "wrong_scope" / REPORT
            report = json.loads(path.read_text())
            report["connectorIds"] = []
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "provenance"):
                validate_output(root / "wrong_scope")


if __name__ == "__main__":
    unittest.main()
