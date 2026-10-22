"""The dated Belgium Shell decision is reproducible but cannot drift silently."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from v9_rebuild import belgium_gap_archive
from v9_rebuild.orchestrator import read_sources, run_source


class BelgiumGapArchiveTests(unittest.TestCase):
    def test_replay_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            belgium_gap_archive.run(base / "replay")
            final = belgium_gap_archive.validate_output(base / "replay")
            self.assertEqual(final["decisions"]["resolvedExactOfficial"],
                             json.loads((base / "replay" / belgium_gap_archive.SHELL).read_text())["count"])
            source = next(row for row in read_sources() if row["id"] == "BE:final_gap_archive")
            result = run_source(source, base / "artifacts", attempts=1)
            self.assertEqual(result["status"], "ok", result)
            self.assertTrue(any("shell_belgium_official" in str(item) for item in result["files"]))

    def test_archived_price_and_input_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            belgium_gap_archive.run(base)
            shell = base / belgium_gap_archive.SHELL
            payload = json.loads(shell.read_text())
            payload["entries"][0]["tariff"]["price"] = 1.79
            shell.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "decision changed"):
                belgium_gap_archive.validate_output(base)
            shell.write_bytes((belgium_gap_archive.ROOT / belgium_gap_archive.SHELL).read_bytes())
            detail = base / belgium_gap_archive.DETAIL
            payload = json.loads(detail.read_text())
            payload["targets"]["Shell Recharge"]["items"][0]["powerW"] = [999999]
            detail.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "input changed"):
                belgium_gap_archive.validate_output(base)

    def test_script_failure_is_not_a_published_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fail(command, **_):
                return subprocess.CompletedProcess(command, 1)
            with self.assertRaises(RuntimeError):
                belgium_gap_archive.run(Path(tmp), runner=fail)
            self.assertFalse((Path(tmp) / belgium_gap_archive.FINAL).exists())


if __name__ == "__main__":
    unittest.main()
