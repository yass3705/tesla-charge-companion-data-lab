"""Offline WAAT/Monta shard execution, merge, checkpoint, and handoff checks."""

import gzip
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.test_v9_waat_inventory import FixtureRunner
from tests.test_v9_waat_monta_public import archived_fixture
from v9_rebuild.electroverse import ROOT
from v9_rebuild.cwd_script import run as inventory_run
from v9_rebuild.orchestrator import read_sources, run_source
from v9_rebuild.waat_monta_sharded import INPUT, OUTPUT, run, validate_output


class FailingShardRunner:
    def __init__(self, fail_index):
        self.fail_index = fail_index
        self.executed = []

    def __call__(self, command, **kwargs):
        index = int(kwargs["env"]["WAAT_SHARD_INDEX"])
        self.executed.append(index)
        if index == self.fail_index:
            return SimpleNamespace(returncode=2)
        return subprocess.run(command, **kwargs)


class WaatMontaMigrationTests(unittest.TestCase):
    def setup_source(self, root):
        inventory_run(root / "inventory", "waat_inventory", runner=FixtureRunner())
        fixture = root / "map.json"
        fixture.write_text(json.dumps({"FRWA2P000001": {"status": 200, "data": {"list": [], "single_list": []}}}))
        return root / "inventory", fixture

    def test_four_shards_include_empty_partitions_without_price_invention(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory, fixture = self.setup_source(root)
            run(root / "monta", inventory, fixture_map=fixture)
            payload = validate_output(root / "monta")
            self.assertEqual(payload["counts"]["inventoryStations"], 1)
            self.assertEqual(payload["counts"]["rankablePhysicalConfigs"], 0)
            self.assertEqual([payload["stations"][0]["stationIdNormalized"]], ["FRWA2P000001"])
            self.assertTrue((root / "monta/data/shards/waat_monta_shard_3.json.gz").is_file())

    def test_monolithic_output_fields_preserved_by_partitioned_collector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory, _ = self.setup_source(root)
            public_fixture = json.loads(archived_fixture(root).read_text())
            raw = public_fixture["map:48.85,2.35"]["data"]
            shard_fixture = root / "shard-map.json"
            shard_fixture.write_text(json.dumps({"FRWA2P000001": {"status": 200, "data": raw}}))
            run(root / "monta", inventory, fixture_map=shard_fixture)
            station = validate_output(root / "monta")["stations"][0]
            with gzip.open(ROOT / "data/national/waat_monta_direct_tariffs_france.json.gz", "rt", encoding="utf-8") as stream:
                legacy = json.load(stream)["stations"][0]
            self.assertTrue(set(legacy).issubset(station))
            self.assertTrue(set(legacy["montaGroups"][0]).issubset(station["montaGroups"][0]))
            self.assertEqual(station["montaGroups"][0]["priceLabel"], public_fixture["map:48.85,2.35"]["data"]["list"][0]["price_label"])

    def test_failed_partition_preserves_finished_shard_and_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory, fixture = self.setup_source(root)
            runner = FailingShardRunner(1)
            with self.assertRaisesRegex(RuntimeError, "shard 1 failed"):
                run(root / "monta", inventory, fixture_map=fixture, runner=runner)
            self.assertEqual(runner.executed, [0, 1])
            self.assertFalse((root / "monta" / OUTPUT).exists())
            resumed = FailingShardRunner(-1)
            run(root / "monta", inventory, fixture_map=fixture, runner=resumed)
            self.assertEqual(resumed.executed, [1, 2, 3])
            self.assertEqual(validate_output(root / "monta")["counts"]["mapErrors"], 0)

    def test_wrong_sha_or_failed_map_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory, fixture = self.setup_source(root)
            run(root / "monta", inventory, fixture_map=fixture)
            (root / "monta" / OUTPUT).write_bytes(b"bad")
            with self.assertRaises((OSError, gzip.BadGzipFile)):
                validate_output(root / "monta")
            bad_map = root / "bad-map.json"
            bad_map.write_text(json.dumps({"FRWA2P000001": {"status": 404, "data": None}}))
            with self.assertRaisesRegex(ValueError, "partial state invalid"):
                run(root / "bad", inventory, fixture_map=bad_map)

    def test_orchestrator_rejects_absent_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = next(row for row in read_sources() if row["id"] == "FR:waat_monta_sharded")
            self.assertEqual(run_source(spec, Path(tmp) / "artifacts")["reason"], "validated_dependency_missing")

    def test_signed_inventory_handoff_and_checkpoint_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, fixture = self.setup_source(root)
            inventory_spec = next(row for row in read_sources() if row["id"] == "FR:waat_inventory")
            def inventory_outer(command, **kwargs):
                inventory_run(Path(command[command.index("--out") + 1]), "waat_inventory", runner=FixtureRunner())
                return SimpleNamespace(returncode=0)
            baseline = root / "baseline"
            inventory_row = run_source(inventory_spec, baseline, runner=inventory_outer)
            self.assertEqual(inventory_row["status"], "ok")
            out_root = root / "artifacts"
            dependency = out_root / "input_dependencies/FR_waat_inventory"
            dependency.mkdir(parents=True)
            shutil.copytree(baseline / "objects", dependency / "objects")
            manifest = {"schema_version": 1, "status": "complete", "sources": [inventory_row]}
            (dependency / "manifest.json").write_text(json.dumps(manifest))
            spec = next(row for row in read_sources() if row["id"] == "FR:waat_monta_sharded")
            def failing_outer(command, **kwargs):
                try:
                    run(Path(command[command.index("--out") + 1]),
                        Path(command[command.index("--inventory") + 1]),
                        fixture_map=fixture, runner=FailingShardRunner(1))
                except RuntimeError:
                    return SimpleNamespace(returncode=2)
                return SimpleNamespace(returncode=0)
            failed = run_source(spec, out_root, attempts=1, runner=failing_outer)
            self.assertEqual(failed["status"], "failed")
            checkpoint = out_root / "checkpoints/FR_waat_monta_sharded"
            self.assertTrue((checkpoint / "data/shards/waat_monta_shard_0.json.gz").is_file())
            def resumed_outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]),
                    Path(command[command.index("--inventory") + 1]), fixture_map=fixture)
                return SimpleNamespace(returncode=0)
            success = run_source(spec, out_root, attempts=1, runner=resumed_outer)
            self.assertEqual(success["status"], "ok")
            self.assertFalse(checkpoint.exists())
            manifest["sources"][0]["sha256"] = "0" * 64
            (dependency / "manifest.json").write_text(json.dumps(manifest))
            rejected = run_source(spec, out_root, attempts=1)
            self.assertEqual(rejected["reason"], "validated_dependency_invalid")


if __name__ == "__main__":
    unittest.main()
