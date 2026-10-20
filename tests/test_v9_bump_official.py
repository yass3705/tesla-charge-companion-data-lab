"""Offline execution of the preserved Bump official rule method."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.bump_official import run, validate_output
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
import bump_official as official  # noqa: E402


PAGES = {
    "pricing": "bornes operees par bump bornes partenaires tarifs application tarifs sont definis par le gestionnaire du site prix sont definis par l'operateur du reseau partenaire duree de recharge temps pendant lequel le vehicule reste branche",
    "minimumTariff": "tarif minimum 0,50 stationnement duree n'est pas remboursable",
    "usage": "22 kw 150 kw carte bancaire badge rfid",
    "sessionTroubleshooting": "pre-autorisation 15 45",
    "dataGouvDataset": "bornes de recharge publiques operees par bump mise a jour chaque jour",
}


class OfflineRunner:
    def __init__(self, missing_marker=False):
        self.missing_marker = missing_marker

    def __call__(self, command, **kwargs):
        url_to_key = {url: key for key, url in official.SOURCES.items()}
        def fetch(url):
            key = url_to_key[url]
            return 200, "" if self.missing_marker and key == "pricing" else PAGES[key]
        try:
            with patch.object(official, "fetch", side_effect=fetch), \
                 patch.object(sys, "argv", command[1:]), patch("builtins.print"):
                official.main()
        except RuntimeError:
            return SimpleNamespace(returncode=2)
        return SimpleNamespace(returncode=0)


class BumpOfficialMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", runner=OfflineRunner())
            payload = validate_output(root / "source")
            self.assertFalse(payload["classification"]["singleGuaranteedNationalCpoDirectTariff"])
            self.assertIsNone(payload["operatorDirect"]["bumpOperatedStations"]["nationalEurPerKwh"])
            spec = next(row for row in read_sources() if row["id"] == "FR:bump_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), runner=OfflineRunner())
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)

    def test_missing_historical_evidence_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, "Historical Bump official method failed"):
                run(Path(temp), runner=OfflineRunner(missing_marker=True))


if __name__ == "__main__":
    unittest.main()
