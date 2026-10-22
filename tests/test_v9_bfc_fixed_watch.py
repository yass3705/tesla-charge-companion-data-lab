"""BFC semantic watches and SIED70 parser on archived-price fixtures."""

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

from v9_rebuild import bfc_fixed_watch
from v9_rebuild.orchestrator import read_sources, run_source


BFC_PAGE = "SICECO Côte-d'Or SIEEEN Nièvre SDEY Yonne Territoire d'Energie 90 Belfort"
SYDED_PAGE = "SYDED 22 kW 50 kW 100 kW"


def decimal(value):
    return f"{float(value):.2f}".replace(".", ",")


def seeds_and_pages(base: Path):
    seeds = {}
    pages = {"bourgogne-franche-comte.com": BFC_PAGE,
             "syded.fr": SYDED_PAGE}
    for relative in bfc_fixed_watch.DATA:
        data = json.loads((bfc_fixed_watch.ROOT / relative).read_text())
        if "sied70" in relative.name:
            direct = data["operatorDirect"]
            low, high = direct["acceleratedBelow50Kw"], direct["rapid50KwOrMore"]
            pages["sied70.fr"] = (
                f"puissance inférieure à 50 kW {decimal(low['eurPerKwh'])} € TTC / kWh "
                f"puissance supérieure ou égale à 50 kW {decimal(high['eurPerKwh'])} € TTC / kWh "
                f"pénalité de {decimal(low['postChargeFee']['eurPerMinute'])} € / minute")
        else:
            page = SYDED_PAGE if "syded" in relative.name else BFC_PAGE
            data["refresh"]["semanticTariffContextSha256"] = hashlib.sha256(page.lower().encode()).hexdigest()
        seed = base / relative.name
        seed.write_text(json.dumps(data))
        seeds[relative] = seed
    return seeds, pages


def runner_for(pages):
    def runner(command, **kwargs):
        def urlopen(request, **_):
            page = next(value for domain, value in pages.items() if domain in request.full_url)
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


class BfcFixedWatchTests(unittest.TestCase):
    def test_six_preserved_methods_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seeds, pages = seeds_and_pages(base)
            bfc_fixed_watch.run(base / "direct", seeds=seeds, runner=runner_for(pages))
            report = bfc_fixed_watch.validate_output(base / "direct", seeds)
            self.assertEqual([row["status"] for row in report["results"]], ["unchanged"] * 6)
            source = next(row for row in read_sources() if row["id"] == "FR:bfc_fixed_watch")

            def process(command, **_):
                bfc_fixed_watch.run(Path(command[-1]), seeds=seeds, runner=runner_for(pages))
                return subprocess.CompletedProcess(command, 0)

            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_changed_context_and_price_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seeds, pages = seeds_and_pages(base)
            target = next(path for path in seeds if "siceco" in path.name)
            data = json.loads(seeds[target].read_text())
            data["refresh"]["semanticTariffContextSha256"] = "0" * 64
            seeds[target].write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "requires review"):
                bfc_fixed_watch.run(base / "changed", seeds=seeds, runner=runner_for(pages))
            seeds, pages = seeds_and_pages(base)
            pages["sied70.fr"] = pages["sied70.fr"].replace("0,54", "0,55")
            with self.assertRaisesRegex(ValueError, "archived tariff changed"):
                bfc_fixed_watch.run(base / "price", seeds=seeds, runner=runner_for(pages))


if __name__ == "__main__":
    unittest.main()
