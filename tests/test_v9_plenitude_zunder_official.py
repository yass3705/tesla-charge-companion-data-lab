"""Offline historical execution for Plenitude and Zunder official rule methods."""

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
import plenitude_official as plenitude  # noqa: E402
import zunder_official as zunder  # noqa: E402

PLENITUDE = {
    "pricing": "Pay Per Use charging cost in France quick fast ultra fast 0,45 0,55. 60 minutes free parking. 0.12 0.20 0.30 between 23:00 and 07:00. Other operators may be different in app.",
    "network": "Plenitude charging points and other operators via interoperability, 600.000 points.",
    "travelPromo": "Historical promotion",
    "bilateral": "Bilateral agreement pricing scheme for mobility service providers in France, VAT excluded.",
}
ZUNDER = {
    "drivers": ("Troyes Charmes. Le prix exact de chaque point s'affiche toujours dans l'app. 0,99 €/session. "
                "Prix fixé par l'opérateur du point. " + " ".join(f"{v:.3f} €/kWh" for v in (0.42, 0.59, 0.33, 0.578, 0.595, 0.44, 0.40, 0.564, 0.32, 0.57))),
    "subscriptions": "0,51 €/kWh 0,39 €/kWh 1,99 €/mois 11,99 €/mois 1% 3% 5% sans engagement",
    "leasingSocial": "Leasing social",
    "leasingTerms": "0,39 €/kWh 0,45 €/kWh jusqu'au 31 décembre 2026",
    "payment": "Le montant que vous indiquez est prépayé.",
    "activation": "TPE, pass RFID, Plug & Charge",
    "dynamic": "Troyes 0,49 €/kWh entre 8h et 18h et 0,40 €/kWh entre 18h et 8h",
}


def runner(source):
    module, pages = (plenitude, PLENITUDE) if source == "plenitude" else (zunder, ZUNDER)
    def execute(command, **kwargs):
        def fetch(url):
            key = next(k for k, value in module.SOURCES.items() if value == url)
            return 200, pages[key]
        with patch.object(module, "fetch", side_effect=fetch), patch.object(sys, "argv", command[1:]), patch("builtins.print"):
            module.main()
        return SimpleNamespace(returncode=0)
    return execute


class PlenitudeZunderOfficialMigrationTests(unittest.TestCase):
    def test_historical_methods_and_orchestrator(self):
        for source in ("plenitude", "zunder"):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                run(root / "source", source, runner=runner(source))
                payload = validate_output(root / "source", source)
                self.assertEqual(payload["country"], "FR")
                spec = next(row for row in read_sources() if row["id"] == f"FR:{source}_official")
                def outer(command, **kwargs):
                    run(Path(command[command.index("--out") + 1]), source, runner=runner(source))
                    return SimpleNamespace(returncode=0)
                artifact = run_source(spec, root / "artifacts", runner=outer)
                self.assertEqual(artifact["status"], "ok")
                self.assertEqual(len(artifact["files"]), 2)


if __name__ == "__main__":
    unittest.main()
