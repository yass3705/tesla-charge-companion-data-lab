"""Offline execution and technical validation of preserved Allego rules."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.allego_official import OUTPUT, run, validate_output
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
import allego_official as historical  # noqa: E402

ARCHIVE = json.loads((ROOT / OUTPUT).read_text(encoding="utf-8"))


class OfflineRunner:
    def __init__(self, missing_caveat=False):
        self.missing_caveat = missing_caveat

    def __call__(self, command, **kwargs):
        pricing = "les tarifs peuvent varier en fonction du type de chargeur" if not self.missing_caveat else "tarifs"
        def fetch(url):
            if url == historical.SOURCES["pricing"]:
                return 200, pricing
            return 200, "historical fixture"
        try:
            with patch.object(historical, "fetch", side_effect=fetch), \
                 patch.object(historical, "static_country_pricing_block", return_value=("historical pricing", {"accessMode": "fixture"})), \
                 patch.object(historical, "parse_country_direct", return_value={"defaultTariffsEurPerKwh": {"ultraFast": 0.59, "fast": 0.49, "regular": 0.39}}), \
                 patch.object(historical, "parse_fee_rules", return_value=ARCHIVE["fees"]), \
                 patch.object(historical, "parse_promo", return_value=ARCHIVE["operatorDirect"]["allegoPlusPromotion"]), \
                 patch.object(historical, "parse_roaming", return_value=ARCHIVE["roaming"]), \
                 patch.object(historical, "browser_select_country", side_effect=RuntimeError("app unavailable")), \
                 patch.object(historical, "parse_station", side_effect=lambda key, url, text: {"name": key, "url": url}), \
                 patch.object(sys, "argv", command[1:]), patch("builtins.print"):
                historical.main()
        except RuntimeError:
            return SimpleNamespace(returncode=2)
        return SimpleNamespace(returncode=0)


class AllegoOfficialMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", runner=OfflineRunner())
            payload = validate_output(root / "source")
            self.assertTrue(payload["classification"]["stationLevelPriceLookupRequiredForExactSimulation"])
            spec = next(row for row in read_sources() if row["id"] == "FR:allego_official")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), runner=OfflineRunner())
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)

    def test_missing_historical_caveat_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, "Historical Allego official method failed"):
                run(Path(temp), runner=OfflineRunner(missing_caveat=True))

    def test_missing_source_evidence_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root, runner=OfflineRunner())
            path = root / OUTPUT
            payload = json.loads(path.read_text())
            payload["sourceEvidence"]["sources"] = []
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "technical contract"):
                validate_output(root)


if __name__ == "__main__":
    unittest.main()
