"""Offline proof that every bounded Electroverse segment yields a usable artifact.

No network access or real supplier calls, including deliberate 429/freshness stops.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import resilient_v9_electroverse_status as resilient
from tests.test_v9_electroverse_status import fixture, part
from v9_rebuild.electroverse_status import (
    IncompleteStatus, STATUS_REPORT, cache_fingerprint, part_path, stage,
    validate_partial,
)


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


class SegmentedStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.parent = self.root / "parent"
        fixture(self.parent, ["A", "B"])
        self.root_checkpoint = self.root / "original"
        stage(self.parent, self.root_checkpoint)
        self.fingerprint = cache_fingerprint(self.root_checkpoint)
        self.initial = part(
            0, self.fingerprint, {"A": {"EVSE-A": "AVAILABLE"}},
            errors={"B": {"error": "single_paged_unavailable", "attempts": 1}},
            expected=2,
        )
        write(part_path(self.root_checkpoint, 0), self.initial)
        self.initial_partial = validate_partial(self.root_checkpoint)
        self.initial_report = {
            "partition": 0, "verifiedLocations": 1,
            "sourceFingerprint": self.fingerprint, "rateLimit": None,
        }
        write(self.root_checkpoint / STATUS_REPORT, self.initial_report)
        self.out = self.root / "out"
        self.env_file = self.root / "github.env"
        self.output_file = self.root / "github.output"
        self.calls = []
        self.rate_limited = False

    def ready(self):
        args = SimpleNamespace(
            out=self.out, bundle=self.parent, checkpoint=self.root_checkpoint,
            checkpoint_fileset="a" * 64, checkpoint_run=45058177243,
            checkpoint_artifact=14770651817,
            checkpoint_verified=1, checkpoint_errors=1,
            checkpoint_partitions=1,
        )
        with (
            patch.dict(os.environ, {"GITHUB_REF_NAME": resilient.BRANCH,
                                    "ELECTROVERSE_API_KEY": "offline-simulation"}),
            patch.object(resilient, "checked_source", return_value=self.parent),
            patch.object(resilient, "checked_status_checkpoint",
                         return_value=(self.root_checkpoint, self.initial_partial,
                                       self.initial_report)),
        ):
            resilient.prepare(args)
        state = resilient.read_progress(self.out)
        self.assertEqual(state["sweepNext"], 0)
        self.assertEqual(state["resumedFrom"]["artifact"], 14770651817)

    def fake_run(self, work, *, partition):
        self.calls.append(partition)
        path = part_path(work, partition)
        old = json.loads(path.read_text()) if path.is_file() else None
        # No artificial successes during sweep; retain original PK A and error B.
        if old is not None:
            data = old
        else:
            data = part(partition, self.fingerprint, {}, expected=0)
        write(path, data)
        limit = (
            {"phase": "status_page", "httpStatus": 429,
             "resumeNotBeforeUtc": "2026-11-24T00:00:00Z"}
            if self.rate_limited else None
        )
        write(work / STATUS_REPORT, {
            "partition": partition, "sourceFingerprint": self.fingerprint,
            "verifiedLocations": len(data["entries"]),
            "rateLimit": limit,
            "rateLimitRecovery": {
                "budgetScope": "station_pk",
                "maxSecondsPerStation": 480, "totalWaitSeconds": 60,
                "maxStationWaitSeconds": 60,
            },
        })
        raise IncompleteStatus("Expected incomplete national source")

    def execute(self, index=0, phase="sweep"):
        args = SimpleNamespace(out=self.out, partition=index, phase=phase)
        with (
            patch.dict(os.environ, {
                "GITHUB_REF_NAME": resilient.BRANCH,
                "ELECTROVERSE_API_KEY": "offline-simulation",
                "GITHUB_ENV": str(self.env_file),
                "GITHUB_OUTPUT": str(self.output_file),
            }),
            patch.object(resilient, "run", side_effect=self.fake_run),
        ):
            resilient.collect_segment(args)

    def test_each_segment_upload_is_self_contained_and_preserves_parent(self):
        self.ready()
        self.execute()
        self.assertEqual(self.calls, [0])
        state = resilient.read_progress(self.out)
        self.assertEqual(state["sweepNext"], 1)
        self.assertFalse(state["halted"])
        staging = self.out / "staged"
        self.assertTrue((staging / "manifest.json").exists())
        self.assertTrue((staging / "checkpoint-manifest.json").exists())
        self.assertTrue((staging / "checkpoints/FR_electroverse_status").exists())
        m = json.loads((staging / "checkpoint-manifest.json").read_text())
        self.assertEqual(m["verifiedLocations"], 1)
        self.assertEqual(m["partitionCount"], 1)
        self.assertFalse(m["completeSnapshotValidated"])
        self.assertEqual(m["resumedFrom"]["artifact"], 14770651817)
        checked, partial, _report = resilient.checked_status_checkpoint(
            staging, self.out / "work", fileset_sha=m["sha256"],
            verified_locations=1, error_count=1, partition_count=1,
        )
        self.assertEqual(partial["verified_locations"], 1)
        self.assertEqual(partial["partitions"][0]["entries"]["A"],
                         {"EVSE-A": "AVAILABLE"})
        self.assertNotIn("manifest.json", [
            x.name for x in (checked / "data/electroverse/live_statuses").iterdir()
        ])
        self.assertIn("checkpoint_ready=true", self.output_file.read_text())
        # The live working directory survives snapshot packaging for the next step.
        self.assertEqual(validate_partial(self.out / "work")["verified_locations"], 1)
        self.execute(index=1)
        self.assertEqual(self.calls, [0, 1])
        self.assertEqual(resilient.read_progress(self.out)["sweepNext"], 2)
        self.assertEqual(json.loads((staging / "checkpoint-manifest.json").read_text())
                         ["partitionCount"], 2)

    def test_429_stop_has_durable_checkpoint_before_next_step(self):
        self.ready()
        self.rate_limited = True
        self.execute()
        state = resilient.read_progress(self.out)
        self.assertTrue(state["halted"])
        self.assertEqual(state["stopReason"], "provider_rate_limited")
        self.assertIn("STATUS_HALT=true", self.env_file.read_text())
        self.assertEqual(json.loads((self.out / "staged/checkpoint-manifest.json")
                                    .read_text())["reason"], "provider_rate_limited")
        with (
            patch.dict(os.environ, {"GITHUB_REF_NAME": resilient.BRANCH}),
            self.assertRaisesRegex(ValueError, "halted"),
        ):
            resilient.collect_segment(SimpleNamespace(
                out=self.out, partition=1, phase="sweep"))
        self.assertEqual(self.calls, [0])

    def test_stale_partition_refuses_supplier_but_saves_checkpoint(self):
        self.ready()
        old = json.loads(part_path(self.out / "work", 0).read_text())
        old["startedAt"] = (datetime.now(timezone.utc) -
                            timedelta(hours=17)).isoformat()
        write(part_path(self.out / "work", 0), old)
        with patch.dict(os.environ, {
            "GITHUB_REF_NAME": resilient.BRANCH,
            "ELECTROVERSE_API_KEY": "offline-simulation",
            "GITHUB_ENV": str(self.env_file),
            "GITHUB_OUTPUT": str(self.output_file),
        }):
            resilient.collect_segment(SimpleNamespace(
                out=self.out, partition=0, phase="sweep"))
        self.assertEqual(self.calls, [])
        self.assertTrue(resilient.read_progress(self.out)["halted"])
        self.assertEqual(resilient.read_progress(self.out)["stopReason"],
                         "checkpoint_stale_or_near_expiry")
        self.assertTrue((self.out / "staged/checkpoint-manifest.json").is_file())

    def test_workflow_places_durable_upload_after_every_unit(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/v9-electroverse-status-rebuild.yml").read_text()
        self.assertNotIn("Retain partial statuses and fingerprinted checkpoint", workflow)
        self.assertIn("timeout-minutes: 300", workflow)
        self.assertEqual(workflow.count("- name: Bounded "), 32)
        self.assertEqual(workflow.count("- name: Preserve immutable "), 32)
        for phase in ("sweep", "recovery"):
            for i in range(16):
                idx = f"{i:02d}"
                step = f"- name: Bounded {phase} {idx}"
                uploaded = f"- name: Preserve immutable {phase} {idx} checkpoint"
                self.assertIn(step, workflow)
                self.assertIn(uploaded, workflow)
                self.assertLess(workflow.index(step), workflow.index(uploaded))
                self.assertIn(f"tcc-v9-electroverse-status-stage-{phase}-{idx}", workflow)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertIn("steps.status_finish.outputs.collection_state == 'complete'", workflow)


if __name__ == "__main__":
    unittest.main()
