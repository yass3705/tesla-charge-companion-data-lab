"""Offline France watch fixture uses only archived tariff values."""

import hashlib
import io
import json
import os
import runpy
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from v9_rebuild import france_fixed_watch
from v9_rebuild.orchestrator import read_sources, run_source


PAGES = {"dream-energy.fr": "recharge coûte 0,59 €/kWh",
         "soregies.fr": "Sorégies Mobilités tarif",
         "mobive.fr": "Mobive abonné non abonné"}


def seed_files(base: Path):
    seeds = {}
    for relative in france_fixed_watch.DATA:
        data = json.loads((france_fixed_watch.ROOT / relative).read_text())
        if "soregies" in relative.name:
            data["refresh"]["semanticTariffContextSha256"] = hashlib.sha256(PAGES["soregies.fr"].lower().encode()).hexdigest()
        if "mobive" in relative.name:
            data["refresh"]["semanticTariffContextSha256"] = hashlib.sha256(PAGES["mobive.fr"].lower().encode()).hexdigest()
        path = base / relative.name
        path.write_text(json.dumps(data))
        seeds[relative] = path
    return seeds


def runner(command, **kwargs):
    def urlopen(request, **_):
        page = next(body for domain, body in PAGES.items() if domain in request.full_url)
        return io.BytesIO(page.encode())
    old = Path.cwd()
    try:
        os.chdir(kwargs["cwd"])
        with patch("urllib.request.urlopen", side_effect=urlopen), redirect_stdout(io.StringIO()):
            try:
                runpy.run_path(command[1], run_name="__main__")
                code = 0
            except SystemExit as error:
                code = int(error.code)
    finally:
        os.chdir(old)
    return subprocess.CompletedProcess(command, code)


class FranceFixedWatchTests(unittest.TestCase):
    def test_historical_watch_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seeds = seed_files(base)
            france_fixed_watch.run(base / "direct", seeds=seeds, runner=runner)
            report = france_fixed_watch.validate_output(base / "direct", seeds)
            self.assertEqual([row["status"] for row in report["results"]], ["unchanged"] * 3)
            source = next(row for row in read_sources() if row["id"] == "FR:fixed_tariff_watch")

            def process(command, **_):
                france_fixed_watch.run(Path(command[-1]), seeds=seeds, runner=runner)
                return subprocess.CompletedProcess(command, 0)

            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_changed_source_and_price_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seeds = seed_files(base)
            sor = next(key for key in seeds if "soregies" in key.name)
            data = json.loads(seeds[sor].read_text())
            data["refresh"]["semanticTariffContextSha256"] = "0" * 64
            seeds[sor].write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "source or price review"):
                france_fixed_watch.run(base / "changed", seeds=seeds, runner=runner)
            seeds = seed_files(base)
            france_fixed_watch.run(base / "valid", seeds=seeds, runner=runner)
            dream = next(key for key in seeds if "dream_energy" in key.name)
            path = base / "valid" / dream
            data = json.loads(path.read_text())
            data["directTariff"]["eurPerKwh"] = 8.88
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "altered archived tariff"):
                france_fixed_watch.validate_output(base / "valid", seeds)


if __name__ == "__main__":
    unittest.main()
