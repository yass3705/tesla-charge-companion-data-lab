"""Offline partition, merge, freshness and national finalization checks."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_v9_electroverse import fixture as cache_fixture, save
from v9_rebuild.electroverse_status import (
    FINAL_REPORT, PARTITION_COUNT, PARTS, STATUS, STATUS_REPORT, IncompleteStatus,
    cache_fingerprint, choose_partition, merge_partitions, part_path, run,
    validate_complete, validate_partial,
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fixture(root: Path, pks: list[str]) -> None:
    cache_fixture(root, pks)
    path = root / "data/electroverse/tariff_cache/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["generatedAt"] = now()
    save(path, manifest)


def part(index: int, fingerprint: str, entries: dict | None = None, *, started: str | None = None,
         errors: dict | None = None, expected: int | None = None) -> dict:
    entries = entries or {}
    return {"schemaVersion": 1, "partition": index, "partitionCount": PARTITION_COUNT,
            "sourceFingerprint": fingerprint, "sourceCacheDate": now(),
            "startedAt": started or now(), "updatedAt": now(),
            "expectedLocations": len(entries) if expected is None else expected,
            "entries": entries, "errors": errors or {}}


class FixtureRunner:
    def __init__(self, fail_once: bool = False):
        self.fail_once = fail_once
        self.seen = []

    def __call__(self, command, **kwargs):
        if Path(command[1]).name != "electroverse_status_incremental.mjs" or command[2] != "collect":
            return subprocess.run(command, **kwargs)
        root = Path(kwargs["cwd"])
        index = int(command[3])
        self.seen.append(index)
        fingerprint = cache_fingerprint(root)
        prior_path = part_path(root, index)
        prior = json.loads(prior_path.read_text()) if prior_path.is_file() else None
        entries = dict((prior or {}).get("entries") or {})
        if self.fail_once:
            self.fail_once = False
            entries["A"] = {"EVSE-A": "AVAILABLE"}
            save(prior_path, part(index, fingerprint, entries, expected=2))
            save(root / STATUS_REPORT, {"partition": index, "sourceFingerprint": fingerprint,
                                        "remaining": 1, "complete": False})
            return SimpleNamespace(returncode=2)
        if prior and prior.get("expectedLocations") == 2:
            entries["B"] = {"EVSE-B": "CHARGING"}
            expected = 2
        else:
            expected = 0
        save(prior_path, part(index, fingerprint, entries, started=(prior or {}).get("startedAt"), expected=expected))
        save(root / STATUS_REPORT, {"partition": index, "sourceFingerprint": fingerprint,
                                    "remaining": 0, "complete": True})
        return SimpleNamespace(returncode=0)


class ElectroverseStatusTests(unittest.TestCase):
    def test_incomplete_partition_retains_entries_and_resumes(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"ELECTROVERSE_API_KEY": "fixture-only"}):
            source, out = Path(temp) / "source", Path(temp) / "out"
            fixture(source, [])
            runner = FixtureRunner(fail_once=True)
            with self.assertRaises(IncompleteStatus):
                run(out, source=source, partition=0, runner=runner)
            self.assertEqual(validate_partial(out)["verified_locations"], 1)
            with self.assertRaises(IncompleteStatus):
                run(out, source=source, partition=0, runner=runner)
            self.assertEqual(validate_partial(out)["verified_locations"], 2)
            self.assertEqual(runner.seen, [0, 0])
            self.assertFalse((out / STATUS / "manifest.json").exists())
            self.assertFalse((source / PARTS).exists())

    def test_all_partitions_finalize_with_existing_script_and_no_api(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"ELECTROVERSE_API_KEY": "fixture-only"}):
            source, out = Path(temp) / "source", Path(temp) / "out"
            fixture(source, [])
            runner = FixtureRunner()
            for index in range(PARTITION_COUNT - 1):
                with self.assertRaises(IncompleteStatus):
                    run(out, source=source, runner=runner)
            run(out, source=source, runner=runner)
            self.assertEqual(runner.seen, list(range(PARTITION_COUNT)))
            self.assertEqual(validate_complete(out)["completedLocations"], 0)
            self.assertTrue((out / FINAL_REPORT).is_file())

    def test_duplicate_location_and_stale_partition_are_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root, [])
            fingerprint = cache_fingerprint(root)
            save(part_path(root, 0), part(0, fingerprint, {"A": {"EVSE-A": "AVAILABLE"}}))
            save(part_path(root, 1), part(1, fingerprint, {"A": {"EVSE-A": "CHARGING"}}))
            with self.assertRaisesRegex(ValueError, "duplicated"):
                validate_partial(root)
            part_path(root, 1).unlink()
            old = (datetime.now(timezone.utc) - timedelta(hours=17)).isoformat()
            save(part_path(root, 0), part(0, fingerprint, {"A": {"EVSE-A": "AVAILABLE"}}, started=old))
            self.assertEqual(choose_partition(root), 0)

    def test_historical_merge_preserves_good_rows_and_rejects_wrong_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root, [])
            fingerprint = cache_fingerprint(root)
            incoming = root / "incoming"
            save(part_path(root, 0), part(0, fingerprint, {"A": {"EVSE-A": "AVAILABLE"}},
                                          errors={"B": {"error": "old"}}, expected=2))
            save(part_path(incoming, 0), part(0, fingerprint, {"B": {"EVSE-B": "CHARGING"}}, expected=2))
            merge_partitions(root, incoming, os.environ.copy())
            merged = json.loads(part_path(root, 0).read_text())
            self.assertEqual(set(merged["entries"]), {"A", "B"})
            self.assertFalse(merged["errors"])
            save(part_path(incoming, 0), part(0, "wrong-fingerprint", {"C": {}}, expected=1))
            with self.assertRaises(ValueError):
                merge_partitions(root, incoming, os.environ.copy())


if __name__ == "__main__":
    unittest.main()
