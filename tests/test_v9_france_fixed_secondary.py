"""INDIGO, Interparking and SEOLIS parsers on archived tariff fixtures."""

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

from v9_rebuild import france_fixed_secondary
from v9_rebuild.orchestrator import read_sources, run_source


def euro(value):
    return str(float(value)).replace(".", ",") if float(value) % 1 else str(int(value))


def seeds_and_pages(base: Path):
    seeds = {}
    archive = {}
    for path in france_fixed_secondary.DATA:
        data = json.loads((france_fixed_secondary.ROOT / path).read_text())
        seed = base / path.name
        seed.write_text(json.dumps(data))
        seeds[path] = seed
        archive[path.stem] = data
    indigo = archive["indigo_official_france"]["memberOffers"]["aLaCarte"]
    inter = archive["interparking_tariff_rules_france"]["directTariff"]
    seo = archive["seolis_alterbase_tariff_rules_france_2026"]
    sub, occ = seo["subscriber"], seo["occasional"]
    pages = {
        "indigoneo.fr": f"{euro(indigo['energyEurPerKwh'])} €/kWh à l'acte frais de session {euro(indigo['sessionFeeEur'])} €",
        "interparking.fr": f"Coût de recharge {euro(inter['eurPerKwh'])} €/kWh",
        "seolis.net": (
            f"Vous êtes un abonné abonnement {euro(sub['annualSubscriptionEur'])} € TTC par an "
            f"AC &lt; 24 kW : {euro(sub['acBelow24KwEurPerKwh'])} € "
            f"DC &lt; 24 kW : {euro(sub['dcBelow24KwEurPerKwh'])} € "
            f"DC &gt; 25 kW : {euro(sub['dcAbove25KwEurPerKwh'])} € "
            f"Vous êtes un utilisateur occasionnel "
            f"AC &lt; 24 kW : {euro(occ['acBelow24KwEurPerKwh'])} € "
            f"DC &lt; 24 kW : {euro(occ['dcBelow24KwEurPerKwh'])} € "
            f"DC &gt; 25 kW : {euro(occ['dcAbove25KwEurPerKwh'])} € "
            f"chaque session {euro(occ['sessionFeeEur'])} € Besoin d'une solution"),
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


class FranceFixedSecondaryTests(unittest.TestCase):
    def test_archived_pages_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seeds, pages = seeds_and_pages(base)
            france_fixed_secondary.run(base / "direct", seeds=seeds, runner=runner_for(pages))
            report = france_fixed_secondary.validate_output(base / "direct", seeds)
            self.assertEqual([row["status"] for row in report["results"]], ["unchanged"] * 4)
            source = next(row for row in read_sources() if row["id"] == "FR:fixed_tariff_secondary")

            def process(command, **_):
                france_fixed_secondary.run(Path(command[-1]), seeds=seeds, runner=runner_for(pages))
                return subprocess.CompletedProcess(command, 0)

            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_price_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seeds, pages = seeds_and_pages(base)
            pages["interparking.fr"] = pages["interparking.fr"].replace("0,5", "0,6")
            with self.assertRaisesRegex(ValueError, "price changed|archived tariff changed"):
                france_fixed_secondary.run(base / "price", seeds=seeds, runner=runner_for(pages))


if __name__ == "__main__":
    unittest.main()
