import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.pilot_v9_status_cycle import advance
from tests.test_v9_electroverse import fixture, save
from v9_rebuild.electroverse_status import STATUS_REPORT, cache_fingerprint, part_path
from tests.test_v9_electroverse_status import part


class StatusCyclePilotTests(unittest.TestCase):
    def executor(self, reports):
        calls = []
        def run(specs, out, **kwargs):
            calls.append(kwargs)
            report = reports[len(calls)-1]
            if report == "complete":return {"status": "complete"}
            state = out / "checkpoints/FR_electroverse_status"
            fixture(state, [])
            if report.get("complete"):
                save(part_path(state, report["partition"]), part(report["partition"], cache_fingerprint(state), {}))
            save(state / STATUS_REPORT, report)
            return {"status": "partial_failure", "sources": [{"reason": "collector_exit_nonzero"}]}
        return calls, run

    def test_successful_partitions_continue_until_real_finalization(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GITHUB_SHA="a"*40, GITHUB_RUN_ID="1"):
            calls, run = self.executor([{"partition": 0, "complete": True}, "complete"])
            result = advance(Path(tmp), specs=[], execute=run)
            self.assertEqual(result["state"], "complete");self.assertEqual(len(calls), 2)

    def test_incomplete_part_or_explicit_limit_keeps_checkpoint_without_retry(self):
        for complete in (True, False):
            with self.subTest(complete=complete), tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GITHUB_SHA="a"*40, GITHUB_RUN_ID="1"):
                calls, run = self.executor([{"partition": 0, "complete": complete}])
                out=Path(tmp);result=advance(out,specs=[],execute=run,max_partitions=1)
                self.assertEqual(result["state"],"partial_checkpoint");self.assertEqual(len(calls),1)
                self.assertTrue((out/"checkpoint-manifest.json").is_file())

    def test_upload_time_reserve_prevents_starting_another_partition(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GITHUB_SHA="a"*40, GITHUB_RUN_ID="1"):
            calls, run = self.executor([{"partition": 0, "complete": True}])
            ticks=iter([0,0,901])
            result=advance(Path(tmp),specs=[],execute=run,budget_seconds=3600,clock=lambda:next(ticks))
            self.assertEqual(result["reason"],"bounded_time_budget");self.assertEqual(len(calls),1)


if __name__ == "__main__":unittest.main()
