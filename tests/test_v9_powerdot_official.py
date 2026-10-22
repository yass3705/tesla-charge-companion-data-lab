"""Offline preserved Powerdot CPO/eMSP classification and CSV schema gates."""

import csv
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

from tests.test_powerdot_electroverse_subscriptions import PAGE
from v9_rebuild import powerdot_official
from v9_rebuild.orchestrator import read_sources, run_source


def fixture_runner(*, empty=False, bad_schema=False, changed_discount=False, http_error=False):
    def run(command, **kwargs):
        spec = importlib.util.spec_from_file_location("powerdot_fixture", command[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        archive = json.loads((powerdot_official.ROOT / powerdot_official.OUTPUT).read_text())
        buffer = io.StringIO()
        fields = ["id_pdc_itinerance", "nom_station", "adresse_station", "ville", "puissance_nominale"]
        if bad_schema:
            fields = ["unrelated"]
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        if not empty and not bad_schema:
            for row in archive["inventory"]["samples"]:
                writer.writerow({"id_pdc_itinerance": row.get("evseId"), "nom_station": row.get("stationName"),
                                 "adresse_station": row.get("address"), "ville": row.get("city"),
                                 "puissance_nominale": row.get("powerKwObserved")})
        pages = {
            module.SOURCES["faq"]: "Miio Chargemap Electromaps",
            module.SOURCES["driver"]: "Scan the QR code on the charger. 300+ mobility platforms",
            module.SOURCES["electroverseSubscription"]: PAGE.replace("France : 22 %", "France : 28 %") if changed_discount else PAGE,
            module.SOURCES["powerdotInventoryCsv"]: buffer.getvalue(),
        }
        def fetch(url):
            return (503 if http_error and url == module.SOURCES["faq"] else 200), pages[url]
        prior = sys.argv
        try:
            sys.argv = command[1:]
            with patch.object(module, "fetch", side_effect=fetch), redirect_stdout(io.StringIO()):
                module.main()
        except RuntimeError:
            return subprocess.CompletedProcess(command, 1)
        finally:
            sys.argv = prior
        return subprocess.CompletedProcess(command, 0)
    return run


class PowerdotOfficialTests(unittest.TestCase):
    def test_archived_cpo_emsp_rules_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            powerdot_official.run(base / "direct", runner=fixture_runner())
            payload = powerdot_official.validate_output(base / "direct")
            self.assertIsNone(payload["operatorDirect"]["adHocQr"]["nationalEurPerKwh"])
            self.assertFalse(payload["mobilityProviders"]["electroversePowerdotSubscription"]["operatorDirect"])
            source = next(row for row in read_sources() if row["id"] == "FR:powerdot_official")
            def process(command, **_):
                powerdot_official.run(Path(command[-1]), runner=fixture_runner())
                return subprocess.CompletedProcess(command, 0)
            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_zero_rows_allowed_but_schema_and_http_errors_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            powerdot_official.run(base / "empty", runner=fixture_runner(empty=True))
            self.assertEqual(powerdot_official.validate_output(base / "empty")["inventory"]["rowCount"], 0)
            with self.assertRaisesRegex(RuntimeError, "failed"):
                powerdot_official.run(base / "schema", runner=fixture_runner(bad_schema=True))
            with self.assertRaisesRegex(RuntimeError, "failed"):
                powerdot_official.run(base / "http", runner=fixture_runner(http_error=True))

    def test_new_discount_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "channel"):
                powerdot_official.run(Path(tmp), runner=fixture_runner(changed_discount=True))


if __name__ == "__main__":
    unittest.main()
