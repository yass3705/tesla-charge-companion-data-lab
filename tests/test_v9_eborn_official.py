"""Offline execution of the preserved eborn official rule method."""

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
import eborn_official as historical  # noqa: E402

TARIFFS = "14 49 0,310 0,433 0,573 0,588 0,650 0,05 0,075 0,12 250 jusqu'à 25kW entre 25 et 60kW supérieure à 60kW 30 minutes 8h00 et 20h00 31 mars 2025 15%"
FAQ = "Easy Charge plus de 3 000 points de charge jusqu'à 120 kW carte bancaire QR code 30 minutes 500 Wh 2 minutes 40 € ou 50 € stationnement payant 430 000 points de charge"


def runner(command, **kwargs):
    def fetch(url):
        key = next(k for k, value in historical.SOURCES.items() if value == url)
        return 200, {"tariffs": TARIFFS, "faq": FAQ, "chargeGuide": "Recharge eborn"}[key]
    with patch.object(historical, "fetch_text", side_effect=fetch), patch.object(sys, "argv", command[1:]), patch("builtins.print"):
        historical.main()
    return SimpleNamespace(returncode=0)


class EbornOfficialMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", "eborn", runner=runner)
            payload = validate_output(root / "source", "eborn")
            self.assertEqual(payload["country"], "FR")
            spec = next(row for row in read_sources() if row["id"] == "FR:eborn_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "eborn", runner=runner)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)


if __name__ == "__main__":
    unittest.main()
