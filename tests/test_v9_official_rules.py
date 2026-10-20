"""Offline historical execution for Fastned and IONITY official rules."""

from __future__ import annotations

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
import fastned_official as fastned  # noqa: E402
import ionity_official as ionity  # noqa: E402
import atlante_official as atlante  # noqa: E402
import etotem_official as etotem  # noqa: E402


FASTNED_PAGES = {
    "tariffs": "Prix standard € 0,61 en France Bénéficiez de 10 % de réduction Économisez 30% € 0,43 (€ 0,43 par kWh en France)",
    "how_to_charge": "Payer par carte bancaire réservation de 40 € Apple Pay",
    "terms": "Conditions d'utilisation",
}
IONITY_PAGES = {
    "access": "France 0,55 €/kWh prix direct en kWh 0,52 €/kWh prix en kWh-go 11,99 prix mensuel de l'électricité 0,31 €/kWh power-monthly-kwh-price 5,99 prix mensuel du mouvement 0,39 €/kWh motion-monthly-kwh-price 119,99 prix annuel de l'électricité 99,99 prix réduit annuel Power 0,33 €/kWh power-annual-kwh-price 59,99 prix annuel du mouvement 49,99 prix réduit annuel de Motion 0,41 €/kWh motion-annual-kwh-price",
    "pricingFaq": "les prix peuvent varier d'un site à l'autre fournisseur de services de mobilité",
    "subscriptions": "IONITY Motion IONITY Power",
    "terms": "24 pays",
    "preauth": "40 EUR",
    "priceChange": "1er juillet 2026",
}
ATLANTE_PAGES = {
    "app": "stations Atlante : 0,29 €/kWh stations Powerdot: 0,42 €/kWh stations ChargeLeague : 0,49 €/kWh Electra, Fastned et IONITY 9,99 €/mois sans engagement réservé uniquement aux particuliers le prix de la recharge varie selon le pays et la borne choisie consultez l'application myAtlante Mastercard, Visa, Maestro American Express Apple Pay",
    "drivers": "application myAtlante carte RFID Atlante applications de mobilité (eMSP) surcoût appliqué par l’opérateur de mobilité carte de crédit",
    "home": "jusqu'à 400 kW",
    "goPress": "Atlante Go",
}
ETOTEM_PAGES = {
    "users": "plus de 900 points de charge 0% de commission pas de frais d'abonnement mensuel 250 000 points de charge",
    "mobility": "formule liberté je paie uniquement ce que je consomme en kWh abonnement SEMOB 45 100 0,45 0,59",
    "home": "e-Totem",
    "saintLouis": "politique tarifaire des bornes de recharge 0,30 0,39 0,45 0,49 10 minutes de franchise 1 € / 15 min 3 € / 15 min limitée à 2 € maximum",
    "dataGouvOrg": "FR*ESE",
}


class OfflineRunner:
    def __init__(self, source, missing=False):
        self.source = source
        self.missing = missing

    def __call__(self, command, **kwargs):
        module = {"fastned": fastned, "ionity": ionity, "atlante": atlante, "etotem": etotem}[self.source]
        pages = {"fastned": FASTNED_PAGES, "ionity": IONITY_PAGES, "atlante": ATLANTE_PAGES, "etotem": ETOTEM_PAGES}[self.source]
        url_keys = {value: key for key, value in module.SOURCES.items()}
        def fetch(url):
            if url in url_keys:
                key = url_keys[url]
                return 200, "" if self.missing and key == ("tariffs" if self.source == "fastned" else "app") else pages[key]
            return 200, "EUR 0,43/kWh membres Gold tarif standard : 0,61/kWh"
        try:
            with patch.object(module, "fetch", side_effect=fetch), \
                 patch.object(sys, "argv", command[1:]), patch("builtins.print"):
                module.main()
        except RuntimeError:
            return SimpleNamespace(returncode=2)
        return SimpleNamespace(returncode=0)


class OfficialRulesMigrationTests(unittest.TestCase):
    def test_preserved_methods_and_orchestrator(self):
        for source in ("atlante", "etotem", "fastned", "ionity"):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                run(root / "source", source, runner=OfflineRunner(source))
                payload = validate_output(root / "source", source)
                self.assertEqual(payload["country"], "FR")
                spec = next(row for row in read_sources() if row["id"] == f"FR:{source}_official")
                def outer(command, **kwargs):
                    run(Path(command[command.index("--out") + 1]), source, runner=OfflineRunner(source))
                    return SimpleNamespace(returncode=0)
                artifact = run_source(spec, root / "artifacts", runner=outer)
                self.assertEqual(artifact["status"], "ok")
                self.assertEqual(len(artifact["files"]), 2)

    def test_missing_source_fails_without_publishing(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, "Historical fastned official method failed"):
                run(Path(temp), "fastned", runner=OfflineRunner("fastned", missing=True))


if __name__ == "__main__":
    unittest.main()
