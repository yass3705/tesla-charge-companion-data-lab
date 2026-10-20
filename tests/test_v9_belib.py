"""Offline checks for the preserved Belib tariff and station methods."""

import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.belib import DIAGNOSTIC, ROOT, STATIONS, SUMMARY, TARIFF, run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
from tests.test_belib_station_base import row  # noqa: E402
import belib_official  # noqa: E402


class BelibMigrationTests(unittest.TestCase):
    def test_official_historical_parser_on_archived_values_without_network(self):
        amounts = "0.33 0.22 0.57 2.30 0.42 0.17 0.37 2.00 0.38 0.25 10.0 14.0 5.70 15.0"
        with tempfile.TemporaryDirectory() as temp:
            original = Path.cwd()
            try:
                os.chdir(temp)
                with patch.object(sys, "argv", ["belib_official.py", "--out", "out/belib"]), \
                     patch.object(belib_official, "optional_html_text", side_effect=[
                         (200, amounts + " 7,00 € / an 20h - 23h 23h - 08h"),
                         (200, "carte bancaire directement sur le totem qr code disponible sur la borne 1,49 € pré-autorisation"),
                         (200, "temps branché = temps facturé")]), \
                     patch.object(belib_official, "pdf_text_and_sha", side_effect=[
                         (200, amounts + " 2 juin 2025", "a" * 64),
                         (200, amounts + " 2 juin 2025", "b" * 64)]), \
                     patch.object(belib_official, "json_get", side_effect=[
                         (200, {"total_count": 1, "results": [row()]}),
                         (200, {"total_count": 1, "results": [{"statut_pdc": "Disponible"}]})]):
                    with patch("builtins.print"):
                        belib_official.main()
                result = json.loads(Path("out/belib/belib_official_paris.json").read_text())
                self.assertEqual(result["dataset"], "belib-official-paris")
                self.assertEqual(result["inventory"]["staticPointCountObserved"], 1)
            finally:
                os.chdir(original)

    def test_chain_transmits_tariff_to_real_station_builder_and_rejects_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture = base / "static.json"
            fixture.write_text(json.dumps([row()]), encoding="utf-8")
            out = base / "validated"
            def offline_runner(command, **kwargs):
                if Path(command[1]).name == "belib_official.py":
                    candidate = Path(kwargs["cwd"]) / "out/belib"
                    candidate.mkdir(parents=True)
                    shutil.copy2(ROOT / TARIFF, candidate / "belib_official_paris.json")
                    (candidate / "SUMMARY.md").write_text("Archived Belib technical summary\n", encoding="utf-8")
                    return SimpleNamespace(returncode=0)
                return subprocess.run(command, **kwargs)
            run(out, static_input=fixture, runner=offline_runner)
            checked = validate_output(out)
            self.assertEqual(checked["stations"]["stats"]["stationCount"], 1)
            self.assertEqual(checked["stations"]["stats"]["chargePointCount"], 1)
            self.assertTrue((out / SUMMARY).is_file())
            self.assertEqual(checked["stations"]["source"]["sha256"], hashlib.sha256(fixture.read_bytes()).hexdigest())
            self.assertEqual(checked["tariff"]["sourceEvidence"]["officialOnly"], True)
            spec = next(item for item in read_sources() if item["id"] == "FR:belib")
            def orchestrator_runner(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), static_input=fixture, runner=offline_runner)
                return SimpleNamespace(returncode=0)
            result = run_source(spec, base / "artifacts", runner=orchestrator_runner)
            self.assertEqual(result["status"], "ok")
            self.assertTrue((base / "artifacts" / result["artifact"]).is_file())
            retry_root = base / "retry"
            retry_input = retry_root / "input_state"
            shutil.copytree(base / "artifacts" / "objects", retry_input / "objects")
            (retry_input / "manifest.json").write_text(json.dumps({"schema_version": 1, "status": "complete", "sources": [result]}), encoding="utf-8")
            prior_sources = []
            def retry_runner(command, **kwargs):
                prior_sources.append(Path(command[command.index("--source") + 1]))
                run(Path(command[command.index("--out") + 1]), source=prior_sources[-1], static_input=fixture, runner=offline_runner)
                return SimpleNamespace(returncode=0)
            retried = run_source(spec, retry_root, runner=retry_runner)
            self.assertEqual(retried["status"], "ok")
            self.assertEqual(len(prior_sources), 1)
            self.assertTrue((prior_sources[0] / TARIFF).is_file())
            (prior_sources[0] / TARIFF).write_text("{}", encoding="utf-8")
            self.assertEqual(run_source(spec, retry_root, runner=retry_runner)["reason"], "validated_dependency_invalid")
            def fail_official(command, **kwargs):
                return SimpleNamespace(returncode=2)
            with self.assertRaisesRegex(RuntimeError, "official extraction failed"):
                run(base / "failed", static_input=fixture, runner=fail_official)
            self.assertFalse((base / "failed" / STATIONS).exists())
            self.assertEqual(json.loads((base / "failed" / DIAGNOSTIC).read_text())["stage"], "official_tariff")
            def failed_outer(command, **kwargs):
                target = Path(command[command.index("--out") + 1]) / DIAGNOSTIC
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps({"dataset": "belib-extraction-diagnostic", "sanitized": True, "stage": "official_tariff"}))
                return SimpleNamespace(returncode=2)
            failure_root = base / "failed-artifacts"
            self.assertEqual(run_source(spec, failure_root, attempts=1, runner=failed_outer)["status"], "failed")
            self.assertTrue((failure_root / "failures/FR_belib/latest_diagnostic.json").is_file())


if __name__ == "__main__":
    unittest.main()
