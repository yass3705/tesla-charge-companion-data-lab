"""Offline operator API pagination, audit and artifact isolation."""

import io
import json
import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from v9_rebuild.orchestrator import read_sources, run_source
from v9_rebuild.uk_connected_kerb_operator import AUDIT, LOCATIONS, REPORT, run, validate_output


def location(number):
    return {"id": f"loc-{number}", "name": f"Fixture {number}", "publish": True,
            "country_code": "GB", "last_updated": "2026-10-10T00:00:00Z",
            "coordinates": {"latitude": 51.5, "longitude": -0.1},
            "evses": [{"uid": f"evse-{number}", "evse_id": f"GB*CK0*E{number}",
                       "physical_reference": str(1000 + number),
                       "connectors": [{"id": f"connector-{number}", "tariff_ids": ["tariff-1"]}]}]}


TARIFF = {"id": "tariff-1", "currency": "GBP", "elements": [{"price_components": [
    {"type": "ENERGY", "price": 0.4, "vat": 20}]}]}


class OfflineRunner:
    def __init__(self, missing_second=False, fail=False):
        self.missing_second = missing_second
        self.fail = fail

    def __call__(self, command, **kwargs):
        if self.fail:
            return SimpleNamespace(returncode=2)

        def urlopen(request, **_):
            url = request.full_url
            page = int(parse_qs(urlparse(url).query)["page"][0])
            if "charging-pools" in url:
                data = [] if page == 2 and self.missing_second else [location(page)]
                response = {"data": data, "pagination": {"totalPages": 2, "totalCount": 2}}
            else:
                response = {"data": [TARIFF], "pagination": {"totalPages": 1, "totalCount": 1}}
            return io.BytesIO(json.dumps(response).encode())

        with patch.dict(os.environ, {"CONNECTED_KERB_TOKEN": "fixture-token"}), \
             patch("urllib.request.urlopen", side_effect=urlopen), \
             patch.object(sys, "argv", command[1:]), patch("builtins.print"):
            try:
                runpy.run_path(command[1], run_name="__main__")
            except (ValueError, RuntimeError):
                return SimpleNamespace(returncode=2)
        return SimpleNamespace(returncode=0)


class ConnectedKerbOperatorTests(unittest.TestCase):
    def test_two_pages_then_audit_and_orchestration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "direct", runner=OfflineRunner())
            report = validate_output(root / "direct")
            self.assertEqual(report["pagination"]["locations"]["pages"], 2)
            self.assertEqual(report["counts"]["locations"], 2)
            self.assertTrue((root / "direct" / LOCATIONS).is_file())
            self.assertTrue((root / "direct" / AUDIT).is_file())
            spec = next(row for row in read_sources() if row["id"] == "GB:connected_kerb_operator")

            def simulated_process(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), runner=OfflineRunner())
                return SimpleNamespace(returncode=0)

            with patch.dict(os.environ, {"CONNECTED_KERB_TOKEN": "fixture-token"}):
                artifact = run_source(spec, root / "artifacts", runner=simulated_process)
            self.assertEqual(artifact["status"], "ok")

    def test_incomplete_pagination_and_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, "historical|Historical"):
                run(root / "incomplete", runner=OfflineRunner(missing_second=True))
            with self.assertRaisesRegex(RuntimeError, "historical|Historical"):
                run(root / "failed", runner=OfflineRunner(fail=True))
            run(root / "corrupt", runner=OfflineRunner())
            report_path = root / "corrupt" / REPORT
            report = json.loads(report_path.read_text())
            report["pagination"]["locations"]["reportedTotal"] = 3
            report_path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "pagination"):
                validate_output(root / "corrupt")


if __name__ == "__main__":
    unittest.main()
