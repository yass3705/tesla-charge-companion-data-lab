import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.pilot_v9_status_checkpoint import CHECKPOINT, SOURCE, BRANCH, verify_package, verify_resume
from v9_rebuild.orchestrator import artifact_digest
from test_v9_electroverse import fixture


class CheckpointHandoffTests(unittest.TestCase):
    def package(self, root):
        state = root / CHECKPOINT
        fixture(state, [])
        digest, files = artifact_digest(state)
        m = dict(state="partial_checkpoint", source=SOURCE, branch=BRANCH,
                 headSha="a" * 40, runId=123, sha256=digest, files=files)
        (root / "checkpoint-manifest.json").write_text(json.dumps(m))
        return state, m

    def test_exact_package_and_provenance_are_required(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); state, m = self.package(root)
            self.assertEqual(verify_package(root, head="a" * 40, run_id=123), state)
            for field, bad in [("branch", "main"), ("headSha", "b" * 40),
                               ("runId", 124), ("state", "complete"), ("sha256", "0" * 64)]:
                altered = dict(m); altered[field] = bad
                (root / "checkpoint-manifest.json").write_text(json.dumps(altered))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    verify_package(root, head="a" * 40, run_id=123)

    def test_extra_file_fails_integrity(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); state, _ = self.package(root)
            (state / "unexpected.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "integrity"):
                verify_package(root, head="a" * 40, run_id=123)

    def test_resume_keeps_all_prior_entries_and_independent_partitions(self):
        before = {"fingerprint": "cache", "partitions": [
            {"partition": 0, "startedAt": "2026-11-14T12:00:00Z", "entries": {"A": {"E1": "AVAILABLE"}}},
            {"partition": 1, "entries": {"B": {"E2": "CHARGING"}}}]}
        after = copy.deepcopy(before)
        after["partitions"][0]["entries"]["C"] = {"E3": "UNKNOWN"}
        verify_resume(before, after, {"partition": 0})
        for mutation in ("entry", "partition", "window", "cache"):
            altered = copy.deepcopy(after)
            if mutation == "entry": del altered["partitions"][0]["entries"]["A"]
            if mutation == "partition": altered["partitions"][1]["entries"]["B"] = {}
            if mutation == "window": altered["partitions"][0]["startedAt"] = "later"
            if mutation == "cache": altered["fingerprint"] = "different"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                verify_resume(before, altered, {"partition": 0})


if __name__ == "__main__":
    unittest.main()
