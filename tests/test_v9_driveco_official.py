"""Run the preserved DRIVECO official method against a reduced offline source fixture."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.electroverse import ROOT
from v9_rebuild.official_rules import run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
import driveco_official as historical  # noqa: E402


PAGES = {
    "pricing": "Tarifs 0,39 €/kWh 0,51 €/kWh 0,55 à 0,59 €/kWh",
    "drivers": "Chaque borne possède sa propre grille tarifaire. Les prix sont affichés avant le démarrage de la recharge. Le prix par opérateur de mobilité diffère.",
    "howTo": "Paiement via l'application, via le QR code, par carte bancaire, avec badge d'interopérabilité.",
    "terms": "Tarification applicable. Demande de pré-autorisation. Le montant de la demande de pré-autorisation figure sur l'application DRIVECO ou sur le portail web. Indemnité forfaitaire de stationnement prolongée. Pénalités de stationnement. Opérateur de mobilité. Durée inférieure à deux minutes, moins de 500 Wh.",
    "inventoryDataset": "Inventaire officiel",
}
CSV = b"id_pdc_itinerance;id_station_itinerance;adresse_station;code_postal;puissance_nominale\nFR*DCO*E1;FR*DCO*S1;Adresse;78000;22\n"


def runner(command, **kwargs):
    def fetch(url):
        key = next(k for k, value in historical.SOURCES.items() if value == url)
        return 200, CSV if key == "inventoryCsv" else PAGES[key].encode(), "utf-8"
    with patch.object(historical, "fetch", side_effect=fetch), patch.object(sys, "argv", command[1:]), patch("builtins.print"):
        historical.main()
    return SimpleNamespace(returncode=0)


class DrivecoOfficialMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", "driveco", runner=runner)
            payload = validate_output(root / "source", "driveco")
            self.assertEqual(payload["inventory"]["rowCount"], 1)
            spec = next(row for row in read_sources() if row["id"] == "FR:driveco_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "driveco", runner=runner)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)

    def test_corrupt_inventory_schema(self):
        with self.assertRaisesRegex(RuntimeError, "no usable station or EVSE identifier"):
            historical.parse_inventory(b"other;columns\nvalue;value\n")


if __name__ == "__main__":
    unittest.main()
