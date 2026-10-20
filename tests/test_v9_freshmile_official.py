"""Offline execution of the preserved Freshmile CPO/eMSP rule method."""

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
import freshmile_official as historical  # noqa: E402

PAGES = {
    "help": "Services entièrement gratuits, sans abonnement ni frais mensuels. Les tarifs varient sur chaque réseau de bornes. Le stationnement peut être payant. Carte des bornes en temps réel et les tarifs en application. Empreinte bancaire.",
    "pass": "Pass Freshmile 4,99 € sans abonnement, 750 000 points de recharge.",
    "passOverview": "Empreinte bancaire de 50 €.",
    "empTerms": "Freshmile agit en qualité d'opérateur de mobilité électrique. Bornes de recharge tierces. Utilisateur tiers. Tarif fixé par ce dernier et affiché sur l'application et le site internet.",
    "cpoTerms": "Le client professionnel propose à Freshmile les tarifs de recharge.",
    "mapArticle": "Carte des bornes, puissance et connecteurs.",
    "shop": "Connect and Go Moselle Metz 3.00 € / mois",
}


def runner(command, **kwargs):
    def fetch(url):
        key = next(k for k, value in historical.SOURCES.items() if value == url)
        return 200, PAGES[key]
    with patch.object(historical, "fetch", side_effect=fetch), patch.object(sys, "argv", command[1:]), patch("builtins.print"):
        historical.main()
    return SimpleNamespace(returncode=0)


class FreshmileOfficialMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", "freshmile", runner=runner)
            payload = validate_output(root / "source", "freshmile")
            self.assertTrue(payload["classification"]["freshmileActsAsCpoAndEmsp"])
            spec = next(row for row in read_sources() if row["id"] == "FR:freshmile_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "freshmile", runner=runner)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)


if __name__ == "__main__":
    unittest.main()
