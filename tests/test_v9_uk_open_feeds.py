"""Offline replay for all UK feed families and technical pagination."""

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from v9_rebuild import uk_open_feeds as adapter
from v9_rebuild.orchestrator import read_sources, run_source


def load_historical(path):
    spec = importlib.util.spec_from_file_location("uk_open_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_runner(*, failed=None, pogo_incomplete=False):
    def run(command, **_):
        module = load_historical(command[1])
        def fetch_source(src):
            if src["name"] == failed:
                raise RuntimeError("offline endpoint failed")
            party = src["party_ids"][0] if src["party_ids"] else "TST"
            location = {"id": src["name"], "party_id": party,
                        "evses": [{"evse_id": f"GB*{party}*E1", "connectors": [{"id": "1", "tariff_ids": ["T1"]}]}]}
            tariff = {"id": "T1", "country_code": "GB", "party_id": party, "currency": "GBP",
                      "elements": [{"price_components": [{"type": "ENERGY", "price": 0.5}]}]}
            audit = {"coverageComplete": not pogo_incomplete, "pricingComplete": True,
                     "failedOffsets": [150] if pogo_incomplete else []} if src["name"] == "PoGo Charge" else None
            return [location], [tariff], audit
        previous = sys.argv
        exit_code = 0
        try:
            sys.argv = command[1:]
            with patch.object(module, "fetch_source", side_effect=fetch_source), redirect_stdout(io.StringIO()):
                module.main()
        except SystemExit as exc:
            exit_code = int(exc.code)
        finally:
            sys.argv = previous
        return subprocess.CompletedProcess(command, exit_code)
    return run


class UkOpenFeedTests(unittest.TestCase):
    def test_all_twelve_sources_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            adapter.run(base / "direct", runner=fixture_runner())
            payload = adapter.validate_output(base / "direct")
            self.assertEqual(payload["summary"]["requestedSources"], 12)
            self.assertEqual(len(payload["sources"]), 12)
            source = next(s for s in read_sources() if s["id"] == "UK:validated_open_feeds")
            def process(command, **_):
                adapter.run(Path(command[-1]), runner=fixture_runner())
                return subprocess.CompletedProcess(command, 0)
            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_failed_source_cannot_finalize(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "failed"):
                adapter.run(base, runner=fixture_runner(failed="char.gy"))
            self.assertFalse((base / adapter.OUTPUT).exists())
            with self.assertRaisesRegex(ValueError, "contract"):
                adapter.run(base / "pogo", runner=fixture_runner(pogo_incomplete=True))

    def test_existing_offset_pagination_and_pogo_partial_tail(self):
        module = load_historical(adapter.ROOT / adapter.SCRIPT)
        def request_page(url, **_):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            offset = int(q.get("offset", [0])[0]); limit = int(q.get("limit", [50])[0])
            total = 51
            return {"data": [{"id": i} for i in range(offset, min(offset + limit, total))], "meta": {"total": total}}, {}
        with patch.object(module, "request_json", side_effect=request_page):
            self.assertEqual(len(module.fetch_offset("https://example.test/locations")), 51)
        def broken_page(url, **_):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            offset = int(q.get("offset", [0])[0])
            return {"data": [{"id": i} for i in range(50)] if offset == 0 else [], "meta": {"total": 51}}, {}
        with patch.object(module, "request_json", side_effect=broken_page):
            with self.assertRaisesRegex(RuntimeError, "pagination incomplete"):
                module.fetch_offset("https://example.test/locations")

        src = next(row for row in module.SOURCES if row["name"] == "PoGo Charge")
        def pogo_page(url, **_):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            offset = int(q.get("offset", [0])[0]); limit = int(q.get("limit", [50])[0])
            if offset == 150 and limit == 1:
                raise RuntimeError("last source row failed")
            return {"data": [{"id": i, "evses": []} for i in range(offset, min(offset + limit, 151))],
                    "meta": {"total": 151}}, {}
        with patch.object(module, "request_json", side_effect=pogo_page):
            locations, tariffs, audit = module.fetch_pogo_hybrid(src)
        self.assertEqual(len(locations), 150)
        self.assertEqual(audit["failedOffsets"], [150])
        self.assertFalse(audit["coverageComplete"])
        self.assertEqual(len(tariffs), 2)


if __name__ == "__main__":
    unittest.main()
