"""Offline Blink PCPR collection, exact connector audit and isolation."""

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
from v9_rebuild.uk_blink import RAW, load_script, run, validate_output
from v9_rebuild.electroverse import ROOT

LOCATION = {
    "id": "1", "country": "GBR", "country_code": "GB", "party_id": "BLI",
    "operator": {"name": "Blink Charging"}, "publish": True,
    "coordinates": {"latitude": "51.5", "longitude": "-0.1"},
    "evses": [{"evse_id": "GB*BLI*E1", "connectors": [
        {"id": "1", "max_electric_power": 22000, "tariff_ids": ["T1"]},
        {"id": "2", "max_electric_power": 50000, "tariff_ids": ["UNKNOWN"]}]}],
}
TARIFF = {"id": "T1", "country_code": "GB", "party_id": "BLI", "currency": "GBP",
          "elements": [{"price_components": [{"type": "ENERGY", "price": 0.5, "step_size": 1}]}]}


class BlinkMigrationTests(unittest.TestCase):
    def fixture(self, root: Path, locations=None, tariffs=None) -> Path:
        path = root / "fixture.json"
        path.write_text(json.dumps({"locations": [LOCATION] if locations is None else locations,
                                    "tariffs": [TARIFF] if tariffs is None else tariffs}))
        return path

    def test_historical_chain_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"BLINK_PCPR_TOKEN": "offline-fixture"}):
            root = Path(temp)
            fixture = self.fixture(root)
            run(root / "source", fixture=fixture)
            doc = validate_output(root / "source")
            connectors = doc["sources"][0]["locations"][0]["evses"][0]["connectors"]
            self.assertEqual(connectors[0]["tariff_ids"], ["T1"])
            self.assertEqual(connectors[1]["tariff_ids"], [])
            spec = next(row for row in read_sources() if row["id"] == "GB:blink_pcpr")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), fixture=fixture)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 4)

    def test_empty_feed_is_visible_without_invented_tariff(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"BLINK_PCPR_TOKEN": "offline-fixture"}):
            root = Path(temp)
            run(root / "source", fixture=self.fixture(root, locations=[], tariffs=[]))
            audit = json.loads((root / "source/reports/uk/blink-pcpr-validation-latest.json").read_text())
            self.assertFalse(audit["validatedForV9"])
            self.assertEqual(audit["status"], "no_exact_tariff_available")

    def test_wrong_operator_and_corrupted_raw_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"BLINK_PCPR_TOKEN": "offline-fixture"}):
            root = Path(temp)
            bad = {**LOCATION, "operator": {"name": "Another CPO"}}
            with self.assertRaisesRegex(RuntimeError, "different CPO"):
                run(root / "bad", fixture=self.fixture(root, locations=[bad]))
            run(root / "good", fixture=self.fixture(root))
            (root / "good" / RAW).write_bytes(b"broken")
            with self.assertRaises(OSError):
                validate_output(root / "good")

    def test_preserved_page_boundary_and_budget(self):
        module = load_script(ROOT / "scripts/uk_blink_pcpr_collect.py", "v9_uk_blink_pagination_test")
        pages = [io.BytesIO(json.dumps({"status_code": 1000, "data": [{}] * 1000}).encode()),
                 io.BytesIO(json.dumps({"status_code": 1000, "data": []}).encode())]
        with patch.object(module.urllib.request, "urlopen", side_effect=pages) as fetch, patch.object(module.time, "sleep"):
            rows, calls = module.collect("locations", "Token offline")
        self.assertEqual((len(rows), calls), (1000, 2))
        self.assertIn("offset=1000", fetch.call_args_list[1].args[0].full_url)


if __name__ == "__main__":
    unittest.main()
