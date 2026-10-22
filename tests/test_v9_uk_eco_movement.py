"""Offline archived inline PCPR collector and fail-closed V9 staging."""

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
from v9_rebuild.uk_eco_movement import COLLECTION, RAW, STAGED, STAGING, run, validate_output


def fixture_location(number, public=False):
    location = {"id": f"uk-{number}", "country": "GB", "publish": public,
                "operator": {"name": "ChargePoint"},
                "coordinates": {"latitude": 51.5, "longitude": -0.1}, "evses": []}
    if public:
        location["evses"] = [{"uid": "evse-1001", "evse_id": "GB*CPI*E1001", "status": "AVAILABLE",
                              "connectors": [{"id": "connector-1001", "tariff_ids": ["tariff-1"]}]}]
    return location


TARIFF = {"id": "tariff-1", "currency": "GBP", "elements": [{"price_components": [
    {"type": "ENERGY", "price": 0.4, "vat": 20, "step_size": 1}]}]}


class Reply(io.BytesIO):
    status = 200
    headers = {}


class OfflineRunner:
    def __init__(self, fail_second_page=False, fail=False):
        self.fail_second_page = fail_second_page
        self.fail = fail

    def __call__(self, command, **kwargs):
        if self.fail:
            return SimpleNamespace(returncode=2)

        def urlopen(request, **_):
            url = request.full_url
            endpoint = urlparse(url).path.rsplit("/", 1)[-1]
            offset = int(parse_qs(urlparse(url).query).get("offset", ["0"])[0])
            if endpoint == "locations":
                if offset == 1000 and self.fail_second_page:
                    raise RuntimeError("fixture interrupted second page")
                rows = [fixture_location(i) for i in range(1, 1001)] if offset == 0 else [fixture_location(1001, True)]
            elif endpoint == "tariffs":
                rows = [TARIFF]
            elif endpoint == "statuses":
                rows = [{"id": "status-1"}]
            else:
                raise AssertionError(f"Unexpected preserved route: {url}")
            return Reply(json.dumps({"data": rows}).encode())

        old = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            with patch.dict(os.environ, {"ECO_MOVEMENT_PCPR_TOKEN": "fixture-token"}), \
                 patch("urllib.request.urlopen", side_effect=urlopen), \
                 patch("time.sleep"), patch.object(sys, "argv", command[1:]), patch("builtins.print"):
                try:
                    runpy.run_path(command[1], run_name="__main__")
                except RuntimeError:
                    return SimpleNamespace(returncode=2)
        finally:
            os.chdir(old)
        return SimpleNamespace(returncode=0)


class EcoMovementMigrationTests(unittest.TestCase):
    def test_inline_method_two_pages_and_orchestration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "direct", runner=OfflineRunner())
            staged = validate_output(root / "direct")
            self.assertEqual(len(staged["sources"][0]["locations"]), 1)
            report = json.loads((root / "direct" / STAGING).read_text())
            self.assertFalse(report["readyForTariffRanking"])
            self.assertEqual(report["sourceLocations"], 1001)
            spec = next(row for row in read_sources() if row["id"] == "GB:eco_movement_pcpr")

            def simulated_process(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), runner=OfflineRunner())
                return SimpleNamespace(returncode=0)

            with patch.dict(os.environ, {"ECO_MOVEMENT_PCPR_TOKEN": "fixture-token"}):
                result = run_source(spec, root / "artifacts", runner=simulated_process)
            self.assertEqual(result["status"], "ok")

    def test_interrupted_page_and_corrupt_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, "Historical Eco-Movement"):
                run(root / "incomplete", runner=OfflineRunner(fail_second_page=True))
            with self.assertRaisesRegex(RuntimeError, "Historical Eco-Movement"):
                run(root / "failed", runner=OfflineRunner(fail=True))
            run(root / "corrupt", runner=OfflineRunner())
            path = root / "corrupt" / STAGING
            report = json.loads(path.read_text())
            report["readyForTariffRanking"] = True
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "fail-closed"):
                validate_output(root / "corrupt")
            path.write_text(json.dumps({**report, "readyForTariffRanking": False}))
            collection = root / "corrupt" / COLLECTION
            snapshot = json.loads(collection.read_text())
            snapshot["fixtureSecretEcho"] = "fixture-token"
            collection.write_text(json.dumps(snapshot))
            with patch.dict(os.environ, {"ECO_MOVEMENT_PCPR_TOKEN": "fixture-token"}):
                with self.assertRaisesRegex(ValueError, "credential"):
                    validate_output(root / "corrupt")
            (root / "corrupt" / STAGED).write_bytes(b"broken")
            with self.assertRaises(OSError):
                validate_output(root / "corrupt")


if __name__ == "__main__":
    unittest.main()
