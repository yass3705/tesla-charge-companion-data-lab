"""Offline execution of relative-output historical CPO methods."""

from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.cwd_script import run, validate_output
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
import etotem_direct_station_inventory as historical  # noqa: E402

CSV = ("id_station_itinerance,id_pdc_itinerance,nom_operateur,nom_station,puissance_nominale,prise_type_combo_ccs,coordonneesXY\n"
       "FR*ETO*ST01,FR*ETO*E01,e-Totem,Fixture,50,true,2.35;48.85\n")


class OfflineRunner:
    def __init__(self, fail=False):
        self.fail = fail

    def __call__(self, command, **kwargs):
        old = Path.cwd()
        dataset = {"id": "fixture-dataset", "title": "recharge IRVE", "resources": [{"id": "fixture-resource", "url": "https://fixture.invalid/current.csv", "format": "csv", "type": "main"}]}
        try:
            os.chdir(kwargs["cwd"])
            with patch.object(historical, "find_etotem_organization", return_value={"id": "fixture-org", "name": "e-Totem", "slug": "e-totem"}), \
                 patch.object(historical, "list_etotem_irve_datasets", return_value=[] if self.fail else [dataset]), \
                 patch.object(historical, "_get_bytes", return_value=CSV.encode()), patch("builtins.print"):
                historical.main()
        except RuntimeError:
            return SimpleNamespace(returncode=2)
        finally:
            os.chdir(old)
        return SimpleNamespace(returncode=0)


class RelativeOutputMigrationTests(unittest.TestCase):
    def test_etotem_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", "etotem_inventory", runner=OfflineRunner())
            payload = validate_output(root / "source", "etotem_inventory")
            self.assertEqual(payload["counts"]["pdcCount"], 1)
            self.assertEqual(payload["stations"][0]["pdcs"][0]["id"], "FR*ETO*E01")
            spec = next(row for row in read_sources() if row["id"] == "FR:etotem_inventory")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "etotem_inventory", runner=OfflineRunner())
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")

    def test_missing_dataset_and_corrupt_gzip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, "Historical etotem_inventory method failed"):
                run(root / "failed", "etotem_inventory", runner=OfflineRunner(fail=True))
            run(root / "source", "etotem_inventory", runner=OfflineRunner())
            path = root / "source/data/national/etotem_direct_stations_france.json.gz"
            path.write_bytes(b"broken")
            with self.assertRaises((OSError, gzip.BadGzipFile)):
                validate_output(root / "source", "etotem_inventory")


if __name__ == "__main__":
    unittest.main()
