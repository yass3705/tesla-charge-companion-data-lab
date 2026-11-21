import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.scheduled_v9_reve import ID, NAME, REPO, TITLE, WORKFLOW, previous_run, restore
from v9_rebuild.reve_stream import FILES, SEED_CHECKPOINT, validate_checkpoint


class ScheduledReveTest(unittest.TestCase):
    def test_never_rewind_past_failed_job(self):
        run = dict(id=11, run_number=7, display_title=TITLE, status="completed", conclusion="failure",
                   event="schedule", workflow_id=WORKFLOW, head_branch="main", repository={"full_name": REPO})
        get = lambda path: json.dumps({"workflow_runs": [run, dict(run, id=10, run_number=6)]})
        self.assertEqual(previous_run({"run_number": 8}, get)["id"], 11)
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, "refusing to rewind"):
            restore(run, Path(tmp), lambda path: '{"artifacts": []}')

    def test_exact_generation_restored_and_damaged_zip_refused(self):
        run = {"id": 123, "head_sha": "a"*40}
        folder = validate_checkpoint(SEED_CHECKPOINT)
        receipt = {"source": ID, "runId": run["id"], "head": run["head_sha"],
                   "generation": folder.name, "state": "partial"}
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("receipt.json", json.dumps(receipt))
            z.write(SEED_CHECKPOINT / "current.json", "current.json")
            for name in FILES:
                z.write(folder / name, f"generations/{folder.name}/{name}")
        raw = stream.getvalue()
        artifact = dict(id=456, name=NAME, expired=False, size_in_bytes=len(raw),
                        digest="sha256:"+hashlib.sha256(raw).hexdigest(),
                        workflow_run=dict(run, head_branch="main"))
        def get(path):
            return raw if path.endswith("/zip") else json.dumps({"artifacts": [artifact]})
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "checkpoint"
            self.assertEqual(restore(run, checkpoint, get), receipt)
            self.assertEqual(validate_checkpoint(checkpoint).name, folder.name)
            artifact["digest"] = "sha256:" + "0"*64
            with self.assertRaisesRegex(ValueError, "integrity"):
                restore(run, Path(tmp) / "invalid", get)
            self.assertFalse((Path(tmp) / "invalid").exists())
