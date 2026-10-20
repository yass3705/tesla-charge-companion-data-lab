"""Offline execution of the preserved Plug Inn Fast Charge rule method."""

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
import pluginn_fastcharge_official as historical  # noqa: E402

PAGES = {
    "fastCharge": "Via carte bancaire 0,59 €/kWh. Charge Pass Basic 0,46 €/kWh. Charge Pass Intense 0,39 €/kWh. Jusqu'à 320 kW, ouvert 24/7 à tous les véhicules électriques. Stationnement 0,30 €/min au-delà d'1 heure.",
    "chargePass": "Formule Basic gratuit. Intense 5,99 €/mois sans engagement.",
    "rename": "Mobilize Fast Charge devient Plug Inn Fast Charge en avril.",
}


def runner(command, **kwargs):
    def fetch(url):
        key = next(k for k, value in historical.SOURCES.items() if value == url)
        return 200, PAGES[key]
    with patch.object(historical, "fetch", side_effect=fetch), patch.object(sys, "argv", command[1:]), patch("builtins.print"):
        historical.main()
    return SimpleNamespace(returncode=0)


class PlugInnOfficialMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", "pluginn_fastcharge", runner=runner)
            payload = validate_output(root / "source", "pluginn_fastcharge")
            self.assertTrue(payload["fees"]["overstayOrParkingDuration"]["doNotModelAsChargeEndedOnly"])
            spec = next(row for row in read_sources() if row["id"] == "FR:pluginn_fastcharge_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "pluginn_fastcharge", runner=runner)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)


if __name__ == "__main__":
    unittest.main()
