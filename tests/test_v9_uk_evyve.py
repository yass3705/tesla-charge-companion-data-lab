"""Offline handoff checks for the preserved Evyve PCPR collector."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.orchestrator import read_sources, run_source
from v9_rebuild.uk_evyve import REPORT, run, validate_output


def fixture(*, empty=False, wrong=False):
    if empty:
        return {"locations": [], "tariffs": []}
    operator = "ChargePoint" if wrong else "Evyve"
    return {
        "locations": [{"id": "L1", "country": "GBR", "country_code": "GB", "party_id": "BLI",
                       "operator": {"name": operator}, "publish": True,
                       "coordinates": {"latitude": "51.5", "longitude": "-0.1"},
                       "evses": [{"evse_id": "GB*BLI*E1", "connectors": [
                           {"id": "1", "max_electric_power": 22000, "tariff_ids": ["T1"]},
                           {"id": "2", "max_electric_power": 50000, "tariff_ids": ["UNKNOWN"]}]}]}],
        "tariffs": [{"id": "T1", "country_code": "GB", "party_id": "BLI", "currency": "GBP",
                     "elements": [{"price_components": [{"type": "ENERGY", "price": 0.5, "step_size": 1}]}]}],
    }


class EvyveMigrationTests(unittest.TestCase):
    def fixture_file(self, root, **kwargs):
        path = root / "fixture.json"
        path.write_text(json.dumps(fixture(**kwargs)), encoding="utf-8")
        return path

    def test_historical_collector_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            "EVYVE_PCPR_TOKEN": "offline-Evyve", "BLINK_PCPR_TOKEN": "offline-Blink"}):
            root = Path(temp)
            source = self.fixture_file(root)
            run(root / "source", fixture=source)
            doc = validate_output(root / "source")
            connectors = doc["sources"][0]["locations"][0]["evses"][0]["connectors"]
            self.assertEqual(connectors[0]["tariff_ids"], ["T1"])
            self.assertEqual(connectors[1]["tariff_ids"], [])
            spec = next(row for row in read_sources() if row["id"] == "GB:evyve_pcpr")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), fixture=source)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 3)

    def test_empty_feed_and_wrong_operator(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            "EVYVE_PCPR_TOKEN": "offline-Evyve", "BLINK_PCPR_TOKEN": "offline-Blink"}):
            root = Path(temp)
            run(root / "empty", fixture=self.fixture_file(root, empty=True))
            report = json.loads((root / "empty" / REPORT).read_text())
            self.assertFalse(report["readyForV9Review"])
            with self.assertRaisesRegex(RuntimeError, "different CPO"):
                run(root / "wrong", fixture=self.fixture_file(root, wrong=True))

    def test_secret_isolation_and_corruption(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            "EVYVE_PCPR_TOKEN": "same-token", "BLINK_PCPR_TOKEN": "same-token"}):
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, "equals Blink"):
                run(root / "same", fixture=self.fixture_file(root))
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            "EVYVE_PCPR_TOKEN": "offline-Evyve", "BLINK_PCPR_TOKEN": "offline-Blink"}):
            root = Path(temp)
            run(root / "source", fixture=self.fixture_file(root))
            (root / "source/data/national/uk_evyve_pcpr_v9.json.gz").write_bytes(b"broken")
            with self.assertRaises(OSError):
                validate_output(root / "source")


if __name__ == "__main__":
    unittest.main()
