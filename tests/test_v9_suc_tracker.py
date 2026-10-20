"""Offline SuC Tracker migration with a smaller valid source snapshot."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source
from v9_rebuild.suc_tracker import DATA, run, validate_output


class SuCTrackerMigrationTests(unittest.TestCase):
    def fixture(self, target: Path) -> Path:
        source = json.loads((ROOT / DATA / "europe.json").read_text(encoding="utf-8"))
        countries = {entry["countryCode"] for entry in json.loads((ROOT / "config/countries.json").read_text()).values() if entry.get("enabled")}
        selected = {}
        for station in source["stations"]:
            if station["country"] in countries and station["country"] not in selected:
                selected[station["country"]] = station
        source["stations"] = list(selected.values())
        source["stats"]["stations"] = len(source["stations"])
        source["generatedAt"] = "2026-10-10T00:00:00Z"
        target.write_text(json.dumps(source), encoding="utf-8")
        return target

    def test_reduced_snapshot_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = self.fixture(root / "fixture.json")
            run(root / "source", fixture=fixture)
            meta = validate_output(root / "source")
            self.assertEqual(meta["sourceStationCount"], len(json.loads(fixture.read_text())["stations"]))
            spec = next(row for row in read_sources() if row["id"] == "GL:suc_tracker")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), fixture=fixture)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 3)

    def test_corrupt_fixture_and_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = self.fixture(root / "fixture.json")
            run(root / "last_good", fixture=fixture)
            prior = (root / "last_good" / DATA / "metadata.json").read_bytes()
            fixture.write_text("{}")
            with self.assertRaisesRegex(RuntimeError, "Historical SuC Tracker method failed"):
                run(root / "failure", source=root / "last_good", fixture=fixture)
            self.assertEqual((root / "last_good" / DATA / "metadata.json").read_bytes(), prior)


if __name__ == "__main__":
    unittest.main()
