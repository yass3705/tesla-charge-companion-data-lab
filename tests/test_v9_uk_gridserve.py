"""Offline historical GRIDSERVE collector and exact connector builder."""

import gzip
import io
import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.orchestrator import read_sources, run_source
from v9_rebuild.uk_gridserve import INTEGRATION_REPORT, STAGED, execute_collector, run, validate_output
from v9_rebuild.uk_blink import load_script
from v9_rebuild.electroverse import ROOT


def fixture(missing=False, empty=False):
    if empty:
        return [], []
    location = {"id": "L1", "country_code": "GB", "party_id": "GRD", "publish": True,
                "name": "Public retail", "coordinates": {"latitude": "51.5", "longitude": "-0.1"},
                "evses": [{"uid": "E1", "evse_id": "GB*GRD*E1", "status": "AVAILABLE",
                           "connectors": [{"id": "1", "max_electric_power": 50000,
                                           "tariff_ids": ["UNKNOWN" if missing else "T1"]}]}]}
    tariff = {"id": "T1", "country_code": "GB", "party_id": "GRD", "currency": "GBP",
              "elements": [{"price_components": [{"type": "ENERGY", "price": 0.5, "step_size": 1}]}]}
    return [location], [tariff]


class Response(io.BytesIO):
    def __init__(self, payload, headers=None):
        super().__init__(json.dumps(payload).encode())
        self.status = 200
        self.headers = headers or {}


def collector_for(locations, tariffs, pages=False):
    def collect(script, out):
        calls = []
        def urlopen(request, timeout=60):
            url = request.full_url
            calls.append(url)
            if "/locations" in url:
                if "page=2" in url:
                    return Response({"data": []})
                headers = {"Link": '<https://api.gridserve.com/ocpi/v1/locations?page=2>; rel="next"'} if pages else {}
                return Response({"data": locations}, headers)
            return Response({"data": tariffs})
        with patch.object(urllib.request, "urlopen", side_effect=urlopen), patch("time.sleep"), patch.dict(os.environ, {"GRIDSERVE_PCPR_API_KEY": "offline-fixture"}):
            execute_collector(script, out)
        return calls
    return collect


class GridserveMigrationTests(unittest.TestCase):
    def test_historical_collector_builder_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"GRIDSERVE_PCPR_API_KEY": "offline-fixture", "GRIDSERVE_API_KEY": "offline-fixture"}):
            root = Path(temp)
            locations, tariffs = fixture()
            collector = collector_for(locations, tariffs, pages=True)
            run(root / "source", collector=collector)
            staged = validate_output(root / "source")
            self.assertEqual(staged["sources"][0]["locations"][0]["evses"][0]["connectors"][0]["tariff_ids"], ["T1"])
            report = json.loads((root / "source" / INTEGRATION_REPORT).read_text())
            self.assertEqual(report["publicConnectors"], 1)
            spec = next(row for row in read_sources() if row["id"] == "GB:gridserve_pcpr")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), collector=collector)
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok", artifact)
            self.assertEqual(len(artifact["files"]), 6)

    def test_unmapped_and_empty_are_unpriced(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"GRIDSERVE_PCPR_API_KEY": "offline-fixture", "GRIDSERVE_API_KEY": "offline-fixture"}):
            root = Path(temp)
            run(root / "unmapped", collector=collector_for(*fixture(missing=True)))
            report = json.loads((root / "unmapped" / INTEGRATION_REPORT).read_text())
            self.assertFalse(report["validatedForV9"])
            self.assertEqual(report["publicUnmappedTariffReferences"], ["UNKNOWN"])
            run(root / "empty", collector=collector_for(*fixture(empty=True)))
            self.assertFalse(json.loads((root / "empty" / INTEGRATION_REPORT).read_text())["validatedForV9"])
            (root / "empty" / STAGED).write_bytes(b"broken")
            with self.assertRaises((OSError, gzip.BadGzipFile)):
                validate_output(root / "empty")

    def test_private_location_and_duplicate_connector(self):
        builder = load_script(ROOT / "scripts/uk_gridserve_v9_prepare.py", "v9_gridserve_private_fixture")
        locations, tariffs = fixture()
        private = dict(locations[0], id="PRIVATE", parking_type="PRIVATE")
        public_doc = {"locations": [private, locations[0]], "collectedAt": "2026-10-20T00:00:00Z"}
        tariff_doc = {"tariffs": tariffs, "collectedAt": "2026-10-20T00:00:00Z"}
        _, crosswalk, report = builder.build(public_doc, tariff_doc)
        self.assertEqual(report["publicLocations"], 1)
        self.assertEqual(len(crosswalk["links"]), 1)
        with self.assertRaisesRegex(AssertionError, "Duplicate physical connector"):
            builder.build({"locations": [locations[0], locations[0]], "collectedAt": public_doc["collectedAt"]}, tariff_doc)


if __name__ == "__main__":
    unittest.main()
