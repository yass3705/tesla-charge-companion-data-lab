"""Offline FR/IT/DE/GB execution of the existing IONITY Direct scripts."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.electroverse import ROOT
from v9_rebuild.ionity import output_path, run, validate_country, validate_output
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
import ionity_station_tariffs as eu  # noqa: E402
import ionity_station_tariffs_uk as uk  # noqa: E402


GEO = {"FR": (48, 2), "IT": (42, 12), "DE": (50, 8), "GB": (52, -1)}


def payloads(country: str):
    lat, lon = GEO[country]
    uid = f"archived-fixture-{country.lower()}"
    station = {"uuid": uid, "locationId": uid, "cpoIdentifier": "IONITY_CPO", "latitude": lat, "longitude": lon, "name": "IONITY fixture"}
    detail = {**station, "country": country, "connectors": [{"uuid": f"connector-{country}", "number": 1,
              "physicalReference": "01", "sourceEvseId": f"{country}*ION*E1", "maxPower": 350000, "type": "CCS",
              "adhocPrice": {"name": "IONITY DIRECT", "unit": "kWh", "amount": 0.83 if country == "GB" else 0.62,
                             "currency": "GBP" if country == "GB" else "EUR"}}]}
    return {"locations": [station]}, detail


class OfflineIonityRunner:
    def __init__(self, fail_country: str | None = None):
        self.fail_country = fail_country
        self.seen = []

    def __call__(self, command, **kwargs):
        country = "GB" if Path(command[1]).name.endswith("_uk.py") else command[command.index("--country") + 1]
        self.seen.append(country)
        if country == self.fail_country:
            return SimpleNamespace(returncode=2)
        static, detail = payloads(country)
        request = lambda url: static if url.endswith("/static") else detail
        if country == "GB":
            with patch.object(uk, "request_json", side_effect=request), patch.object(uk, "OUT", Path(kwargs["cwd"]) / output_path("GB")), patch("builtins.print"):
                uk.main()
        else:
            old_country = eu.TARGET_COUNTRY
            try:
                with patch.object(eu, "request_json", side_effect=request), patch.object(sys, "argv", command[1:]), patch("builtins.print"):
                    eu.main()
            finally:
                eu.TARGET_COUNTRY = old_country
        return SimpleNamespace(returncode=0)


class IonityFamilyTests(unittest.TestCase):
    def test_empty_source_is_technical_output_not_volume_rejection(self):
        prior = eu.TARGET_COUNTRY
        try:
            eu.TARGET_COUNTRY = "FR"
            self.assertEqual(eu.make_payload([], [], [])["counts"]["countryLocationCount"], 0)
        finally:
            eu.TARGET_COUNTRY = prior
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            with patch.object(uk, "request_json", return_value={"locations": []}), patch.object(uk, "OUT", out / output_path("GB")), patch("builtins.print"):
                uk.main()
            self.assertEqual(validate_country(out, "GB")["counts"]["ukLocationCount"], 0)

    def test_all_historical_scripts_run_offline_and_publish_together(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            runner = OfflineIonityRunner()
            run(base / "direct", runner=runner)
            self.assertEqual(runner.seen, ["FR", "IT", "DE", "GB"])
            output = validate_output(base / "direct")
            self.assertEqual({c: d["counts"]["ukLocationCount" if c == "GB" else "countryLocationCount"] for c, d in output.items()},
                             {"FR": 1, "IT": 1, "DE": 1, "GB": 1})
            spec = next(row for row in read_sources() if row["id"] == "FR:ionity_direct_family")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), runner=OfflineIonityRunner())
                return SimpleNamespace(returncode=0)
            result = run_source(spec, base / "artifacts", runner=outer)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(len(result["files"]), 4)
            self.assertFalse((ROOT / output_path("FR")).samefile(base / "artifacts" / result["artifact"]))

    def test_failure_keeps_unfinished_family_out_of_validated_objects(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = OfflineIonityRunner(fail_country="IT")
            with self.assertRaisesRegex(RuntimeError, "IT extraction failed"):
                run(root / "partial", runner=runner)
            self.assertTrue((root / "partial" / output_path("FR")).is_file())
            self.assertFalse((root / "partial" / output_path("GB")).exists())
            with self.assertRaises(FileNotFoundError):
                validate_output(root / "partial")


if __name__ == "__main__":
    unittest.main()
