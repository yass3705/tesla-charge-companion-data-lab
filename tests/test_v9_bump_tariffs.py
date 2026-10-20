"""Offline execution of the preserved Bump GraphQL and TCC finalizer."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.bump_tariffs import GRAPHQL, TCC, run, validate_output
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
import bump_graphql_national_tariffs as graph  # noqa: E402
import bump_tcc_ready_france as tcc  # noqa: E402


STATION = {"stationKey": "FR*BUP*S1", "idStationItinerance": "FR*BUP*S1",
           "name": "Fixture Bump", "address": "Rue Test", "latitude": 48.0,
           "longitude": 2.0, "points": [{"idPdcItinerance": "FR*BUP*E1", "suffix": "1", "powerKw": "22"}]}


class OfflineRunner:
    def __init__(self, tile_failure=False, second_failure=False, matched=False, tariff_failure=False):
        self.tile_failure = tile_failure
        self.second_failure = second_failure
        self.matched = matched
        self.tariff_failure = tariff_failure
        self.seen = []

    def __call__(self, command, **kwargs):
        name = Path(command[1]).name
        self.seen.append(name)
        if name == "bump_tcc_ready_france.py" and self.second_failure:
            return SimpleNamespace(returncode=2)
        previous = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            if name == "bump_graphql_national_tariffs.py":
                def tile(value):
                    locations = ([{"locationId": "loc-1", "name": "Fixture Bump", "latitude": 48.0,
                                   "longitude": 2.0, "evses": [{"evseId": "evse-1", "identifier": "FR*BUP*E1",
                                   "suffix": "1", "tariffGroupId": "group-1"}]}] if self.matched else [])
                    return {"key": value["key"], "status": 503 if self.tile_failure else 200,
                            "errors": ["fixture failure"] if self.tile_failure else [], "locations": locations}
                def tariff(pair):
                    return pair, {"status": 503 if self.tariff_failure else 200,
                                  "errors": ["fixture failure"] if self.tariff_failure else [], "tariff": {
                        "tariffId": "tariff-1", "name": "Fixture", "currency": "EUR",
                        "energyEurPerKwh": 0.4, "timeEurPerHour": None,
                        "flatFeeEur": None, "minPriceEur": None,
                        "isTariffChangingInTime": False}}
                with patch.object(graph, "official_stations", return_value=([STATION], {"datasetId": "fixture"})), \
                     patch.object(graph, "fetch_tile", side_effect=tile), \
                     patch.object(graph, "fetch_tariff", side_effect=tariff), \
                     patch.object(sys, "argv", [str(graph.__file__)]), patch("builtins.print"):
                    graph.main()
            else:
                with patch("builtins.print"):
                    tcc.main()
        finally:
            os.chdir(previous)
        return SimpleNamespace(returncode=0)


class BumpTariffMigrationTests(unittest.TestCase):
    def test_real_graphql_and_tcc_methods(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = OfflineRunner()
            run(root / "source", runner=runner)
            self.assertEqual(runner.seen, ["bump_graphql_national_tariffs.py", "bump_tcc_ready_france.py"])
            result = validate_output(root / "source")
            self.assertEqual(result["graphql"]["counts"]["officialPoints"], 1)
            self.assertFalse(result["tcc"]["stations"][0]["points"][0]["rankable"])
            spec = next(row for row in read_sources() if row["id"] == "FR:bump_tariffs")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), runner=OfflineRunner())
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 6)

    def test_exact_evse_match_receives_only_its_tariff(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            run(out, runner=OfflineRunner(matched=True))
            result = validate_output(out)
            point = result["tcc"]["stations"][0]["points"][0]
            self.assertEqual(point["idPdcItinerance"], "FR*BUP*E1")
            self.assertTrue(point["rankable"])
            self.assertEqual(point["components"]["energyEurPerKwh"], 0.4)

    def test_failed_tile_is_not_publishable(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "requests or report incomplete"):
                run(Path(temp), runner=OfflineRunner(tile_failure=True))

    def test_second_script_failure_keeps_graphql_only(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            with self.assertRaisesRegex(RuntimeError, "bump_tcc_ready_france"):
                run(out, runner=OfflineRunner(second_failure=True))
            self.assertTrue((out / GRAPHQL).is_file())
            self.assertFalse((out / TCC).exists())

    def test_failed_tariff_request_is_not_publishable(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "requests or report incomplete"):
                run(Path(temp), runner=OfflineRunner(matched=True, tariff_failure=True))


if __name__ == "__main__":
    unittest.main()
