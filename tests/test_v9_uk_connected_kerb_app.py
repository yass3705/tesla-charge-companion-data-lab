"""Offline guest app, exact QR joins, signed dependency and recovery."""

import io
import json
import os
import runpy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from tests.test_v9_uk_connected_kerb_operator import OfflineRunner as OperatorRunner
from v9_rebuild.orchestrator import read_sources, run_batch, run_source
from v9_rebuild.uk_connected_kerb_app import run, validate_app_output
from v9_rebuild.uk_connected_kerb_operator import run as run_operator


class AppRunner:
    def __init__(self, missing=None, fail=False):
        self.missing = set(missing or [])
        self.fail = fail

    def __call__(self, command, **kwargs):
        if self.fail:
            return SimpleNamespace(returncode=2)

        def urlopen(request, **_):
            url = request.full_url
            if url.endswith("/login/guest"):
                body = {"accessToken": "fixture-access-token"}
            elif "/locations/search?" in url:
                qr = parse_qs(urlparse(url).query)["qrCode"][0]
                body = {"locations": [] if qr in self.missing else [{
                    "id": f"app-{qr}", "latitude": 51.5, "longitude": -0.1,
                    "sockets": [{"qrCode": qr}]}]}
            elif "/locations/app-" in url:
                qr = url.rsplit("app-", 1)[-1]
                body = {"id": f"app-{qr}", "latitude": 51.5, "longitude": -0.1,
                        "accessType": "PUBLIC", "sockets": [{"qrCode": qr, "id": f"socket-{qr}",
                        "fullTariffSpecification": [{"id": f"tariff-app-{qr}", "tariffOption": "REGULAR"}],
                        "unifiedTariffs": [{"id": f"tariff-app-{qr}", "slices": {"ENERGY": [
                            {"price": 0.48, "minDuration": 0, "stepSize": 1}]}}]}]}
            else:
                raise AssertionError(f"Unexpected guest route: {url}")
            return io.BytesIO(json.dumps(body).encode())

        with patch("urllib.request.urlopen", side_effect=urlopen), \
             patch.object(sys, "argv", command[1:]), patch("builtins.print"):
            runpy.run_path(command[1], run_name="__main__")
        return SimpleNamespace(returncode=0)


def operator_bundle(base: Path) -> Path:
    dependency = base / "operator-bundle"
    spec = next(row for row in read_sources() if row["id"] == "GB:connected_kerb_operator")
    def simulated_process(command, **kwargs):
        run_operator(Path(command[command.index("--out") + 1]), runner=OperatorRunner())
        return SimpleNamespace(returncode=0)

    with patch.dict(os.environ, {"CONNECTED_KERB_TOKEN": "fixture-token"}):
        manifest = run_batch([spec], dependency, workers=1, runner=simulated_process)
    assert manifest["status"] == "complete"
    return dependency


class ConnectedKerbAppTests(unittest.TestCase):
    def test_exact_guest_and_orchestration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dep = operator_bundle(root)
            # The artifact path is nested under one immutable content-addressed object.
            operator_state = dep / Path(*Path(json.loads((dep / "manifest.json").read_text())["sources"][0]["artifact"]).parts[:3])
            run(root / "direct", operator_state, runner=AppRunner())
            report = validate_app_output(root / "direct")
            self.assertEqual(report["resolvedConnectors"], 2)
            self.assertFalse(json.loads((root / "direct/docs/connected-kerb-uk-integration-2026-10-07.json").read_text())["publishedToV9"])
            artifacts = root / "artifacts"
            shutil.copytree(dep, artifacts / "input_dependencies/GB_connected_kerb_operator")
            spec = next(row for row in read_sources() if row["id"] == "GB:connected_kerb_app")

            def simulated_process(command, **kwargs):
                run(Path(command[command.index("--out") + 1]),
                    Path(command[command.index("--operator-state") + 1]), runner=AppRunner())
                return SimpleNamespace(returncode=0)

            result = run_source(spec, artifacts, runner=simulated_process)
            self.assertEqual(result["status"], "ok")

    def test_partial_and_missing_prices_are_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dep = operator_bundle(root)
            relative = Path(json.loads((dep / "manifest.json").read_text())["sources"][0]["artifact"])
            operator_state = dep / Path(*relative.parts[:3])
            run(root / "partial", operator_state, runner=AppRunner(missing={"1002"}))
            report = validate_app_output(root / "partial")
            self.assertEqual((report["resolvedConnectors"], report["unresolvedConnectors"]), (1, 1))
            run(root / "no_price", operator_state, runner=AppRunner(missing={"1001", "1002"}))
            report = validate_app_output(root / "no_price")
            self.assertEqual((report["resolvedConnectors"], report["unresolvedConnectors"]), (0, 2))

    def test_missing_bad_sha_and_failed_guest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dep = operator_bundle(root)
            spec = next(row for row in read_sources() if row["id"] == "GB:connected_kerb_app")
            missing = run_source(spec, root / "missing")
            self.assertEqual(missing["reason"], "validated_dependency_missing")
            bundle = root / "bad/input_dependencies/GB_connected_kerb_operator"
            shutil.copytree(dep, bundle)
            manifest = json.loads((bundle / "manifest.json").read_text())
            artifact = bundle / manifest["sources"][0]["artifact"]
            artifact.write_bytes(b"corrupt")
            bad = run_source(spec, root / "bad")
            self.assertEqual(bad["reason"], "validated_dependency_invalid")
            relative = Path(json.loads((dep / "manifest.json").read_text())["sources"][0]["artifact"])
            operator_state = dep / Path(*relative.parts[:3])
            with self.assertRaisesRegex(RuntimeError, "Historical Connected Kerb"):
                run(root / "failed", operator_state, runner=AppRunner(fail=True))


if __name__ == "__main__":
    unittest.main()
