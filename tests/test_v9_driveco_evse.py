"""DRIVECO exact EVSE CSV parser on frozen archived tariff values."""

import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.driveco_evse import OUTPUT, run, validate_output
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
import driveco_evse_tariffs as historical  # noqa: E402


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class FixtureRunner:
    def __init__(self, fail=False):
        self.fail = fail

    def __call__(self, command, **kwargs):
        if self.fail:
            return SimpleNamespace(returncode=2)
        archived = json.loads((ROOT / "data/operator_direct/driveco_evse_tariffs.json").read_text())
        known = archived["resolved"][0]
        tariff = known["tariff"]
        exact = {"energyPrice": tariff["energyPriceEurPerKwh"], "fixedPrice": tariff["fixedPriceEur"],
                 "minimumBilling": tariff["minimumBillingEur"], "matrix": tariff["matrix"],
                 "matrixOSF": tariff["matrixOSF"], "hasDynamicTarif": tariff["hasDynamicTarif"],
                 "ecoHour": tariff["ecoHour"]}
        fields = ["id_pdc_itinerance", "id_station_itinerance", "nom_operateur", "nom_station", "adresse_station", "puissance_nominale", "tarification"]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"id_pdc_itinerance": known["evseId"], "id_station_itinerance": known["stationId"],
                         "nom_operateur": known["operator"], "nom_station": known["stationName"],
                         "adresse_station": known["address"], "puissance_nominale": known["powerKw"],
                         "tarification": json.dumps(exact)})
        writer.writerow({"id_pdc_itinerance": "FRDRVEFIXTUREUNPRICED", "id_station_itinerance": "FRDRVSFIXTURE",
                         "nom_operateur": "DRIVECO", "nom_station": "Fixture without price", "puissance_nominale": 22,
                         "tarification": ""})
        argv = [str(ROOT / "scripts/driveco_evse_tariffs.py"), "--out", command[command.index("--out") + 1]]
        with patch.object(sys, "argv", argv), patch("urllib.request.urlopen", return_value=Response(buffer.getvalue().encode())), patch("builtins.print"):
            historical.main()
        return SimpleNamespace(returncode=0)


class DrivecoEvseMigrationTests(unittest.TestCase):
    def test_preserved_parser_and_unknown_full_session_fee(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root / "source", runner=FixtureRunner())
            payload = validate_output(root / "source")
            archived = json.loads((ROOT / "data/operator_direct/driveco_evse_tariffs.json").read_text())
            self.assertEqual(payload["summary"]["rowCount"], 2)
            self.assertEqual(payload["resolved"][0]["tariff"]["energyPriceEurPerKwh"], archived["resolved"][0]["tariff"]["energyPriceEurPerKwh"])
            self.assertFalse(payload["resolved"][0]["feeSemantics"]["safeForFullSessionCost"])
            self.assertEqual(payload["unresolved"][0]["unresolvedReason"], "official_driveco_irve_row_has_no_machine_readable_tarification")
            spec = next(row for row in read_sources() if row["id"] == "FR:driveco_evse")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), runner=FixtureRunner())
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_failed_collector_and_corrupt_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "Historical DRIVECO"):
                run(root / "failed", runner=FixtureRunner(fail=True))
            run(root / "source", runner=FixtureRunner())
            (root / "source" / OUTPUT).write_text("{}")
            with self.assertRaises(ValueError):
                validate_output(root / "source")


if __name__ == "__main__":
    unittest.main()
