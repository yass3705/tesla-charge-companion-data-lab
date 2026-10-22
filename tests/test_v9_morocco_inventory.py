"""Offline execution of the two archived Moroccan public-map methods."""

import io
import json
import os
import runpy
import tempfile
import unittest
from contextlib import redirect_stdout
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild import morocco_inventory
from v9_rebuild.orchestrator import artifact_digest, read_sources, run_source, sha256


FASTVOLT = {"carte": {"components": [{"chargers": [
    {"charger_id": "FV-1", "charger_name": "A", "geo_coordinates": "33.5,-7.5", "ccs_count": 1},
    {"charger_id": "TEST-2", "charger_name": "Test", "geo_coordinates": "33.5,-7.5", "ccs_count": 1},
]}]}}
KILOWATT = [
    {"id": "KW-1", "name": "A", "location": {"latitude": 33.5, "longitude": -7.5},
     "connectors": [{"type": "CCS", "power": 50}]},
    {"id": "KW-2", "name": "Test", "location": {"latitude": 33.5, "longitude": -7.5},
     "connectors": []},
]


class Response(io.BytesIO):
    status = 200
    headers = {"Content-Type": "application/json"}


def offline_runner(command, **kwargs):
    method = "fastvolt" if "fastvolt" in command[1] else "kilowatt"

    def urlopen(request, **_):
        url = request.full_url
        payload = (FASTVOLT if method == "fastvolt" else
                   {"count": 1} if url.endswith("connectors-count") else KILOWATT)
        return Response(json.dumps(payload).encode())

    old = Path.cwd()
    stdout = io.StringIO()
    try:
        os.chdir(kwargs["cwd"])
        with patch("urllib.request.urlopen", side_effect=urlopen), redirect_stdout(stdout):
            runpy.run_path(command[1], run_name="__main__")
    finally:
        os.chdir(old)
    return SimpleNamespace(returncode=0, stdout=stdout.getvalue())


