"""Offline historical IZIVIA parser and V9 finalization tests."""

import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from v9_rebuild import izivia_official as adapter
from v9_rebuild.orchestrator import read_sources, run_source


def fixture_runner(*, changed_price=False, bad_http=False, fallback=False):
    def run(command, **_):
        spec = importlib.util.spec_from_file_location("izivia_fixture", command[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        grand = ("3,50 €/h 2,50 €/h 1,50 €/h 6 €/h 5 €/h 4 €/h "
                 "0,45 €/kWh 0,40 €/kWh 0,30 €/kWh 0,55 €/kWh 0,50 €/kWh "
                 "+ 0,20 €/min après 45 min 6 € + 0,38 €/kWh après 20 kWh "
                 "5 € + 0,38 €/kWh après 20 kWh 4 € + 0,38 €/kWh après 20 kWh")
        pages = {
            "fast": "IZIVIA FAST happy hour de 150 kW à 200 kW à partir de 0,30 € en happy hour",
            "express": "IZIVIA Express tarifs sont fixés entre 0,40 à 0,55 € TTC par kWh jusqu'à 150 kW",
            "grand_lyon": "JS shell" if fallback else grand,
            "grand_lyon_offers": "paynow stationnement n'est pas payant ni limité dans le temps",
            "pass": "sans abonnement 15 € TTC le Pass IZIVIA",
            "roaming_fee": "frais de service de 15 %",
            "paynow": "paynow",
        }
        if changed_price:
            pages["fast"] = pages["fast"].replace("0,30 €", "0,31 €")
        def fetch(url):
            key = next(k for k, v in module.SOURCES.items() if v == url)
            return (503 if bad_http and key == "express" else 200), pages[key]
        previous = sys.argv
        try:
            sys.argv = command[1:]
            with patch.object(module, "fetch", side_effect=fetch), \
                 patch.object(module, "fetch_rendered", return_value=grand), \
                 redirect_stdout(io.StringIO()):
                module.main()
        except RuntimeError:
            return subprocess.CompletedProcess(command, 1)
        finally:
            sys.argv = previous
        return subprocess.CompletedProcess(command, 0)
    return run


class IziviaOfficialTests(unittest.TestCase):
    def test_historical_price_families_and_browser_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            adapter.run(base / "direct", runner=fixture_runner())
            payload = adapter.validate_output(base / "direct")
            self.assertEqual(payload["operatorDirectNetworks"][0]["pricing"]["happyHourFloorEurPerKwh"], 0.30)
            self.assertFalse(payload["mobilityProvider"]["operatorDirect"])
            adapter.run(base / "fallback", runner=fixture_runner(fallback=True))
            self.assertTrue(adapter.validate_output(base / "fallback")["sourceEvidence"]["dynamicBrowserFallbackUsed"])
            source = next(s for s in read_sources() if s["id"] == "FR:izivia_official")
            def process(command, **_):
                adapter.run(Path(command[-1]), runner=fixture_runner())
                return subprocess.CompletedProcess(command, 0)
            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_http_and_unarchived_price_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "failed"):
                adapter.run(base / "http", runner=fixture_runner(bad_http=True))
            self.assertFalse((base / "http" / adapter.OUTPUT).exists())
            with self.assertRaisesRegex(ValueError, "contract"):
                adapter.run(base / "new_price", runner=fixture_runner(changed_price=True))


if __name__ == "__main__":
    unittest.main()
