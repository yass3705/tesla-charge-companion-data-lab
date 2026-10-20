"""Offline execution of the preserved Métropolis tariff and post-charge rules."""

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
import metropolis_official as historical  # noqa: E402

HOME = ("0,44 0,53 0,63 3,7 22 180 0,10 0,20. Tarification post charge après 10min sans charge. "
        "Neuilly-sur-Seine journée de 8h à 20h, la nuit de 20h à 8h. "
        "Bornes 22 kW situées sur les stations ultra-rapides Express.")
FAQ = ("0,53 € TTC / kWh (au lieu de 0,63 €). 10 € par an. 9,90 € par mois. "
       "2 heures de post charge offertes par mois. 2 € par nuit de post charge entre 20h et 8h hors station Express. "
       "Pré-autorisation bancaire de 49€. Apple Pay, Google Pay, QR code. "
       "Badge abonné Métropolis Recharge ou d'autres opérateurs. L'opérateur a la liberté d'appliquer des frais. "
       "Le badge Métropolis ne permet pas la recharge hors réseau.")


def runner(command, **kwargs):
    def fetch(url):
        key = next(k for k, value in historical.SOURCES.items() if value == url)
        return 200, {"home": HOME, "faq": FAQ}[key]
    with patch.object(historical, "fetch_text", side_effect=fetch), patch.object(sys, "argv", command[1:]), patch("builtins.print"):
        historical.main()
    return SimpleNamespace(returncode=0)


class MetropolisOfficialMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", "metropolis", runner=runner)
            payload = validate_output(root / "source", "metropolis")
            self.assertEqual(payload["fees"]["postCharge"]["graceMinutes"], 10)
            spec = next(row for row in read_sources() if row["id"] == "FR:metropolis_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "metropolis", runner=runner)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)


if __name__ == "__main__":
    unittest.main()
