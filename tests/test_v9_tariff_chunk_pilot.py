import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.pilot_v9_tariff_chunks import advance
from tests.test_v9_electroverse import fixture, save


class TariffChunkPilotTests(unittest.TestCase):
    def test_time_budget_keeps_upload_reserve_after_completed_chunk(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GITHUB_SHA="a"*40, GITHUB_RUN_ID="1"):
            calls=[];ticks=iter([0,0,2501]);out=Path(tmp)
            def execute(specs, folder, **kwargs):
                calls.append(1)
                state=folder / "checkpoints/FR_electroverse_full"
                fixture(state,["a"])
                save(state / "v9-electroverse-checkpoint.json", {"mode":"full","completed":[0],"pending":None})
                return {"status":"partial_failure","sources":[{"reason":"collector_exit_nonzero"}]}
            result=advance(out,specs=[],chunk_count=2,execute=execute,clock=lambda:next(ticks))
            self.assertEqual(result["status"], "checkpointed")
            self.assertEqual(len(calls),1)
            self.assertTrue((out / "checkpoint-manifest.json").is_file())

    def test_only_successful_chunk_boundaries_continue(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GITHUB_SHA="a"*40, GITHUB_RUN_ID="1"):
            out = Path(tmp)
            calls = []
            def execute(specs, folder, **kwargs):
                calls.append(kwargs)
                if len(calls) == 2:
                    return {"status": "complete"}
                state = folder / "checkpoints/FR_electroverse_full"
                fixture(state, ["a", "b"])
                save(state / "v9-electroverse-checkpoint.json", {"mode": "full", "completed": [0], "pending": None})
                return {"status": "partial_failure", "sources": [{"reason": "collector_exit_nonzero"}]}
            self.assertEqual(advance(out, specs=[], chunk_count=2, execute=execute)["status"], "complete")
            self.assertEqual(len(calls), 2)
            self.assertTrue((out / "checkpoint-manifest.json").is_file())

    def test_graceful_budget_produces_only_a_partial_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GITHUB_SHA="a"*40, GITHUB_RUN_ID="1"):
            out = Path(tmp)
            def execute(specs, folder, **kwargs):
                state = folder / "checkpoints/FR_electroverse_full"
                fixture(state, ["a", "b"])
                save(state / "v9-electroverse-checkpoint.json",
                     {"mode": "full", "completed": [], "pending": {"offset": 0, "pks": ["b"]}})
                return {"status": "partial_failure", "sources": [{"reason": "collector_window_budget"}]}
            ticks=iter([0,0,2501])
            result = advance(out, specs=[], chunk_count=1, execute=execute, clock=lambda:next(ticks))
            self.assertEqual(result["status"], "checkpointed")
            self.assertFalse(result["completeSnapshotValidated"])
            self.assertFalse((out / "objects").exists())

    def test_failed_or_timed_out_chunk_preserves_state_without_retry(self):
        for reason, pending in [("collector_exit_nonzero", {"offset": 0, "pks": ["b"]}), ("collector_timeout", None)]:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GITHUB_SHA="a"*40, GITHUB_RUN_ID="1"):
                out = Path(tmp)
                calls = []
                def execute(specs, folder, **kwargs):
                    calls.append(1)
                    state = folder / "checkpoints/FR_electroverse_full"
                    fixture(state, ["a", "b"])
                    save(state / "v9-electroverse-checkpoint.json", {"mode": "full", "completed": [0], "pending": pending})
                    return {"status": "partial_failure", "sources": [{"reason": reason}]}
                with self.assertRaisesRegex(RuntimeError, "no automatic provider retry"):
                    advance(out, specs=[], chunk_count=2, execute=execute)
                self.assertEqual(len(calls), 1)
                self.assertTrue((out / "checkpoint-manifest.json").is_file())

    def test_second_window_continues_without_restarting_the_chunk(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GITHUB_SHA="a"*40, GITHUB_RUN_ID="1"):
            out=Path(tmp);calls=[]
            def execute(specs, folder, **kwargs):
                calls.append(1)
                if len(calls)==2:
                    return {"status":"complete"}
                state=folder / "checkpoints/FR_electroverse_full"
                fixture(state,["a","b"])
                save(state / "v9-electroverse-checkpoint.json",
                     {"mode":"full","completed":[],"pending":{"offset":0,"pks":["b"]}})
                return {"status":"partial_failure","sources":[{"reason":"collector_window_budget"}]}
            ticks=iter([0,0,1200])
            result=advance(out,specs=[],chunk_count=1,execute=execute,clock=lambda:next(ticks))
            self.assertEqual(result["status"],"complete")
            self.assertEqual(len(calls),2)

    def test_complete_remaining_can_checkpoint_after_crossing_a_chunk(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GITHUB_SHA="a"*40, GITHUB_RUN_ID="1"):
            out=Path(tmp);calls=[]
            state=out / "checkpoints/FR_electroverse_full"
            fixture(state,["a","b"])
            save(state / "v9-electroverse-checkpoint.json",
                 {"mode":"full","completed":[0,6000],"pending":{"offset":12000,"pks":["a","b"]}})
            def execute(specs, folder, **kwargs):
                calls.append(1)
                save(state / "v9-electroverse-checkpoint.json",
                     {"mode":"full","completed":[0,6000,12000],"pending":{"offset":18000,"pks":["b"]}})
                return {"status":"partial_failure","sources":[{"reason":"collector_window_budget"}]}
            result=advance(out,specs=[{"finish_remaining_chunks":True}],chunk_count=4,
                           execute=execute,max_provider_windows=1)
            self.assertEqual(result["status"],"checkpointed")
            self.assertEqual(len(calls),1)
            self.assertTrue((out / "checkpoint-manifest.json").is_file())

    def test_complete_remaining_stops_first_failure_after_chunk_crossing(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GITHUB_SHA="a"*40, GITHUB_RUN_ID="1"):
            out=Path(tmp);calls=[]
            state=out / "checkpoints/FR_electroverse_full"
            fixture(state,["a","b"])
            save(state / "v9-electroverse-checkpoint.json",
                 {"mode":"full","completed":[0,6000],"pending":{"offset":12000,"pks":["a","b"]}})
            def execute(specs, folder, **kwargs):
                calls.append(1)
                save(state / "v9-electroverse-checkpoint.json",
                     {"mode":"full","completed":[0,6000,12000],"pending":{"offset":18000,"pks":["b"]}})
                return {"status":"partial_failure","sources":[{"reason":"collector_exit_nonzero"}]}
            with self.assertRaisesRegex(RuntimeError,"no automatic provider retry"):
                advance(out,specs=[{"finish_remaining_chunks":True}],chunk_count=4,
                        execute=execute,max_provider_windows=1)
            self.assertEqual(len(calls),1)
            self.assertTrue((out / "checkpoint-manifest.json").is_file())

    def test_complete_remaining_rejects_cursor_regression(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GITHUB_SHA="a"*40, GITHUB_RUN_ID="1"):
            out=Path(tmp);calls=[]
            state=out / "checkpoints/FR_electroverse_full"
            fixture(state,["a","b"])
            save(state / "v9-electroverse-checkpoint.json",
                 {"mode":"full","completed":[0,6000],"pending":{"offset":12000,"pks":["a","b"]}})
            def execute(specs, folder, **kwargs):
                calls.append(1)
                save(state / "v9-electroverse-checkpoint.json",
                     {"mode":"full","completed":[0],"pending":{"offset":6000,"pks":["a"]}})
                return {"status":"partial_failure","sources":[{"reason":"collector_window_budget"}]}
            with self.assertRaisesRegex(RuntimeError,"lost its verified chunk lineage"):
                advance(out,specs=[{"finish_remaining_chunks":True}],chunk_count=4,
                        execute=execute,max_provider_windows=1)
            self.assertEqual(len(calls),1)

    def test_no_progress_between_windows_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GITHUB_SHA="a"*40, GITHUB_RUN_ID="1"):
            out=Path(tmp)
            def execute(specs, folder, **kwargs):
                state=folder / "checkpoints/FR_electroverse_full"
                fixture(state,["a","b"])
                save(state / "v9-electroverse-checkpoint.json",
                     {"mode":"full","completed":[],"pending":{"offset":0,"pks":["b"]}})
                return {"status":"partial_failure","sources":[{"reason":"collector_window_budget"}]}
            with self.assertRaisesRegex(RuntimeError,"did not advance"):
                advance(out,specs=[],chunk_count=1,execute=execute,clock=lambda:0)


    def test_one_provider_window_is_persisted_without_second_invocation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GITHUB_SHA="a"*40, GITHUB_RUN_ID="1"):
            out=Path(tmp);calls=[]
            def execute(specs, folder, **kwargs):
                calls.append(1)
                state=folder / "checkpoints/FR_electroverse_full"
                fixture(state,["a","b"])
                save(state / "v9-electroverse-checkpoint.json",
                     {"mode":"full","completed":[],"pending":{"offset":0,"pks":["b"]}})
                return {"status":"partial_failure","sources":[{"reason":"collector_window_budget"}]}
            result=advance(out,specs=[],chunk_count=1,execute=execute,max_provider_windows=1)
            self.assertEqual(result["status"],"checkpointed")
            self.assertEqual(result["reason"],"pilot_provider_window_limit")
            self.assertFalse(result["completeSnapshotValidated"])
            self.assertEqual(len(calls),1)
            self.assertTrue((out / "checkpoint-manifest.json").is_file())

if __name__ == "__main__":
    unittest.main()
