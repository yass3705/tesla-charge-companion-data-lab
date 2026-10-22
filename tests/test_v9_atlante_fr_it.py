"""Offline execution and interrupted FR/IT resume for the preserved Atlante method."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v9_rebuild import atlante_fr_it
from v9_rebuild.orchestrator import read_sources, run_source


class FixtureRunner:
    def __init__(self):
        self.fail_italy_once = False
        self.calls = []

    def __call__(self, command, **_):
        spec = importlib.util.spec_from_file_location("atlante_fixture", command[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.OFFLINE = False
        module.RESUME = True
        out = Path(command[command.index("--out") + 1])

        def request(path):
            self.calls.append(path)
            if path.startswith("/map-locations?"):
                country = "IT" if "ITATE" in path else "FR"
                return {"locations": [{"id": country + "-station", "countryCode": country,
                                         "partyId": "ATE" if country == "IT" else "ATL"}],
                        "locationSummaries": []}
            country = "IT" if "IT-station" in path else "FR"
            if path.endswith("/tariffs"):
                if country == "IT" and self.fail_italy_once:
                    self.fail_italy_once = False
                    raise OSError("offline simulated tariff page failure")
                return [{"identifiers": {"evseId": country + "*ATL*E1", "connectorId": "1"},
                         "priceComponents": [{"priceDimension": "ENERGY", "currency": "EUR",
                                              "price": {"incl_vat": 0.5}}]}]
            return {"id": country + "-station", "countryCode": country,
                    "partyId": "ATE" if country == "IT" else "ATL", "operatorName": "Atlante",
                    "evses": [{"evseId": country + "*ATL*E1", "connectors": [
                        {"evseConnectorId": "1", "evseCommonConnectorType": "CCS",
                         "evsePowerType": "DC", "max_electric_power": 150}]}]}

        module.request = request
        for country in ("FR", "IT"):
            module.run(country, out, 1)
        return subprocess.CompletedProcess(command, 0)


class AtlanteMigrationTests(unittest.TestCase):
    def test_failure_checkpoint_resume_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            runner = FixtureRunner()
            runner.fail_italy_once = True
            with self.assertRaisesRegex(ValueError, "technical completion"):
                atlante_fr_it.run(base / "failed", checkpoint=base / "checkpoint", runner=runner)
            atlante_fr_it.validate_checkpoint(base / "checkpoint")
            first = len([p for p in runner.calls if p.endswith("FR-station/tariffs")])
            atlante_fr_it.run(base / "success", checkpoint=base / "checkpoint", runner=runner)
            self.assertEqual(first, len([p for p in runner.calls if p.endswith("FR-station/tariffs")]))
            self.assertFalse((base / "checkpoint").exists())
            reports = atlante_fr_it.validate_output(base / "success")
            self.assertEqual({country: report["connectorCount"] for country, report in reports.items()},
                             {"FR": 1, "IT": 1})
            source = next(row for row in read_sources() if row["id"] == "FR:atlante_fr_it")

            def process(command, **_):
                atlante_fr_it.run(Path(command[command.index("--out") + 1]),
                                  checkpoint=Path(command[command.index("--checkpoint") + 1]), runner=FixtureRunner())
                return subprocess.CompletedProcess(command, 0)

            with patch.dict(os.environ, {"ATLANTE_API_SUBSCRIPTION_KEY": "offline-fixture"}):
                result = run_source(source, base / "artifacts", attempts=1, runner=process)
            self.assertEqual(result["status"], "ok", result)
            self.assertTrue(any(str(item).find("atlante_direct_stations_italy_latest.json.gz") >= 0
                                for item in result["files"]))

    def test_checkpoint_sha_and_missing_country_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            runner = FixtureRunner()
            runner.fail_italy_once = True
            with self.assertRaises(ValueError):
                atlante_fr_it.run(base / "failed", checkpoint=base / "checkpoint", runner=runner)
            file = next((base / "checkpoint" / "FR").rglob("*.json"))
            file.write_text(json.dumps({"mutated": True}))
            with self.assertRaisesRegex(ValueError, "SHA"):
                atlante_fr_it.validate_checkpoint(base / "checkpoint")
            with self.assertRaisesRegex(ValueError, "SHA"):
                atlante_fr_it.run(base / "retry", checkpoint=base / "checkpoint", runner=FixtureRunner())
            atlante_fr_it.run(base / "complete", checkpoint=base / "new-checkpoint", runner=FixtureRunner())
            (base / "complete" / atlante_fr_it.OUTPUTS["IT"]).unlink()
            with self.assertRaises(OSError):
                atlante_fr_it.validate_output(base / "complete")


if __name__ == "__main__":
    unittest.main()
