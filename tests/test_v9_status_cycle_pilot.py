import os
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.pilot_v9_status_cycle import advance, record_checkpoint, restore_checkpoint
from v9_rebuild.electroverse import MAPPING, CACHE
from tests.test_v9_electroverse import fixture, save
from v9_rebuild.electroverse_status import STATUS_REPORT, cache_fingerprint, part_path
from tests.test_v9_electroverse_status import part


class StatusCyclePilotTests(unittest.TestCase):
    def test_cross_run_restore_requires_receipt_and_identical_tariff(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GITHUB_SHA="a"*40, GITHUB_RUN_ID="1"):
            root = Path(tmp); incoming = root / "incoming"; tariff = root / "tariff"
            state = incoming / "checkpoints/FR_electroverse_status"
            fixture(state, ["a"]); fixture(tariff, ["a"])
            save(part_path(state, 0), part(0, cache_fingerprint(state), {}))
            record_checkpoint(incoming, [])
            pin = hashlib.sha256((incoming / "checkpoint-manifest.json").read_bytes()).hexdigest()
            args = dict(head="a"*40, run_id=1, manifest_sha=pin)
            restored = restore_checkpoint(incoming, root / "restored", tariff, **args)
            self.assertEqual(len(restored["partitions"]), 1)
            self.assertEqual((root / "restored/checkpoints/FR_electroverse_status" / part_path(Path(), 0)).read_bytes(), part_path(state, 0).read_bytes())
            for changed in ({"head":"b"*40}, {"run_id":2}, {"manifest_sha":"0"*64}):
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    restore_checkpoint(incoming, root / "bad", tariff, **dict(args, **changed))
                self.assertFalse((root / "bad").exists())
            # Same-length altered mapping must fail even when the historical
            # fingerprint (cache manifest metadata) is still identical.
            (tariff / MAPPING).write_bytes((tariff / MAPPING).read_bytes().replace(b'"a"', b'"b"'))
            self.assertEqual(cache_fingerprint(state), cache_fingerprint(tariff))
            with self.assertRaisesRegex(ValueError, "mapping"):
                restore_checkpoint(incoming, root / "bad", tariff, **args)
            (tariff / MAPPING).write_bytes((state / MAPPING).read_bytes())
            shard = tariff / CACHE / "shard-000.json"
            shard.write_bytes(shard.read_bytes().replace(b'"version": 1', b'"version": 2'))
            with self.assertRaisesRegex(ValueError, "cache"):
                restore_checkpoint(incoming, root / "bad", tariff, **args)
            self.assertFalse((root / "bad").exists())

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
