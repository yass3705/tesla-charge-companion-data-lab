"""Offline execution of both preserved Bump inventory scripts."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.bump_inventory import run, validate_output
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
import bump_direct_inventory as inventory  # noqa: E402
import bump_direct_station_tariffs as stations  # noqa: E402


ROW = {"nom_operateur": "Bump", "id_station_itinerance": "FR*BUP*S1",
       "id_pdc_itinerance": "FR*BUP*E1", "nom_station": "Fixture Bump",
       "adresse_station": "Rue Test", "puissance_nominale": "22", "tarification": ""}
CSV = (",".join(ROW) + "\n" + ",".join(ROW.values()) + "\n").encode()


class OfflineRunner:
    def __init__(self, fail_second=False):
        self.fail_second = fail_second
        self.seen = []

    def __call__(self, command, **kwargs):
        name = Path(command[1]).name
        self.seen.append(name)
        if self.fail_second and name == "bump_direct_station_tariffs.py":
            return SimpleNamespace(returncode=2)
        previous = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            if name == "bump_direct_inventory.py":
                dataset = {"id": "fixture", "title": "Bump", "resources": [{"format": "csv", "url": "fixture://csv", "id": "fixture-csv"}]}
                with patch.object(inventory, "get_json", return_value=dataset), \
                     patch.object(inventory, "get_bytes", return_value=CSV), patch("builtins.print"):
                    inventory.main()
            else:
                with patch.object(stations, "fetch_json", return_value={"data": [ROW], "meta": {"total": 1}}), \
                     patch("builtins.print"):
                    stations.main()
        finally:
            os.chdir(previous)
        return SimpleNamespace(returncode=0)


class BumpInventoryMigrationTests(unittest.TestCase):
    def test_real_scripts_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = OfflineRunner()
            run(root / "source", runner=runner)
            self.assertEqual(runner.seen, ["bump_direct_inventory.py", "bump_direct_station_tariffs.py"])
            data = validate_output(root / "source")
            self.assertEqual(data["inventory"]["stations"][0]["stationKey"], "FR*BUP*S1")
            self.assertEqual(data["stations"]["stations"][0]["evses"][0]["pdcId"], "FR*BUP*E1")
            spec = next(row for row in read_sources() if row["id"] == "FR:bump_inventory_family")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), runner=OfflineRunner())
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 4)

    def test_second_failure_does_not_finalize(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "partial"
            with self.assertRaisesRegex(RuntimeError, "bump_direct_station_tariffs"):
                run(out, runner=OfflineRunner(fail_second=True))
            self.assertTrue((out / "data/national/bump_direct_inventory_france.json.gz").is_file())
            self.assertFalse((out / "data/national/bump_direct_stations_france.json.gz").exists())

    def test_truncated_pagination_fails(self):
        with patch.object(stations, "fetch_json", return_value={"data": [], "meta": {"total": 1}}), patch("builtins.print"):
            with self.assertRaisesRegex(RuntimeError, "pagination ended"):
                stations.main()

    def test_corrupt_inventory_cannot_validate(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            run(out, runner=OfflineRunner())
            (out / "data/national/bump_direct_inventory_france.json.gz").write_bytes(b"corrupt")
            with self.assertRaises(OSError):
                validate_output(out)


if __name__ == "__main__":
    unittest.main()
