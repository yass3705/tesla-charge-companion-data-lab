"""WAAT/Monta public evidence method, signed inventory, and failure gates."""

import gzip
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.test_v9_waat_inventory import FixtureRunner
from v9_rebuild.cwd_script import run as inventory_run
from v9_rebuild.orchestrator import read_sources, run_source
from v9_rebuild.waat_monta_public import OUTPUT, PROVENANCE, run, validate_output
from v9_rebuild.electroverse import ROOT


def archived_fixture(root: Path) -> Path:
    with gzip.open(ROOT / "data/national/waat_monta_public_tariffs_france.json.gz", "rt", encoding="utf-8") as stream:
        source = json.load(stream)
    record = source["directGroups"][0]
    group = dict(record["group"])
    group["location"] = "48.85,2.35"
    group_id = group["id"]
    fixture = {
        "map:48.85,2.35": {"status": 200, "data": {"list": [group], "single_list": []}},
        f"/api/v1/charge_point_groups/{group_id}": {"status": 200, "data": record["detail"]},
        f"/api/v1/charge_points?charge_point_group_id={group_id}&size=200": {"status": 200, "data": record["children"]},
    }
    path = root / "fixture.json"
    path.write_text(json.dumps(fixture))
    return path


class WaatMontaPublicTests(unittest.TestCase):
    def setup_input(self, root):
        inventory_run(root / "inventory", "waat_inventory", runner=FixtureRunner())
        return root / "inventory", archived_fixture(root)

    def test_preserved_script_and_fail_closed_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory, fixture = self.setup_input(root)
            run(root / "public", inventory, fixture_map=fixture)
            payload = validate_output(root / "public")
            self.assertEqual(payload["counts"]["irveStationCount"], 1)
            self.assertEqual(payload["counts"]["directWaatGroupCount"], 1)
            self.assertFalse(payload["stations"][0]["rankableDirect"])
            self.assertEqual(payload["directGroups"][0]["detailStatus"], 200)
            (root / "public" / PROVENANCE).write_text("{}")
            with self.assertRaisesRegex(ValueError, "technical contract"):
                validate_output(root / "public")

    def test_incomplete_map_or_detail_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory, fixture = self.setup_input(root)
            data = json.loads(fixture.read_text())
            data["map:48.85,2.35"] = {"status": 404, "data": None}
            fixture.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "technical contract"):
                run(root / "map-failed", inventory, fixture_map=fixture)
            fixture = archived_fixture(root)
            data = json.loads(fixture.read_text())
            key = next(key for key in data if key.startswith("/api/v1/charge_point_groups/"))
            data[key] = {"status": 500, "data": None}
            fixture.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "technical contract"):
                run(root / "detail-failed", inventory, fixture_map=fixture)

    def test_signed_inventory_dependency_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, fixture = self.setup_input(root)
            spec = next(row for row in read_sources() if row["id"] == "FR:waat_monta_public")
            self.assertEqual(run_source(spec, root / "missing")["reason"], "validated_dependency_missing")
            inventory_spec = next(row for row in read_sources() if row["id"] == "FR:waat_inventory")
            def inventory_outer(command, **kwargs):
                inventory_run(Path(command[command.index("--out") + 1]), "waat_inventory", runner=FixtureRunner())
                return SimpleNamespace(returncode=0)
            baseline = root / "baseline"
            inventory_row = run_source(inventory_spec, baseline, runner=inventory_outer)
            out_root = root / "artifacts"
            dependency = out_root / "input_dependencies/FR_waat_inventory"
            dependency.mkdir(parents=True)
            shutil.copytree(baseline / "objects", dependency / "objects")
            manifest = {"schema_version": 1, "status": "complete", "sources": [inventory_row]}
            (dependency / "manifest.json").write_text(json.dumps(manifest))
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), Path(command[command.index("--inventory") + 1]), fixture_map=fixture)
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, out_root, runner=outer)["status"], "ok")
            manifest["sources"][0]["sha256"] = "0" * 64
            (dependency / "manifest.json").write_text(json.dumps(manifest))
            self.assertEqual(run_source(spec, out_root, runner=outer)["reason"], "validated_dependency_invalid")


if __name__ == "__main__":
    unittest.main()
