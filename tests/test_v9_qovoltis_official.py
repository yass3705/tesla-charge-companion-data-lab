"""Offline historical execution for Qovoltis official station-specific rules."""

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
import qovoltis_official as historical  # noqa: E402

PAGES = {
    "nomadTerms": "Tarifs des bornes de recharge Qovoltis ouvertes au public à la localisation. Bornes de recharge partenaire et opérateurs partenaires à la localisation. Offre Nomad Open, offre Nomad Gold sans frais d'accès. Tarifs applicables pour la borne concernée.",
    "adHoc": "Je recharge par carte bancaire sans compte Qovoltis.",
    "dataGouvOrg": "Qovoltis IRVE statique",
}


def runner(command, **kwargs):
    def fetch(url):
        key = next(k for k, value in historical.SOURCES.items() if value == url)
        return 200, PAGES[key]
    with patch.object(historical, "fetch", side_effect=fetch), patch.object(sys, "argv", command[1:]), patch("builtins.print"):
        historical.main()
    return SimpleNamespace(returncode=0)


class QovoltisOfficialMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", "qovoltis", runner=runner)
            payload = validate_output(root / "source", "qovoltis")
            self.assertIsNone(payload["operatorDirect"]["nomadOpen"]["nationalEurPerKwh"])
            spec = next(row for row in read_sources() if row["id"] == "FR:qovoltis_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "qovoltis", runner=runner)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)


if __name__ == "__main__":
    unittest.main()
