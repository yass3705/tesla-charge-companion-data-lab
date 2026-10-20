"""Offline failure/restart checks for the existing Electroverse scripts."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.electroverse import CACHE, MAPPING, REPORTS, IncompleteCollection, read_json, run, shard_index, validate_state


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def fixture(root: Path, pks: list[str]) -> None:
    save(root / MAPPING, {"mappings": [{"electroverseLocationPk": pk, "irveStationId": f"FR-{pk}"} for pk in pks]})
    metas = []
    for index in range(128):
        name = f"shard-{index:03d}.json"
        path = root / CACHE / name
        save(path, {"version": 1, "shard": index, "shardCount": 128, "stations": {}})
        metas.append({"shard": index, "file": name, "count": 0, "sizeBytes": path.stat().st_size})
    save(root / CACHE / "manifest.json", {"version": 1, "shardCount": 128, "totalStations": 0, "shards": metas})


class SimulatedCollector:
    def __init__(self, fail_once: str | None = None):
        self.fail_once = fail_once
        self.selections = []

    def __call__(self, command, **kwargs):
        name = Path(command[-1]).name
        cwd = Path(kwargs["cwd"])
        if name == "electroverse_force_chunk_selection.mjs":
            return subprocess.run(command, **kwargs)
        if name == "electroverse_daily_delta_selector.mjs":
            pks = [row["electroverseLocationPk"] for row in read_json(cwd / MAPPING)["mappings"]]
            save(cwd / REPORTS / "incremental-selection.json", {"selectedCount": len(pks), "selected": [{"pk": pk} for pk in pks]})
            return SimpleNamespace(returncode=0)
        self.selections.append([str(row["pk"]) for row in read_json(cwd / REPORTS / "incremental-selection.json")["selected"]])
        failed = []
        manifest = read_json(cwd / CACHE / "manifest.json")
        for pk in self.selections[-1]:
            if pk == self.fail_once:
                failed.append({"pk": pk, "error": "fixture_interruption"})
                self.fail_once = None
                continue
            index = shard_index(pk)
            meta = manifest["shards"][index]
            path = cwd / CACHE / meta["file"]
            shard = read_json(path)
            shard["stations"][pk] = {"electroverseLocationPk": pk, "tariffHash": "fixture-sha", "tariff": {"chargingLocationPk": pk}}
            save(path, shard)
            meta["count"] = len(shard["stations"])
            meta["sizeBytes"] = path.stat().st_size
        manifest["totalStations"] = sum(meta["count"] for meta in manifest["shards"])
        save(cwd / CACHE / "manifest.json", manifest)
        save(cwd / REPORTS / "hybrid-refresh-failures.json", {"failures": failed})
        return SimpleNamespace(returncode=2 if failed else 0)


class ElectroverseTests(unittest.TestCase):
    def test_full_chunk_budget_keeps_checkpoint_until_final_chunk(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"ELECTROVERSE_API_KEY": "fixture-only"}):
            source, out = Path(temp) / "source", Path(temp) / "out"
            fixture(source, ["a", "b", "c"])
            collector = SimulatedCollector()
            with self.assertRaises(IncompleteCollection):
                run(out, "full", source=source, runner=collector, chunk_size=2, max_chunks=1)
            self.assertEqual(read_json(out / "v9-electroverse-checkpoint.json")["completed"], [0])
            self.assertEqual(validate_state(out, require_complete=False)["totalStations"], 2)
            run(out, "full", source=source, runner=collector, chunk_size=2, max_chunks=1)
            self.assertEqual(collector.selections, [["a", "b"], ["c"]])
            self.assertEqual(validate_state(out)["totalStations"], 3)
            self.assertFalse((out / "v9-electroverse-checkpoint.json").exists())

    def test_full_failure_keeps_success_and_retries_only_failed_pk(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"ELECTROVERSE_API_KEY": "fixture-only"}):
            source, out = Path(temp) / "source", Path(temp) / "out"
            fixture(source, ["a", "b", "c"])
            collector = SimulatedCollector(fail_once="b")
            with self.assertRaises(IncompleteCollection):
                run(out, "full", source=source, runner=collector, chunk_size=2)
            self.assertEqual(read_json(out / "v9-electroverse-checkpoint.json")["pending"]["pks"], ["b"])
            self.assertEqual(validate_state(out, require_complete=False)["totalStations"], 1)
            with self.assertRaises(IncompleteCollection):
                validate_state(out)
            run(out, "full", source=source, runner=collector, chunk_size=2)
            self.assertEqual(collector.selections, [["a", "b"], ["b"], ["c"]])
            self.assertEqual(validate_state(out)["totalStations"], 3)
            self.assertFalse((out / "v9-electroverse-checkpoint.json").exists())
            self.assertEqual(validate_state(source)["totalStations"], 0)

    def test_daily_resume_from_isolated_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"ELECTROVERSE_API_KEY": "fixture-only"}):
            source, failed, resumed = (Path(temp) / name for name in ("source", "failed", "resumed"))
            fixture(source, ["a", "b"])
            collector = SimulatedCollector(fail_once="b")
            with self.assertRaises(IncompleteCollection):
                run(failed, "daily", source=source, runner=collector)
            run(resumed, "daily", source=source, resume=failed, runner=collector)
            self.assertEqual(collector.selections, [["a", "b"], ["b"]])
            self.assertEqual(validate_state(resumed)["totalStations"], 2)
            self.assertEqual(validate_state(source)["totalStations"], 0)

    def test_manifest_corruption_blocks_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root, [])
            manifest = read_json(root / CACHE / "manifest.json")
            manifest["shards"][0]["count"] = 1
            save(root / CACHE / "manifest.json", manifest)
            with self.assertRaises(ValueError):
                validate_state(root)


if __name__ == "__main__":
    unittest.main()
