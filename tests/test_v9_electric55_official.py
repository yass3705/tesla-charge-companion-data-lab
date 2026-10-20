"""Offline execution of the preserved E55C official tariff classification."""

import json
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
import electric55_official as historical  # noqa: E402

TUTORIAL = ("Payez à l'acte par carte bancaire sans inscription sans application sans badge. "
            "Le tarif applicable vous est présenté avant validation du paiement. "
            "Application de mobilité. Le prix affiché et facturé peut varier selon l'opérateur utilisé. "
            "Prix TTC facturés par E55C aux opérateurs de mobilité. "
            "De jour entre 7h et 23h, de nuit entre 23h et 7h. "
            + " ".join(str(x).replace(".", ",") for x in list(historical.DAY_RATES.values()) + list(historical.NIGHT_RATES.values())))
FAQ = "Type 2, badge et application. Ne propose pas de facturation directe; paiement par carte bancaire n'est donc pas directement autorisé."
META = json.dumps({"organization": {"name": "Electric 55 Charging"}, "resources": [
    {"schema": {"name": "etalab/schema-irve-statique"}},
    {"schema": {"name": "etalab/schema-irve-dynamique"}}]})


def runner(command, **kwargs):
    def fetch(url):
        key = next(k for k, value in historical.SOURCES.items() if value == url)
        return 200, {"tutorial": TUTORIAL, "faq": FAQ, "dataGouv": META}[key], "application/json" if key == "dataGouv" else "text/html"
    with patch.object(historical, "fetch", side_effect=fetch), patch.object(sys, "argv", command[1:]), patch("builtins.print"):
        historical.main()
    return SimpleNamespace(returncode=0)


class Electric55OfficialMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", "electric55", runner=runner)
            payload = validate_output(root / "source", "electric55")
            self.assertFalse(payload["indicativeWholesaleTariffsToMobilityOperators"]["consumerTariff"])
            spec = next(row for row in read_sources() if row["id"] == "FR:electric55_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "electric55", runner=runner)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)


if __name__ == "__main__":
    unittest.main()
