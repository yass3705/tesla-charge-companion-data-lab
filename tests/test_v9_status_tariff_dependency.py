import json
import shutil
import tempfile
import unittest
from pathlib import Path

from v9_rebuild.orchestrator import artifact_digest, sha256, status_tariff_dependency
from v9_rebuild.electroverse import CACHE
from tests.test_v9_electroverse import fixture, save


def dependency(out):
    bundle = out / "input_dependencies/FR_electroverse_full"
    staged = out / "fixture-cache"
    fixture(staged, [])
    digest, files = artifact_digest(staged)
    state = bundle / "objects/FR_electroverse_full" / digest
    state.parent.mkdir(parents=True)
    staged.rename(state)
    artifact = state / CACHE / "manifest.json"
    save(bundle / "manifest.json", {"schema_version": 1, "status": "complete", "sources": [{
        "source": "FR:electroverse_full", "module": "electroverse", "status": "ok",
        "artifact": artifact.relative_to(bundle).as_posix(), "sha256": sha256(artifact),
        "artifact_set_sha256": digest, "files": files}]})
    return state


class StatusTariffDependencyTests(unittest.TestCase):
    def test_new_tariff_state_replaces_archive_without_discarding_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            state = dependency(out)
            checkpoint = out / "checkpoints/FR_electroverse_status"
            shutil.copytree(state, checkpoint)
            manifest = checkpoint / CACHE / "manifest.json"
            payload = json.loads(manifest.read_text());payload["generatedAt"] = "2026-01-01T00:00:00Z"
            save(manifest, payload)
            before, files = artifact_digest(checkpoint)
            self.assertEqual(status_tariff_dependency(out, checkpoint, None), state)
            self.assertFalse(checkpoint.exists())
            archive = out / "checkpoint_history/FR_electroverse_status" / before
            self.assertEqual(artifact_digest(archive), (before, files))
            self.assertEqual(status_tariff_dependency(out, checkpoint, None), state)

    def test_compatible_checkpoint_and_previous_state_are_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp);state = dependency(out)
            checkpoint = out / "checkpoints/FR_electroverse_status"
            shutil.copytree(state, checkpoint)
            previous = out / "previous";shutil.copytree(state, previous)
            before = artifact_digest(checkpoint)
            self.assertEqual(status_tariff_dependency(out, checkpoint, previous), previous)
            self.assertEqual(artifact_digest(checkpoint), before)
            self.assertFalse((out / "checkpoint_history").exists())

    def test_missing_or_corrupt_dependency_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp);(out / "input_dependencies").mkdir()
            checkpoint = out / "checkpoints/FR_electroverse_status"
            with self.assertRaises(ValueError):status_tariff_dependency(out, checkpoint, out / "old")
            state = dependency(out)
            (state / CACHE / "manifest.json").write_text('{}')
            with self.assertRaises(ValueError):status_tariff_dependency(out, checkpoint, out / "old")


if __name__ == "__main__":
    unittest.main()
