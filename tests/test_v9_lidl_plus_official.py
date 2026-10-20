"""Offline historical execution for the Lidl Plus network rule."""

import sys
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.electroverse import ROOT
from v9_rebuild.official_rules import run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
import lidl_plus_official as historical  # noqa: E402

PAGE = ("Même tarif facturé au kWh partout en France. "
        "Tarifs bornes de recharge DC 0,29 € / kWh pré-autorisation 50 €. "
        "Tarifs bornes de recharge AC 0,18 € / kWh pré-autorisation 50 €. "
        "E-Mobilité - Protection des données")


def runner(command, **kwargs):
    with patch.object(historical, "fetch", return_value=(200, PAGE)), patch.object(sys, "argv", command[1:]), patch("builtins.print"):
        historical.main()
    return SimpleNamespace(returncode=0)


class LidlPlusOfficialMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", "lidl_plus", runner=runner)
            payload = validate_output(root / "source", "lidl_plus")
            self.assertEqual({row["currentType"] for row in payload["pricing"]}, {"AC", "DC"})
            archived = json.loads((ROOT / "data/operator_direct/lidl_plus_france.json").read_text())
            self.assertEqual([(row["currentType"], row["pricePerKwh"]) for row in payload["pricing"]],
                             [(row["currentType"], row["pricePerKwh"]) for row in archived["pricing"]])
            spec = next(row for row in read_sources() if row["id"] == "FR:lidl_plus_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "lidl_plus", runner=runner)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)

    def test_missing_national_scope_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "no longer confirms"):
            historical.build_payload(PAGE.replace("Même tarif facturé au kWh partout en France.", ""), 200)


if __name__ == "__main__":
    unittest.main()
