"""Five preserved Spain core parsers on prices already archived in Data Lab."""

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

from v9_rebuild import spain_fixed_core
from v9_rebuild.orchestrator import read_sources, run_source


def decimal(value):
    return f"{float(value):.2f}".replace(".", ",")


def seeds_and_pages(base: Path):
    seeds = {}
    values = {}
    for path in spain_fixed_core.DATA:
        body = json.loads((spain_fixed_core.ROOT / path).read_text())
        seed = base / path.name
        seed.write_text(json.dumps(body))
        seeds[path] = seed
        values[path.stem.split("_")[0]] = body["publicTariffs"]
    r, e, w, z, a = (values[key] for key in ("repsol", "eranovum", "wenea", "zunder", "acciona"))
    pages = {
        "repsol.es": f"Motos {decimal(r['motorcyclesEurPerKwh'])} €/kWh coches normal {decimal(r['normalCarChargeEurPerKwh'])} €/kWh ultrarrápida {decimal(r['ultraFastCarChargeEurPerKwh'])} €/kWh",
        "eranovum.energy": f"España Hasta 22 kW {decimal(e['upTo22KwEurPerKwh'])} € 30 kW {decimal(e['30KwEurPerKwh'])} € 60 kW {decimal(e['60KwEurPerKwh'])} € 120 kW {decimal(e['120KwEurPerKwh'])} € a partir de 150 kW {decimal(e['from150KwEurPerKwh'])} € Bélgica",
        "wenea.com": f"AC 7.4 kW - 22 kW {decimal(w['ac7_4To22KwEurPerKwh'])} €/kWh DC 50 kW - 150 kW {decimal(w['dc50To150KwEurPerKwh'])} €/kWh HPC 151 kW - 400 kW {decimal(w['hpc151To400KwEurPerKwh'])} €/kWh",
        "zunder.com": f"Carga AC hasta 50 kW {decimal(z['standardAcUpTo50KwEurPerKwh'])} €/kWh Carga rápida más de 50 kW {decimal(z['standardFastOver50KwEurPerKwh'])} €/kWh",
        "acciona.com": f"hasta 22 kW {decimal(a['upTo22KwEurPerKwh'])} €/kWh más de 22 kW {decimal(a['over22KwEurPerKwh'])} €/kWh",
    }
    return seeds, pages


def runner_for(pages):
    def runner(command, **kwargs):
        def urlopen(request, **_):
            page = next(body for domain, body in pages.items() if domain in request.full_url)
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
    return runner


class SpainFixedCoreTests(unittest.TestCase):
    def test_five_parsers_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seeds, pages = seeds_and_pages(base)
            spain_fixed_core.run(base / "direct", seeds=seeds, runner=runner_for(pages))
            report = spain_fixed_core.validate_output(base / "direct", seeds)
            self.assertEqual([row["status"] for row in report["results"]], ["unchanged"] * 5)
            source = next(row for row in read_sources() if row["id"] == "ES:fixed_tariff_core")

            def process(command, **_):
                spain_fixed_core.run(Path(command[-1]), seeds=seeds, runner=runner_for(pages))
                return subprocess.CompletedProcess(command, 0)

            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_price_change_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seeds, pages = seeds_and_pages(base)
            pages["repsol.es"] = pages["repsol.es"].replace("0,56", "0,57")
            with self.assertRaisesRegex(ValueError, "tariff changed"):
                spain_fixed_core.run(base / "price", seeds=seeds, runner=runner_for(pages))


if __name__ == "__main__":
    unittest.main()
