"""Preserved Sorégies method on archived facts, with headline prices unrankable."""

import csv
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from v9_rebuild import soregies_official
from v9_rebuild.orchestrator import read_sources, run_source


def fixture_runner(*, broken=False, empty=False):
    def run(command, **kwargs):
        spec = importlib.util.spec_from_file_location("soregies_fixture", command[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        archive = json.loads((soregies_official.ROOT / soregies_official.OUTPUT).read_text())
        examples = [] if empty else archive["technical"]["stationExamplesFromOfficialDataset"]
        buffer = io.StringIO()
        fieldnames = ["id_station_itinerance", "id_pdc_itinerance", "nom_station", "adresse_station",
                      "code_insee_commune", "nom_enseigne", "nom_operateur", "puissance_nominale",
                      "prise_type_2", "prise_type_combo_ccs", "prise_type_chademo"]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in examples:
            writer.writerow(row)
        pages = {
            module.OFFER_URL: b"Plus de 700 points de charge 1 000 000 application Sor\xc3\xa9gies Mobilit\xc3\xa9s tarif en vigueur typologie de la borne",
            module.PLUS_URL: b"-20% application Sor\xc3\xa9gies Mobilit\xc3\xa9s sans engagement",
            module.PRO_URL: "Sorégies Mobilités Pro application Sorégies Mobilités carte bancaire Normale Accéléré Rapide Ultra-rapide".encode(),
            module.DATASET_PAGE: "Sorégies Mobilités Gireve application Sorégies Mobilités carte bancaire".encode(),
            module.DATASET_CSV: buffer.getvalue().encode(),
        }
        def fetch(url, attempts=3):
            return pages[url], 503 if broken and url == module.DATASET_CSV else 200
        current = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            with patch.object(module, "fetch", side_effect=fetch), redirect_stdout(io.StringIO()):
                module.main()
        except RuntimeError:
            return subprocess.CompletedProcess(command, 1)
        finally:
            os.chdir(current)
        return subprocess.CompletedProcess(command, 0)
    return run


class SoregiesOfficialTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            soregies_official.run(base / "direct", runner=fixture_runner())
            payload = soregies_official.validate_output(base / "direct")
            self.assertEqual(payload["classification"]["officialDatasetRows"], 3)
            self.assertFalse(payload["currentMarketingOffer"]["headlineValuesSafeAsUniversalStationTariff"])
            source = next(row for row in read_sources() if row["id"] == "FR:soregies_mobilites_official")
            def process(command, **_):
                soregies_official.run(Path(command[-1]), runner=fixture_runner())
                return subprocess.CompletedProcess(command, 0)
            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_empty_dataset_and_price_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            soregies_official.run(base / "empty", runner=fixture_runner(empty=True))
            payload = soregies_official.validate_output(base / "empty")
            self.assertEqual(payload["classification"]["officialDatasetRows"], 0)
            output = base / "empty" / soregies_official.OUTPUT
            payload["currentMarketingOffer"]["mobilitesPlusHeadlineEurPerKwh"] = 9.99
            output.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "price-scope"):
                soregies_official.validate_output(base / "empty")

    def test_http_failure_stops_method(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "failed"):
                soregies_official.run(Path(tmp), runner=fixture_runner(broken=True))


if __name__ == "__main__":
    unittest.main()
