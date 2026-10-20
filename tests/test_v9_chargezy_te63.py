"""Offline TE63 historical PAN join and publication checks."""

import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.chargezy_te63 import OUTPUT, REPORT, RUNTIME, run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source

CSV = ("nom_operateur,nom_enseigne,id_pdc_itinerance,id_station_itinerance,nom_station,adresse_station,puissance_nominale,prise_type_combo_ccs,prise_type_chademo,prise_type_2,prise_type_ef\n"
       "SPIE CityNetworks,CHARGEZY - TE63,FR*CZY*E1,FR*CZY*S1,Public,Street,22,false,false,true,false\n"
       "SPIE CityNetworks,CHARGEZY - TE63,FR*CZY*E2,FR*CZY*S2,Coustilles Saint-Germain,Street,50,true,false,false,false\n"
       "SPIE CityNetworks,CHARGEZY - TE63,FR*CZY*E3,FR*CZY*S3,Unknown,Street,75,true,false,false,false\n")


class FakeResponse:
    def __init__(self, value):
        self.value = value
        self.content = value.encode() if isinstance(value, str) else b""

    def json(self):
        return self.value

    def raise_for_status(self):
        return None


class OfflineRunner:
    def __init__(self, fail=False):
        self.fail = fail

    def __call__(self, command, **kwargs):
        if self.fail:
            return SimpleNamespace(returncode=2)
        metadata = {"resources": [{"format": "csv", "title": "Consolidation dernière version",
                                   "url": "https://fixture.invalid/pan.csv", "last_modified": "2026-10-10"}]}

        class Session:
            headers = {}

            def get(self, url, **_):
                return FakeResponse(metadata if url != "https://fixture.invalid/pan.csv" else CSV)

        with patch.dict(sys.modules, {"requests": SimpleNamespace(Session=Session)}), patch("builtins.print"):
            runpy.run_path(command[1], run_name="__main__")
        return SimpleNamespace(returncode=0)


class ChargezyMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "historical", runner=OfflineRunner())
            payload = validate_output(root / "historical")
            self.assertEqual(payload["coverage"], {"panRows": 3, "exactRows": 1,
                            "specialPaymentModeRows": 1, "gaps": 1, "coveragePct": 33.333})
            spec = next(row for row in read_sources() if row["id"] == "FR:chargezy_te63")

            def simulated_process(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), runner=OfflineRunner())
                return SimpleNamespace(returncode=0)

            result = run_source(spec, root / "artifacts", runner=simulated_process)
            self.assertEqual(result["status"], "ok")

    def test_failed_script_and_corrupt_exact_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, "Historical TE63"):
                run(root / "failed", runner=OfflineRunner(fail=True))
            run(root / "corrupt", runner=OfflineRunner())
            path = root / "corrupt" / RUNTIME
            runtime = json.loads(path.read_text())
            runtime["directOffers"][0]["evseIds"] = ["FR*CZY*E2"]
            path.write_text(json.dumps(runtime))
            with self.assertRaisesRegex(ValueError, "contract"):
                validate_output(root / "corrupt")
            (root / "corrupt" / OUTPUT).write_text("broken")
            with self.assertRaises(json.JSONDecodeError):
                validate_output(root / "corrupt")


if __name__ == "__main__":
    unittest.main()
