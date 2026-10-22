"""France Lidl, Stations-E and eborn parsers on archived-price page fixtures."""

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

from v9_rebuild import france_fixed_core
from v9_rebuild.orchestrator import read_sources, run_source


def euro(value):
    return str(float(value)).replace(".", ",") if float(value) % 1 else str(int(value))


def seeds_and_pages(base: Path):
    seeds = {}
    archive = {}
    for path in france_fixed_core.DATA:
        data = json.loads((france_fixed_core.ROOT / path).read_text())
        seed = base / path.name
        seed.write_text(json.dumps(data))
        seeds[path] = seed
        archive[path.stem] = data
    lidl = archive["lidl_tariff_rules_france"]
    direct = lidl["directPayment"]
    promo = lidl["lidlPlusActiveOffer"]
    stations = archive["stations_e_tariff_rules_france"]["directPayment"]
    eborn = archive["eborn_easycharge_official_france"]
    classes = {row["class"]: row for row in eborn["powerClasses"]}
    ep = [f"Abonné à la carte {euro(eborn['subscription']['aLaCarteAnnualFeeEur'])} € TTC Abonnement annuel",
          f"Abonné au forfait {euro(eborn['subscription']['monthlyBundleFeeEur'])} € TTC Abonnement mensuel"]
    for label, name in (("accélérée", "accelerated"), ("rapide", "fast"), ("ultra-rapide", "ultra_fast")):
        row = classes[name]
        carte = (f"{euro(row['aLaCarteEurPerKwh'])} TTC € / kWh" if name == "ultra_fast"
                 else f"{euro(row['aLaCarteEurPerKwh'])} € TTC / kWh")
        ep.append(f"Charge {label} Abonné à la carte {carte} Non abonné {euro(row['nonSubscriberEurPerKwh'])} € TTC / kWh")
    pages = {
        "tarifs-bornes": f"AC {euro(direct['AC']['eurPerKwh'])} € par kWh DC {euro(direct['DC']['eurPerKwh'])} € par kWh",
        "e-mobilite-faq": f"prolongement exceptionnel du prix application Lidl Plus borne de type AC {euro(promo['AC']['eurPerKwh'])} € par kWh application Lidl Plus borne de type DC {euro(promo['DC']['eurPerKwh'])} € par kWh",
        "stations-e.com": f"Bornes 22AC ou 24DC {euro(stations['ac22OrDc24EurPerKwh'])} € / kWh Bornes 50DC {euro(stations['dc50EurPerKwh'])} € / kWh",
        "eborn.fr": " ".join(ep),
    }
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


class FranceFixedCoreTests(unittest.TestCase):
    def test_archived_pages_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seeds, pages = seeds_and_pages(base)
            france_fixed_core.run(base / "direct", seeds=seeds, runner=runner_for(pages))
            report = france_fixed_core.validate_output(base / "direct", seeds)
            self.assertEqual([row["status"] for row in report["results"]], ["unchanged"] * 4)
            source = next(row for row in read_sources() if row["id"] == "FR:fixed_tariff_core")

            def process(command, **_):
                france_fixed_core.run(Path(command[-1]), seeds=seeds, runner=runner_for(pages))
                return subprocess.CompletedProcess(command, 0)

            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_new_price_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seeds, pages = seeds_and_pages(base)
            pages["stations-e.com"] = pages["stations-e.com"].replace("0,54", "0,55")
            with self.assertRaisesRegex(ValueError, "price changed|archived tariff changed"):
                france_fixed_core.run(base / "price", seeds=seeds, runner=runner_for(pages))


if __name__ == "__main__":
    unittest.main()
