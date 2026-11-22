"""End-to-end offline checks for status sweep, last-pass recovery and stopping rules.

No provider/network requests; fixtures stage an isolated parent and mocked per-partition runner.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import pilot_v9_electroverse_status as pilot
from tests.test_v9_electroverse_status import fixture, part
from v9_rebuild.electroverse_status import (
    IncompleteStatus, STATUS_REPORT, cache_fingerprint, part_path, stage, validate_partial,
)


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


class DeferredSweepTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        fixture(self.source, ["A"])
        self.checkpoint = self.root / "initial-checkpoint"
        stage(self.source, self.checkpoint)
        self.fingerprint = cache_fingerprint(self.checkpoint)
        initial = part(0, self.fingerprint, {}, errors={
            "A": {"attempts": 1, "error": "single_paged_unavailable"},
        }, expected=1)
        write(part_path(self.checkpoint, 0), initial)
        self.initial_partial = validate_partial(self.checkpoint)
        self.initial_report = {
            "partition": 0, "sourceFingerprint": self.fingerprint,
            "verifiedLocations": 0, "rateLimit": None,
        }
        self.out = self.root / "out"
        self.seen = []
        self.outcome = []
        self.stop_partition = None
        self.recovery_succeeds = True

    def mock_run(self, work: Path, *, source: Path, partition: int) -> None:
        phase = "recovery" if os.environ.get("ELECTROVERSE_STATUS_RECOVERY_ONLY") == "1" else "sweep"
        self.seen.append((phase, partition))
        assert source == self.source
        assert os.environ["ELECTROVERSE_STATUS_429_MAX_SECONDS_PER_STATION"] == "480"
        assert "ELECTROVERSE_STATUS_429_BUDGET_SECONDS" not in os.environ
        if phase == "sweep":
            assert os.environ["ELECTROVERSE_STATUS_DEFER_FAILED"] == "1"
        else:
            assert os.environ["ELECTROVERSE_STATUS_DEFER_FAILED"] == "0"
        prior = json.loads(part_path(work, partition).read_text()) if part_path(work, partition).exists() else None
        if partition == 0:
            if phase == "recovery" and self.recovery_succeeds:
                data = part(0, self.fingerprint, {"A": {"EVSE-A": "AVAILABLE"}},
                            started=prior["startedAt"], expected=1)
            else:
                data = part(0, self.fingerprint, {}, errors={
                    "A": {"attempts": 2 if phase == "recovery" else 1,
                          "error": "single_paged_unavailable"},
                }, started=prior["startedAt"], expected=1)
        else:
            data = part(partition, self.fingerprint, {}, expected=0)
        write(part_path(work, partition), data)
        limit = None
        if partition == self.stop_partition:
            limit = {
                "phase": "status_batch", "httpStatus": 429,
                "resumeNotBeforeUtc": "2026-11-23T18:00:00Z",
            }
        write(work / STATUS_REPORT, {
            "partition": partition, "sourceFingerprint": self.fingerprint,
            "verifiedLocations": len(data["entries"]), "rateLimit": limit,
            "rateLimitRecovery": {"totalWaitSeconds": 0,
                                  "maxStationWaitSeconds": 0,
                                  "maxSecondsPerStation": 480,
                                  "budgetScope": "station_pk"},
        })
        raise IncompleteStatus("fixture partition recorded")

    def execute(self):
        args = ["pilot", "--bundle", str(self.source), "--checkpoint", str(self.checkpoint),
                "--checkpoint-fileset", "a" * 64, "--checkpoint-run", "45053244431",
                "--checkpoint-artifact", "14766791724", "--checkpoint-verified", "1423",
                "--checkpoint-errors", "4", "--checkpoint-partitions", "1",
                "--out", str(self.out), "--mode", "collect", "--budget-seconds", "18000"]

        def complete(work, out, resume):
            self.outcome.append(("complete", work))
        def checkpoint(work, out, reason, last_report, resume):
            self.outcome.append((reason, work, last_report))

        with (patch.object(sys, "argv", args),
              patch.dict(os.environ, {"GITHUB_REF_NAME": pilot.BRANCH,
                                      "ELECTROVERSE_API_KEY": "synthetic-only",
                                      "GITHUB_OUTPUT": ""}),
              patch.object(pilot, "checked_source", return_value=self.source),
              patch.object(pilot, "checked_status_checkpoint",
                           return_value=(self.checkpoint, self.initial_partial, self.initial_report)),
              patch.object(pilot, "run", side_effect=self.mock_run),
              patch.object(pilot, "finish_complete", side_effect=complete),
              patch.object(pilot, "finish_checkpoint", side_effect=checkpoint)):
            pilot.main()

    def test_all_sixteen_are_visited_before_retrying_individual_failures(self):
        self.execute()
        self.assertEqual(self.seen, [("sweep", i) for i in range(16)] + [("recovery", 0)])
        self.assertEqual(self.outcome[0][0], "complete")
        self.assertFalse((self.out / "work/data/electroverse/live_statuses/deferred-failures.json").exists())
        self.assertEqual(validate_partial(self.out / "work")["verified_locations"], 1)

    def test_unresolved_failure_stays_in_tracked_queue_and_is_never_promoted(self):
        self.recovery_succeeds = False
        self.execute()
        self.assertEqual(self.seen, [("sweep", i) for i in range(16)] + [("recovery", 0)])
        self.assertEqual(self.outcome[0][0], "deferred_errors_remaining")
        self.assertEqual(self.outcome[0][2]["partition"], 0)
        work = self.outcome[0][1]
        queue = json.loads((work / "data/electroverse/live_statuses/deferred-failures.json").read_text())
        self.assertEqual(queue["remainingLocations"], 1)
        self.assertEqual(queue["errorCount"], 1)
        self.assertEqual(queue["partitionCount"], 16)
        self.assertEqual(queue["partitionDetails"][0]["errors"][0]["pk"], "A")
        self.assertTrue(pilot.report_matches_partition(validate_partial(work), self.outcome[0][2]))

    def test_429_stops_before_later_partitions_or_recovery(self):
        self.stop_partition = 3
        self.execute()
        self.assertEqual(self.seen, [("sweep", i) for i in range(4)])
        self.assertEqual(self.outcome[0][0], "provider_rate_limited")
        work = self.outcome[0][1]
        queue = json.loads((work / "data/electroverse/live_statuses/deferred-failures.json").read_text())
        self.assertEqual(queue["partitionCount"], 4)
        self.assertGreaterEqual(queue["remainingLocations"], 1)

    def test_report_can_refer_to_recovery_partition_not_the_last_partition(self):
        snapshot = {"fingerprint": self.fingerprint, "verified_locations": 1,
                    "partitions": [
                        part(i, self.fingerprint,
                             {"A": {"EVSE-A": "AVAILABLE"}} if i == 0 else {},
                             expected=1 if i == 0 else 0)
                        for i in range(16)]}
        self.assertTrue(pilot.report_matches_partition(snapshot, {
            "partition": 0, "verifiedLocations": 1}))
        self.assertFalse(pilot.report_matches_partition(snapshot, {
            "partition": 0, "verifiedLocations": 2}))
        self.assertFalse(pilot.report_matches_partition(snapshot, {
            "partition": 16, "verifiedLocations": 0}))


if __name__ == "__main__":
    unittest.main()
