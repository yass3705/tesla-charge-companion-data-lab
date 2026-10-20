"""Offline historical Révéo official/OCPI classification and isolated handoff."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.cwd_script import run, validate_output
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
import reveo_official as historical  # noqa: E402

PAGES = {
    historical.PRICING_URL: "Le prix du badge Révéo : 12,00€ Abonnement Révéo : 1,50€/mois/badge jusqu’à 50% de remise Hérault Pyrénées-Orientales Toulouse Métropole prix à la minute durée de connexion",
    historical.HOW_URL: "Scanner le QR code tarif public utilisateur occasionnel réseaux partenaires",
    historical.ROAMING_PAGE_URL: "transmise en OCPI via GIREVE FR*M31 / FR*S48 / FR*S12 / FR*S34 tariffs.json",
}


class Runner:
    def __init__(self, tariffs=None, broken=False):
        self.tariffs = tariffs if tariffs is not None else [{
            "country_code": "FR", "party_id": "M31", "id": "historical-fixture",
            "currency": "EUR", "elements": [],
            "tariff_alt_text": [{"language": "fr", "text": "Tarif technique OCPI"}],
        }]
        self.broken = broken

    def __call__(self, command, **kwargs):
        old = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            def fetch(url, attempts=3):
                if self.broken and url == historical.OCPI_URL:
                    return 200, b"not-json"
                raw = json.dumps(self.tariffs).encode() if url == historical.OCPI_URL else PAGES[url].encode()
                return 200, raw
            with patch.object(historical, "fetch", side_effect=fetch), patch("builtins.print"):
                historical.main()
        except (RuntimeError, json.JSONDecodeError):
            return SimpleNamespace(returncode=2)
        finally:
            os.chdir(old)
        return SimpleNamespace(returncode=0)


class ReveoRelativeMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", "reveo_official", runner=Runner())
            payload = validate_output(root / "source", "reveo_official")
            self.assertEqual(payload["technicalTariffEvidence"]["activeTariffs"][0]["classification"],
                             "cpo_ocpi_tariff_transmitted_to_roaming_via_gireve")
            self.assertTrue(payload["roaming"]["separateFromDirectRetail"])
            spec = next(row for row in read_sources() if row["id"] == "FR:reveo_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "reveo_official", runner=Runner())
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)

    def test_empty_complete_feed_and_corrupt_feed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "empty", "reveo_official", runner=Runner(tariffs=[]))
            payload = validate_output(root / "empty", "reveo_official")
            self.assertEqual(payload["technicalTariffEvidence"]["activeTariffs"], [])
            with self.assertRaisesRegex(RuntimeError, "Historical reveo_official method failed"):
                run(root / "broken", "reveo_official", runner=Runner(broken=True))
            self.assertFalse((root / "broken/data/operator_direct/reveo_official_france.json").exists())


if __name__ == "__main__":
    unittest.main()
