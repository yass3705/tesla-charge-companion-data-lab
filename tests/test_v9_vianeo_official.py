"""Offline historical execution for Vianeo's separate direct and roaming rules."""

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
import vianeo_official as historical  # noqa: E402

PAGES = {
    "pricing": "0,54 €/kWh 0,60 €/kWh 10 % sous le tarif public. Tarif fixé par votre fournisseur de carte. Frais à la minute sur certaines stations.",
    "maxSubscription": "Vianeo Max 0,33 €/kWh 9,99 €/mois sans engagement partout en France.",
    "help": "Pré-autorisation de 50 €.",
    "terms": "200 kWh / jour. Points de charge dédiés aux véhicules poids lourds. Prix au kWh et/ou à la durée.",
    "superOffPeak": "Super heures creuses 0,29 €/kWh de 22h à 8h jusqu'au 31/12/2026 uniquement via application.",
    "selection": "Igny Palaiseau Lieusaint Carré Sénart Noisy-le-Grand",
    "inventoryOrg": "ENGIE Vianeo juillet 2026",
}


def runner(command, **kwargs):
    def fetch(url):
        key = next(k for k, value in historical.SOURCES.items() if value == url)
        return 200, PAGES[key]
    with patch.object(historical, "fetch", side_effect=fetch), patch.object(sys, "argv", command[1:]), patch("builtins.print"):
        historical.main()
    return SimpleNamespace(returncode=0)


class VianeoOfficialMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", "vianeo", runner=runner)
            payload = validate_output(root / "source", "vianeo")
            self.assertFalse(payload["roaming"]["operatorDirect"])
            spec = next(row for row in read_sources() if row["id"] == "FR:vianeo_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "vianeo", runner=runner)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)


if __name__ == "__main__":
    unittest.main()
