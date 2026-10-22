"""Offline execution of archived IZIVIA FAST capture and exact-station compiler."""

import gzip
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from v9_rebuild import izivia_fast
from v9_rebuild.orchestrator import read_sources, run_source


def archived_fixture():
    national = izivia_fast._gz(izivia_fast.ROOT / izivia_fast.NATIONAL)
    capture = izivia_fast._gz(izivia_fast.ROOT / izivia_fast.CAPTURE)
    station = next(row for row in national["stations"] if row.get("stationId") == "FRIZFPFAST422")
    captured = next(row for row in capture["stations"] if row.get("stationId") == "FRIZFPFAST422")
    return station, captured


class FixtureRunner:
    def __init__(self, *, price=True, error=False):
        self.price = price
        self.error = error
        self.calls = []

    def __call__(self, command, **kwargs):
        if not command[1].endswith("izivia_fast_capture.py"):
            return subprocess.run(command, **kwargs)
        out = Path(kwargs["cwd"])
        station, captured = archived_fixture()
        source = out / izivia_fast.NATIONAL
        with gzip.open(source, "wt", encoding="utf-8") as stream:
            json.dump({"stations": [station]}, stream)
        if str(out / "scripts") not in sys.path:
            sys.path.insert(0, str(out / "scripts"))
        spec = importlib.util.spec_from_file_location("izivia_fast_fixture", command[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.SOURCE = source
        module.OUTPUT = out / izivia_fast.TEMP_CAPTURE
        module.SUMMARY = out / izivia_fast.TEMP_SUMMARY

        def request(path, method="GET", body=None):
            self.calls.append(path)
            if path == "map/markers":
                return 200, [{"id": captured["mapId"], "pos": [station["lon"], station["lat"]]}]
            if path == f"charging-locations/{captured['mapId']}":
                return 200, captured["mapDetail"]
            if "pricing-info-items" in path:
                if self.error:
                    return 503, {"offlineFixtureError": True}
                text = captured["directRawPricing"][0]
                return 200, [{"itemType": "charging_location", "rawPricingInfos": [text] if self.price else []}]
            raise AssertionError(path)

        with patch.object(module, "request", side_effect=request), redirect_stdout(io.StringIO()):
            module.main()
        return subprocess.CompletedProcess(command, 0)


class IziviaFastMigrationTests(unittest.TestCase):
    def test_exact_archived_offer_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            izivia_fast.run(base / "direct", runner=FixtureRunner())
            offers = izivia_fast.validate_output(base / "direct")
            self.assertEqual(offers["policy"]["capturedStations"], 1)
            self.assertEqual({sid for row in offers["directOffers"] for sid in row["stationIds"]},
                             {"FRIZFPFAST422"})
            source = next(row for row in read_sources() if row["id"] == "FR:izivia_fast")

            def process(command, **_):
                izivia_fast.run(Path(command[-1]), runner=FixtureRunner())
                return subprocess.CompletedProcess(command, 0)

            result = run_source(source, base / "artifacts", attempts=1, runner=process)
            self.assertEqual(result["status"], "ok", result)
            self.assertTrue(any("izivia_fast_inventory" in str(item) for item in result["files"]))

    def test_no_price_is_explicit_and_transport_failure_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            izivia_fast.run(base / "unpriced", runner=FixtureRunner(price=False))
            offers = izivia_fast.validate_output(base / "unpriced")
            self.assertEqual(offers["directOffers"], [])
            with self.assertRaisesRegex(ValueError, "capture incomplete"):
                izivia_fast.run(base / "failed", runner=FixtureRunner(error=True))

    def test_corrupt_identity_and_compiled_price_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            izivia_fast.run(base, runner=FixtureRunner())
            output = base / izivia_fast.OFFERS
            payload = json.loads(output.read_text())
            payload["directOffers"][0]["stationIds"] = ["FRIZFPFAST999"]
            output.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "compiled offer"):
                izivia_fast.validate_output(base)
            izivia_fast.run(base / "fresh", runner=FixtureRunner())
            output = base / "fresh" / izivia_fast.OFFERS
            payload = json.loads(output.read_text())
            payload["directOffers"][0]["pricing"]["rules"][0]["pricePerKwh"] = 9.99
            output.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "compiled offer"):
                izivia_fast.validate_output(base / "fresh")


if __name__ == "__main__":
    unittest.main()
