"""Offline Allego UK and Source EV exact-connector PCPR handoff."""

from __future__ import annotations

import json
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.orchestrator import read_sources, run_source
from v9_rebuild.uk_pcpr import paths, run, validate_output
from v9_rebuild.uk_blink import load_script
from v9_rebuild.electroverse import ROOT


def fixture(provider: str, *, empty=False, wrong=False) -> dict:
    if empty:
        return {"locations": [], "tariffs": []}
    source_ev = provider == "source_ev"
    party = "SGB" if source_ev else "ABC"
    tariff_id = "GB*SGB_02" if source_ev else "T1"
    loc = {
        "id": "L1", "country_code": "GB", "country": "GBR", "party_id": party,
        "operator": {"name": "ChargePoint" if wrong else "Source EV" if source_ev else "Allego UK"},
        "publish": True, "coordinates": {"latitude": "51.5", "longitude": "-0.1"},
        "evses": [{"uid": "1", "evse_id": f"GB*{party}*E1", "status": "AVAILABLE",
                   "connectors": [{"id": "1", "standard": "IEC_62196_T2", "max_electric_power": 22000,
                                   "tariff_ids": [tariff_id]}]}],
    }
    tariff = {"id": tariff_id, "country_code": "GB", "party_id": party, "currency": "GBP",
              "elements": [{"price_components": [{"type": "ENERGY", "price": 0.7416667 if source_ev else 0.5,
                                                  "vat": 0.2 if source_ev else 20, "step_size": 1}]}]}
    return {"locations": [loc], "tariffs": [tariff]}


class UKPCPRMigrationTests(unittest.TestCase):
    def fixture_file(self, root: Path, provider: str, **kwargs) -> Path:
        path = root / "fixture.json"
        path.write_text(json.dumps(fixture(provider, **kwargs)), encoding="utf-8")
        return path

    def test_two_historical_methods_and_orchestrator(self):
        for provider, secret in (("allego_uk", "ALLEGO_UK_PCPR_TOKEN"), ("source_ev", "SOURCE_EV_PCPR_TOKEN")):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {secret: "offline-fixture"}):
                root = Path(temp)
                source = self.fixture_file(root, provider)
                run(root / "source", provider, fixture=source)
                doc = validate_output(root / "source", provider)
                self.assertEqual(len(doc["sources"][0]["tariffs"]), 1)
                spec = next(row for row in read_sources() if row["id"] == f"GB:{provider}_pcpr")
                def outer(command, **kwargs):
                    run(Path(command[command.index("--out") + 1]), provider, fixture=source)
                    return SimpleNamespace(returncode=0)
                artifact = run_source(spec, root / "artifacts", runner=outer)
                self.assertEqual(artifact["status"], "ok")
                self.assertEqual(len(artifact["files"]), 4)

    def test_empty_and_wrong_operator_are_distinct(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"ALLEGO_UK_PCPR_TOKEN": "offline-fixture"}):
            root = Path(temp)
            run(root / "empty", "allego_uk", fixture=self.fixture_file(root, "allego_uk", empty=True))
            audit = json.loads((root / "empty" / paths("allego_uk")[3]).read_text())
            self.assertFalse(audit["validatedForV9"])
            self.assertEqual(audit["status"], "no_exact_tariff_available")
            with self.assertRaisesRegex(RuntimeError, "different CPO"):
                run(root / "wrong", "allego_uk", fixture=self.fixture_file(root, "allego_uk", wrong=True))

    def test_preserved_page_boundary_and_budget(self):
        module = load_script(ROOT / "scripts/uk_pcpr_cpo_collect.py", "v9_uk_pcpr_pagination_test")
        pages = [io.BytesIO(json.dumps({"status_code": 1000, "data": [{}] * 1000}).encode()),
                 io.BytesIO(json.dumps({"status_code": 1000, "data": [{"id": "last"}]}).encode())]
        budget = [0]
        with patch.object(module.urllib.request, "urlopen", side_effect=pages) as fetch, patch.object(module.time, "sleep"):
            rows = module.collect("locations", "Token offline", budget)
        self.assertEqual(len(rows), 1001)
        self.assertEqual(budget[0], 2)
        self.assertIn("offset=1000", fetch.call_args_list[1].args[0].full_url)
        with self.assertRaisesRegex(RuntimeError, "request budget reached"):
            module.collect("locations", "Token offline", [28])


if __name__ == "__main__":
    unittest.main()