class MoroccoInventoryTests(unittest.TestCase):
    def test_archived_methods_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for method in morocco_inventory.METHODS:
                with self.subTest(method=method):
                    out = base / method
                    morocco_inventory.run(out, method, runner=offline_runner)
                    report = morocco_inventory.validate_output(out, method)
                    rows = report["chargers" if method == "fastvolt" else "stations"]
                    self.assertEqual([r["production_candidate"] for r in rows], [True, False])
                    self.assertEqual(rows[0]["charger_id" if method == "fastvolt" else "id"],
                                     "FV-1" if method == "fastvolt" else "KW-1")
                    self.assertTrue(all(r["site_brand"] is None for r in rows))
                    spec = next(x for x in read_sources() if x["id"] == f"MA:{method}_inventory")

                    def process(command, **_):
                        morocco_inventory.run(Path(command[command.index("--out") + 1]),
                                              method, runner=offline_runner)
                        return SimpleNamespace(returncode=0)

                    self.assertEqual(run_source(spec, base / f"{method}-artifact", runner=process)["status"], "ok")

    def test_failures_and_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "failure"
            failed = lambda *_args, **_kwargs: SimpleNamespace(returncode=2, stdout="")
            with self.assertRaises(RuntimeError):
                morocco_inventory.run(out, "fastvolt", runner=failed)
            self.assertFalse((out / morocco_inventory.METHODS["fastvolt"][1]).exists())
            morocco_inventory.run(out, "fastvolt", runner=offline_runner)
            path = out / morocco_inventory.METHODS["fastvolt"][1]
            report = json.loads(path.read_text())
            report["summary"]["charger_count"] = 999
            path.write_text(json.dumps(report))
            with self.assertRaises(ValueError):
                morocco_inventory.validate_output(out, "fastvolt")

    def test_signed_kilowatt_reconciliation_is_diagnostic(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            stage = base / "inventory-stage"
            morocco_inventory.run(stage, "kilowatt", runner=offline_runner)
            digest, files = artifact_digest(stage)
            bundle = base / "bundle"
            state = bundle / "objects/MA_kilowatt_inventory" / digest
            state.parent.mkdir(parents=True)
            shutil.copytree(stage, state)
            artifact = state / morocco_inventory.METHODS["kilowatt"][1]
            (bundle / "manifest.json").write_text(json.dumps({"schema_version": 1,
                "status": "complete", "sources": [{"source": "MA:kilowatt_inventory",
                "module": "morocco_inventory", "status": "ok",
                "artifact": str(artifact.relative_to(bundle)), "sha256": sha256(artifact),
                "artifact_set_sha256": digest, "files": files}]}))

            # The historical diagnostic script does not access the network.
            def diagnostic_runner(command, **kwargs):
                old = Path.cwd()
                try:
                    os.chdir(kwargs["cwd"])
                    with redirect_stdout(io.StringIO()):
                        runpy.run_path(command[1], run_name="__main__")
                finally:
                    os.chdir(old)
                return SimpleNamespace(returncode=0, stdout="")

            def process(command, **_):
                morocco_inventory.reconcile(Path(command[command.index("--out") + 1]),
                                             Path(command[command.index("--source") + 1]),
                                             runner=diagnostic_runner)
                return SimpleNamespace(returncode=0)

            spec = next(x for x in read_sources() if x["id"] == "MA:kilowatt_reconcile")
            artifacts = base / "artifacts"
            shutil.copytree(bundle, artifacts / "input_dependencies/MA_kilowatt_inventory")
            result = run_source(spec, artifacts, runner=process)
            self.assertEqual(result["status"], "ok", result)
            report = morocco_inventory.validate_reconciliation(
                next((artifacts / "objects/MA_kilowatt_reconcile").iterdir()))
            self.assertTrue(report["policy"]["no_production_merges_applied"])
            self.assertEqual(report["summary"]["production_station_records"], 1)
            self.assertEqual(run_source(spec, base / "missing")["reason"], "validated_dependency_missing")
            bad = base / "bad/input_dependencies/MA_kilowatt_inventory"
            shutil.copytree(bundle, bad)
            (bad / json.loads((bad / "manifest.json").read_text())["sources"][0]["artifact"]).write_bytes(b"bad")
            self.assertEqual(run_source(spec, base / "bad")["reason"], "validated_dependency_invalid")

    def test_kilowatt_tariff_overlay_preserves_free_evidence_and_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            stage = base / "inventory-stage"
            morocco_inventory.run(stage, "kilowatt", runner=offline_runner)
            input_path = stage / morocco_inventory.METHODS["kilowatt"][1]
            source = json.loads(input_path.read_text())
            source["stations"][0]["name"] = "Al Mazar Mall"
            unknown = dict(source["stations"][0], id="KW-UNKNOWN", name="Unknown site")
            source["stations"].append(unknown)
            source["summary"].update(raw_station_records=3, production_candidates=2)
            input_path.write_text(json.dumps(source))
            morocco_inventory.validate_output(stage, "kilowatt")
            digest, files = artifact_digest(stage)
            bundle = base / "bundle"
            state = bundle / "objects/MA_kilowatt_inventory" / digest
            state.parent.mkdir(parents=True)
            shutil.copytree(stage, state)
            artifact = state / morocco_inventory.METHODS["kilowatt"][1]
            (bundle / "manifest.json").write_text(json.dumps({"schema_version": 1,
                "status": "complete", "sources": [{"source": "MA:kilowatt_inventory",
                "module": "morocco_inventory", "status": "ok",
                "artifact": str(artifact.relative_to(bundle)), "sha256": sha256(artifact),
                "artifact_set_sha256": digest, "files": files}]}))

            def historical_runner(command, **kwargs):
                old = Path.cwd()
                try:
                    os.chdir(kwargs["cwd"])
                    with redirect_stdout(io.StringIO()):
                        runpy.run_path(command[1], run_name="__main__")
                finally:
                    os.chdir(old)
                return SimpleNamespace(returncode=0, stdout="")

            def process(command, **_):
                morocco_inventory.build_tariff_overlay(
                    Path(command[command.index("--out") + 1]),
                    Path(command[command.index("--source") + 1]), runner=historical_runner)
                return SimpleNamespace(returncode=0)

            spec = next(x for x in read_sources() if x["id"] == "MA:kilowatt_tariff_overlay")
            artifacts = base / "artifacts"
            shutil.copytree(bundle, artifacts / "input_dependencies/MA_kilowatt_inventory")
            result = run_source(spec, artifacts, runner=process)
            self.assertEqual(result["status"], "ok", result)
            output = next((artifacts / "objects/MA_kilowatt_tariff_overlay").iterdir())
            report = morocco_inventory.validate_tariff_overlay(output)
            rows = {row["station_id"]: row for row in report["stations"]}
            self.assertEqual(rows["KW-1"]["tariff_mad"], 0)
            self.assertTrue(rows["KW-1"]["tariff_evidence_rule"])
            self.assertIsNone(rows["KW-UNKNOWN"]["tariff_mad"])
            self.assertFalse(rows["KW-UNKNOWN"]["tariff_production_eligible"])
            self.assertEqual(run_source(spec, base / "missing")["reason"], "validated_dependency_missing")
            bad = base / "bad/input_dependencies/MA_kilowatt_inventory"
            shutil.copytree(bundle, bad)
            (bad / json.loads((bad / "manifest.json").read_text())["sources"][0]["artifact"]).write_bytes(b"bad")
            self.assertEqual(run_source(spec, base / "bad")["reason"], "validated_dependency_invalid")
            rows["KW-UNKNOWN"]["tariff_mad"] = 0
            (output / morocco_inventory.TARIFF_OVERLAY[1]).write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "unresolved tariff"):
                morocco_inventory.validate_tariff_overlay(output)


if __name__ == "__main__":
    unittest.main()
