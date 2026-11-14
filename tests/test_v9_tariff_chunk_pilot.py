import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.pilot_v9_tariff_chunks import advance
from tests.test_v9_electroverse import fixture, save


class TariffChunkPilotTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
