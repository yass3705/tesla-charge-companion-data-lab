"""Offline historical execution for IECharge direct and roaming classification."""

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
import iecharge_official as historical  # noqa: E402

PAGES = {
    "pricing": "0,25 €/kWh jusqu'à 320 kW via l'application et par carte bancaire. Votre fournisseur peut vous facturer un tarif différent. Réservation de 20 €.",
    "faq": "Vous verrez également le prix dans l'application.",
    "stations": "Chaque station propose 4 points de charge.",
    "networkDesign": "Deux de 320 kW et deux de 160 kW.",
    "current2026": "0,25 €/kWh, meilleur tarif actuel.",
}


def runner(command, **kwargs):
    def fetch(url):
        key = next(k for k, value in historical.SOURCES.items() if value == url)
        return 200, PAGES[key]
    with patch.object(historical, "fetch", side_effect=fetch), patch.object(sys, "argv", command[1:]), patch("builtins.print"):
        historical.main()
    return SimpleNamespace(returncode=0)


class IEChargeOfficialMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", "iecharge", runner=runner)
            payload = validate_output(root / "source", "iecharge")
            self.assertFalse(payload["roaming"]["operatorDirect"])
            spec = next(row for row in read_sources() if row["id"] == "FR:iecharge_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "iecharge", runner=runner)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)


if __name__ == "__main__":
    unittest.main()
