"""Spain EMT/Endesa/Plenergy archived tariff refresh on offline fixtures."""

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

from v9_rebuild import spain_fixed_secondary
from v9_rebuild.orchestrator import read_sources, run_source


EMT_PAGE = "Colón reserva retirada"
PDF = b"offline archived PDF fixture"


def seed_files(base: Path):
    seeds = {}
    pages = {}
    for relative in spain_fixed_secondary.DATA:
        data = json.loads((spain_fixed_secondary.ROOT / relative).read_text())
        if "emt_madrid" in relative.name:
            data["refresh"]["semanticTariffContextSha256"] = hashlib.sha256(EMT_PAGE.lower().encode()).hexdigest()
            pages[data["source"]] = EMT_PAGE.encode()
        elif "endesa" in relative.name:
            data["refresh"]["sourceSha256"] = hashlib.sha256(PDF).hexdigest()
            pages[data["source"]] = PDF
        else:
            for station in data["stationTariffs"]:
                price = f"{float(station['eurPerKwh']):.2f}".replace(".", ",")
                pages[station["source"]] = f"Precio KWh {price} €".encode()
        path = base / relative.name
        path.write_text(json.dumps(data))
        seeds[relative] = path
    return seeds, pages


def make_runner(pages):
    def runner(command, **kwargs):
        def urlopen(request, **_):
            return io.BytesIO(pages[request.full_url])
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
    return runner


class SpainFixedSecondaryTests(unittest.TestCase):
    def test_historical_methods_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seeds, pages = seed_files(base)
            spain_fixed_secondary.run(base / "direct", seeds=seeds, runner=make_runner(pages))
            report = spain_fixed_secondary.validate_output(base / "direct", seeds)
            self.assertEqual([row["status"] for row in report["results"]], ["unchanged"] * 3)
            source = next(row for row in read_sources() if row["id"] == "ES:fixed_tariff_secondary")

            def process(command, **_):
                spain_fixed_secondary.run(Path(command[-1]), seeds=seeds, runner=make_runner(pages))
                return subprocess.CompletedProcess(command, 0)

            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_changed_hash_and_exact_station_price_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seeds, pages = seed_files(base)
            emt = next(path for path in seeds if "emt_madrid" in path.name)
            data = json.loads(seeds[emt].read_text())
            data["refresh"]["semanticTariffContextSha256"] = "0" * 64
            seeds[emt].write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "requires review"):
                spain_fixed_secondary.run(base / "changed", seeds=seeds, runner=make_runner(pages))
            seeds, pages = seed_files(base)
            plenergy = next(path for path in seeds if "plenergy" in path.name)
            first = json.loads(seeds[plenergy].read_text())["stationTariffs"][0]
            pages[first["source"]] = "Precio KWh 9,99 €".encode()
            with self.assertRaisesRegex(ValueError, "requires review"):
                spain_fixed_secondary.run(base / "price", seeds=seeds, runner=make_runner(pages))


if __name__ == "__main__":
    unittest.main()
