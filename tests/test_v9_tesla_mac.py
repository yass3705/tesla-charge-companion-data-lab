"""Offline immutable Tesla/Mac ingress without changing Updater Test acquisition."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import import_tesla_mac_ingress as historical
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source
from v9_rebuild.tesla_mac import CATALOGUE, MANIFEST, run, validate_output

FIRST = ROOT / "data/tesla/mac/history/c37e7717d4a19036b49e6c129c2bd00485b900f6.json"


def ready(raw, run_id=1):
    rows = json.loads(raw)
    return {"schemaVersion": 1, "status": "ready",
            "sourceRepository": historical.INGRESS, "cataloguePath": historical.INGRESS_PATH,
            "catalogueCommit": "a" * 40, "catalogueSha256": hashlib.sha256(raw).hexdigest(),
            "catalogueBytes": len(raw), "stationCount": len(rows),
            "sourcePublishedAt": "2026-10-20T12:00:00Z", "lot": "historical-fixture",
            "updaterRunId": run_id,
            "countryDates": {code: "2026-10-20" for code in {row["countryCode"] for row in rows}},
            "countriesUpdated": ["FR"], "provenance": "historical Mac bytes"}


class OfflineRunner:
    def __call__(self, command, **kwargs):
        try:
            with patch.object(sys, "argv", command[1:]), patch("builtins.print"):
                historical.main()
        except (ValueError, OSError):
            return SimpleNamespace(returncode=2)
        return SimpleNamespace(returncode=0)


class TeslaMacMigrationTests(unittest.TestCase):
    def test_historical_catalogue_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = FIRST.read_bytes()
            candidate = root / "candidate.json"
            candidate.write_bytes(raw)
            pin = root / "ready.json"
            pin.write_text(json.dumps(ready(raw)), encoding="utf-8")
            run(root / "source", ready_file=pin, catalogue_file=candidate, runner=OfflineRunner())
            manifest = validate_output(root / "source")
            self.assertEqual(manifest["catalogueSha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(manifest["stationCount"], len(json.loads(raw)))
            spec = next(row for row in read_sources() if row["id"] == "GL:tesla_mac")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), ready_file=pin,
                    catalogue_file=candidate, runner=OfflineRunner())
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)

    def test_bad_sha_does_not_replace_last_good(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = FIRST.read_bytes()
            candidate = root / "candidate.json"
            candidate.write_bytes(raw)
            pin = ready(raw)
            pin["catalogueSha256"] = "0" * 64
            ready_file = root / "ready.json"
            ready_file.write_text(json.dumps(pin), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Historical Tesla/Mac ingress import failed"):
                run(root / "source", ready_file=ready_file, catalogue_file=candidate, runner=OfflineRunner())
            self.assertEqual((root / "source" / CATALOGUE).read_bytes(), (ROOT / CATALOGUE).read_bytes())
            self.assertEqual((root / "source" / MANIFEST).read_bytes(), (ROOT / MANIFEST).read_bytes())

    def test_resume_from_previous_validated_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = FIRST.read_bytes()
            second = (ROOT / CATALOGUE).read_bytes()
            first_file = root / "first.json"
            second_file = root / "second.json"
            first_file.write_bytes(first)
            second_file.write_bytes(second)
            first_pin = root / "first-ready.json"
            second_pin = root / "second-ready.json"
            first_pin.write_text(json.dumps(ready(first, 1)), encoding="utf-8")
            second_pin.write_text(json.dumps(ready(second, 2)), encoding="utf-8")
            run(root / "first-state", ready_file=first_pin, catalogue_file=first_file, runner=OfflineRunner())
            run(root / "second-state", source=root / "first-state", ready_file=second_pin,
                catalogue_file=second_file, runner=OfflineRunner())
            self.assertEqual(validate_output(root / "second-state")["catalogueSha256"], hashlib.sha256(second).hexdigest())


if __name__ == "__main__":
    unittest.main()
