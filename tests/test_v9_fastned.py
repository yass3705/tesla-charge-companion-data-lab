"""Offline execution of the preserved Fastned FR and GB inventory scripts."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.electroverse import ROOT
from v9_rebuild.fastned import FILES, run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
import fastned_station_inventory as fr  # noqa: E402
import fastned_station_inventory_uk as gb  # noqa: E402
from tests.test_fastned_station_inventory import FR_HTML, TARIFF_TEXT  # noqa: E402


FR_PAGE = "https://www.fastnedcharging.com/fr/emplacements/aire-de-test"
GB_PAGE = "https://www.fastnedcharging.com/en/locations/united-kingdom/test-site"
GB_TARIFF = "£0.79 in the United Kingdom £0.55 (£0.55 per kWh in the United Kingdom) get 10% off save 30% £4.99 per month until 31 October 2026"
GB_HTML = """<html><body><h1>Test UK</h1><div>Address Test Road, United Kingdom Opening times 24/7
Number of charging spots 8 Type of Connectors CCS, CHADEMO Maximum power up to 400 kW
Starting from GBP 0.55/kWh standard rate: 0.79/kWh</div>
<a href="https://www.google.com/maps/dir/?api=1&amp;destination=52.0%2C-1.0">Directions</a></body></html>"""
GB_SITEMAP = f'<urlset><url><loc>{GB_PAGE}</loc></url></urlset>'


class OfflineFastnedRunner:
    def __init__(self, fail_country: str | None = None):
        self.fail_country = fail_country
        self.seen = []

    def __call__(self, command, **kwargs):
        country = "GB" if Path(command[1]).name.endswith("_uk.py") else "FR"
        self.seen.append(country)
        if country == self.fail_country:
            return SimpleNamespace(returncode=2)
        if country == "FR":
            with patch.object(fr, "fetch_text", side_effect=lambda url: TARIFF_TEXT if url == fr.TARIFF_URL else FR_HTML), \
                 patch.object(fr, "discover_location_urls", return_value=(fr.SITEMAP_CANDIDATES[0], [FR_PAGE], 1)), \
                 patch.object(sys, "argv", command[1:]), patch("builtins.print"):
                fr.main()
        else:
            prior = Path.cwd()
            try:
                os.chdir(kwargs["cwd"])
                def fetch(url, tries=4):
                    if url == gb.TARIFF_URL:
                        return GB_TARIFF
                    if url in gb.SITEMAPS:
                        return GB_SITEMAP
                    if url == GB_PAGE:
                        return GB_HTML
                    raise AssertionError(url)
                with patch.object(gb, "fetch", side_effect=fetch), patch("builtins.print"):
                    gb.main()
            finally:
                os.chdir(prior)
        return SimpleNamespace(returncode=0)


class FastnedFamilyTests(unittest.TestCase):
    def test_both_historical_scripts_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = OfflineFastnedRunner()
            run(root / "source", runner=runner)
            self.assertEqual(runner.seen, ["FR", "GB"])
            result = validate_output(root / "source")
            self.assertEqual(result["FR"]["counts"]["franceLocationCount"], 1)
            self.assertEqual(result["GB"]["counts"]["ukLocationCount"], 1)
            spec = next(row for row in read_sources() if row["id"] == "FR:fastned_inventory_family")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), runner=OfflineFastnedRunner())
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 3)

    def test_failed_second_script_does_not_finalize_family(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "partial"
            with self.assertRaisesRegex(RuntimeError, "GB inventory failed"):
                run(out, runner=OfflineFastnedRunner(fail_country="GB"))
            self.assertTrue((out / FILES["FR"]).is_file())
            self.assertFalse((out / FILES["GB"]).exists())


if __name__ == "__main__":
    unittest.main()
