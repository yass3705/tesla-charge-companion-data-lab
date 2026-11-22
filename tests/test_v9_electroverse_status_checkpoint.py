"""Offline regression tests for checkpointed Electroverse status reuse."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.pilot_v9_electroverse_status import (
    SOURCE_ARTIFACT, SOURCE_RUN, SOURCE_ZIP_SHA, checked_status_checkpoint,
    resume_eligibility,
)
from tests.test_v9_electroverse_status import fixture, part, FixtureRunner
from v9_rebuild.electroverse_status import (
    STATUS, STATUS_REPORT, IncompleteStatus, cache_fingerprint, part_path,
    run, stage, validate_partial,
)
from v9_rebuild.orchestrator import artifact_digest


class CheckpointRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "tariff-parent"
        fixture(self.source, ["A", "B"])
        self.archive = self.root / "artifact"
        self.checkpoint = self.archive / "checkpoints/FR_electroverse_status"
        stage(self.source, self.checkpoint)
        fingerprint = cache_fingerprint(self.checkpoint)
        self.saved = part(0, fingerprint, {"A": {"EVSE-A": "AVAILABLE"}},
                          errors={"B": {"attempts": 1, "error": "single_paged_unavailable"}},
                          expected=2)
        path = part_path(self.checkpoint, 0)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.saved) + "\n")
        self.report = {
            "partition": 0, "sourceFingerprint": fingerprint, "verifiedLocations": 1,
            "rateLimit": {"httpStatus": 429, "resumeNotBeforeUtc":
                          (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()},
        }
        rp = self.checkpoint / STATUS_REPORT
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(self.report) + "\n")
        self.publish_metadata()

    def publish_metadata(self):
        digest, files = artifact_digest(self.checkpoint)
        self.fileset = digest
        metadata = {
            "schemaVersion": 1, "source": "FR:electroverse_status",
            "branch": "rebuild/v9-20261020", "state": "partial_checkpoint",
            "parentRun": SOURCE_RUN, "parentArtifact": SOURCE_ARTIFACT,
            "parentZipSha256": SOURCE_ZIP_SHA,
            "sourceFingerprint": cache_fingerprint(self.checkpoint),
            "sha256": digest, "files": files,
            "verifiedLocations": 1, "partitionCount": 1,
            "reason": "provider_rate_limited", "completeSnapshotValidated": False,
        }
        (self.archive / "checkpoint-manifest.json").write_text(json.dumps(metadata) + "\n")
        (self.archive / "manifest.json").write_text(json.dumps({
            "schema_version": 1, "status": "partial_failure",
            "sources": [{"source": "FR:electroverse_status", "status": "failed",
                         "reason": "provider_rate_limited",
                         "lastPartitionReport": self.report}],
        }) + "\n")

    def check(self):
        return checked_status_checkpoint(
            self.archive, self.source, fileset_sha=self.fileset,
            verified_locations=1, error_count=1, partition_count=1,
        )

    def test_pinned_checkpoint_is_immutable_and_reuses_success_without_retry(self):
        checkpoint, partial, report = self.check()
        self.assertEqual(partial["verified_locations"], 1)
        self.assertEqual(len(partial["partitions"][0]["errors"]), 1)
        eligible, reason = resume_eligibility(partial, report, datetime.now(timezone.utc))
        self.assertTrue(eligible, reason)
        resumed = self.root / "resumed"
        shutil.copytree(checkpoint, resumed)
        self.assertEqual(validate_partial(resumed)["verified_locations"], 1)
        with patch.dict(os.environ, {"ELECTROVERSE_API_KEY": "fixture-only"}):
            fake = FixtureRunner()
            with self.assertRaises(IncompleteStatus):
                run(resumed, source=self.source, partition=0, runner=fake)
        after = json.loads(part_path(resumed, 0).read_text())
        self.assertEqual(after["entries"]["A"], {"EVSE-A": "AVAILABLE"})
        self.assertEqual(after["entries"]["B"], {"EVSE-B": "CHARGING"})
        self.assertEqual(fake.seen, [0])
        self.assertNotIn("B", after["errors"])
        self.assertFalse((resumed / STATUS / "manifest.json").exists())

    def test_tampered_member_fails_file_sha(self):
        partition = part_path(self.checkpoint, 0)
        partition.write_text(partition.read_text().replace("AVAILABLE", "CHARGING"))
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.check()

    def test_modified_parent_is_rejected_even_with_recomputed_manifest(self):
        mapping = self.checkpoint / "data/electroverse/irve_location_mapping.json"
        mapping.write_bytes(mapping.read_bytes() + b" ")
        self.publish_metadata()
        with self.assertRaisesRegex(ValueError, "tariff parent"):
            self.check()

    def test_foreign_source_and_fake_promotion_are_rejected(self):
        metadata = json.loads((self.archive / "checkpoint-manifest.json").read_text())
        metadata["sourceFingerprint"] = "f" * 64
        (self.archive / "checkpoint-manifest.json").write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            self.check()
        self.publish_metadata()
        top = json.loads((self.archive / "manifest.json").read_text())
        top["status"] = "complete"
        (self.archive / "manifest.json").write_text(json.dumps(top))
        with self.assertRaisesRegex(ValueError, "unpromotable"):
            self.check()

    def test_cooldown_and_expiry_fail_closed(self):
        checkpoint, partial, report = self.check()
        now = datetime.now(timezone.utc)
        waiting = dict(report)
        waiting["rateLimit"] = {"httpStatus": 429,
                               "resumeNotBeforeUtc": (now + timedelta(minutes=5)).isoformat()}
        self.assertEqual(resume_eligibility(partial, waiting, now),
                         (False, "provider_cooldown_active"))
        stale = dict(partial)
        stale_part = dict(partial["partitions"][0])
        stale_part["startedAt"] = (now - timedelta(hours=17)).isoformat()
        stale["partitions"] = [stale_part]
        self.assertEqual(resume_eligibility(stale, report, now),
                         (False, "checkpoint_stale_or_near_expiry"))


if __name__ == "__main__":
    unittest.main()
