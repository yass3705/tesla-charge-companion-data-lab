"""Offline execution of the preserved five-script REVE v2 national chain."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from v9_rebuild import reve_national
from v9_rebuild.orchestrator import read_sources, run_source


LOCATION = {"id": "L1", "name": "Fixture", "address": "Fixture street",
            "coordinates": {"latitude": 40.0, "longitude": -3.0}, "owner": {"name": "Fixture"},
            "status": "AVAILABLE", "evses": [{"evse_id": "ES*FIX*E1", "connectors": [
                {"id": "C1", "standard": "IEC_62196_T2", "max_electric_power": 22000,
                 "tariffs": [{"tariff": {"currency": "EUR", "elements": [
                     {"price_components": [{"type": "ENERGY", "price": 0.4}]}]}}]}]}]}


class OfflineNodeRunner:
    def __init__(self, pages=1):
        self.pages = pages

    def __call__(self, command, **kwargs):
        if command[-1].endswith("reve-v2-web-extract.mjs"):
            preload = Path(kwargs["cwd"]) / "fixture_fetch.mjs"
            body = json.dumps({"data": [LOCATION], "total_pages": self.pages})
            preload.write_text("globalThis.fetch=async()=>new Response(" + json.dumps(body) +
                               ",{status:200,headers:{'content-type':'application/json'}});\n")
            command = ["node", "--import", str(preload), command[-1]]
        return subprocess.run(command, **kwargs)


class ReveNationalMigrationTests(unittest.TestCase):
    def test_complete_small_snapshot_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            reve_national.run(base / "direct", runner=OfflineNodeRunner())
            result = reve_national.validate_output(base / "direct")
            self.assertEqual(result["stations"], 1)
            self.assertEqual(result["uniqueEvseIds"], 1)
            self.assertEqual(result["directOffers"], 1)
            source = next(row for row in read_sources() if row["id"] == "ES:reve_national")

            def process(command, **_):
                reve_national.run(Path(command[-1]), runner=OfflineNodeRunner())
                return subprocess.CompletedProcess(command, 0)

            status = run_source(source, base / "artifacts", attempts=1, runner=process)
            self.assertEqual(status["status"], "ok")
            self.assertTrue((base / "artifacts" / status["artifact"]).is_file())
            offer_tile = next((base / "direct" / reve_national.OFFERS).glob("offers_*.json.gz"))
            offer_tile.write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "SHA256"):
                reve_national.validate_output(base / "direct")

    def test_incomplete_pagination_never_publishes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "web-extract"):
                reve_national.run(base / "incomplete", runner=OfflineNodeRunner(pages=2))
            self.assertFalse((base / "incomplete" / reve_national.STATIONS).exists())


if __name__ == "__main__":
    unittest.main()
