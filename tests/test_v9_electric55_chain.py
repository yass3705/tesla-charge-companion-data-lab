"""Offline execution of the archived E55C static and exact direct chain."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from electric55_station_base import build
import electric55_station_base as station_base
import electric55_direct_tariffs as direct
from tests.test_electric55_direct_tariffs import tariff_payload
from v9_rebuild.electric55_chain import FINAL, digest, run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source

EVSE = "FR*55C*EFR39000*P7PPFG*1"
ROW = {"nom_station": "Fixture E55C", "adresse_station": "1 rue Test 39000 Lons-le-Saunier",
       "coordonneesXY": "[5.548529,46.674931]", "id_station_itinerance": "FR55CP39000TEST",
       "id_pdc_itinerance": "FR55CEFR39000P7PPFG1", "id_pdc_local": EVSE,
       "nom_operateur": "Electric 55 Charging", "nom_enseigne": "E55C",
       "paiement_acte": "true", "gratuit": "false", "prise_type_2": "true",
       "puissance_nominale": "22.08", "tarification": ""}


class FixtureRunner:
    def __init__(self, fail_stage=None):
        self.fail_stage = fail_stage

    def __call__(self, command, **kwargs):
        script = Path(command[1]).name
        if script == self.fail_stage:
            return SimpleNamespace(returncode=2)
        with patch.object(sys, "argv", command[1:]):
            if script == "electric55_station_base.py":
                station_base.main()
            else:
                links = {EVSE: {"chargingStationId": EVSE, "connectorId": 1,
                                "paymentUrl": "https://ev-qr.com/?t=e55c&b=fixture&c=1"}}
                result = {EVSE: {"ok": True, "payload": tariff_payload(), "url": "https://fixture.invalid"}}
                with patch.object(direct, "load_official_map", return_value=(links, {"paymentLinkCount": 1})), \
                     patch.object(direct, "_fetch_many", return_value=result):
                    direct.main()
        return SimpleNamespace(returncode=0)


class E55CMigrationTests(unittest.TestCase):
    def fixture(self, root):
        csv_path = root / "e55c.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=ROW.keys())
            writer.writeheader()
            writer.writerow(ROW)
        return csv_path

    def test_historical_chain_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = self.fixture(root)
            run(root / "source", input_csv=csv_path, runner=FixtureRunner())
            final = validate_output(root / "source")
            self.assertEqual(final["stats"]["stationCount"], 1)
            self.assertEqual(final["stats"]["chargePointCountWithMachineReadablePricing"], 1)
            self.assertEqual(final["stations"][0]["chargePoints"][0]["localEvseId"], EVSE)
            spec = next(row for row in read_sources() if row["id"] == "FR:electric55_chain")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), input_csv=csv_path, runner=FixtureRunner())
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_failure_preserves_prior_and_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = self.fixture(root)
            with self.assertRaisesRegex(RuntimeError, "direct tariff method failed"):
                run(root / "failed", input_csv=csv_path, runner=FixtureRunner("electric55_direct_tariffs.py"))
            self.assertTrue((root / "failed/input/electric55_last_good.json").is_file())
            self.assertFalse((root / "failed/reports/electric55/v9-chain-provenance.json").exists())
            run(root / "source", input_csv=csv_path, runner=FixtureRunner())
            provenance = root / "source/reports/electric55/v9-chain-provenance.json"
            obj = json.loads(provenance.read_text())
            obj["finalSha256"] = "0" * 64
            provenance.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError, "handoff invalid"):
                validate_output(root / "source")

    def test_empty_operator_scope_no_volume_gate(self):
        payload = build([{**ROW, "nom_operateur": "Other CPO"}], source={"sha256": "fixture"})
        self.assertEqual(payload["stations"], [])

    def test_resume_uses_only_validated_previous_catalogue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = self.fixture(root)
            run(root / "first", input_csv=csv_path, runner=FixtureRunner())
            run(root / "second", source=root / "first", input_csv=csv_path, runner=FixtureRunner())
            provenance = json.loads((root / "second/reports/electric55/v9-chain-provenance.json").read_text())
            self.assertEqual(provenance["previousSha256"], digest(root / "first" / FINAL))
            (root / "first" / FINAL).write_text("{}")
            with self.assertRaisesRegex(ValueError, "catalogue technical contract invalid"):
                run(root / "rejected", source=root / "first", input_csv=csv_path, runner=FixtureRunner())


if __name__ == "__main__":
    unittest.main()
