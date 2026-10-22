"""Both archived e-Vadea image discovery and grid parser run without network."""

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from v9_rebuild import evadea_official
from v9_rebuild.orchestrator import read_sources, run_source


def fixture_runner(*, changed=False, missing_image=False):
    def run(command, **kwargs):
        base = Path(kwargs["cwd"])
        discovery_file = base / evadea_official.SCRIPTS[1]
        final_file = base / evadea_official.SCRIPTS[0]
        def load(name, file):
            spec = importlib.util.spec_from_file_location(name, file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        discovery = load("evadea_discovery_fixture", discovery_file)
        final = load("evadea_final_fixture", final_file)
        archived = json.loads((evadea_official.ROOT / "reports/evadea/latest_tariff_image_discovery.json").read_text())
        lines = archived["tariffImage"]["tariffRelevantLines"][:]
        if changed:
            lines = [line.replace("0,48", "0,98") for line in lines]
        image_url = "https://www.e-vadea.fr/storage/text_images/archived-fixture.png"
        pages = {
            discovery.SOURCES["tariffs"]: (200, f'<img alt="Tarification tableau" src="{image_url}">'.encode(), "utf-8"),
            image_url: (404 if missing_image else 200, b"offline archived image fixture" * 80, "utf-8"),
            discovery.SOURCES["faq"]: (200, "pré-autorisation 49€ forfait post-charge tolérance de 5 minutes invité".encode(), "utf-8"),
            discovery.SOURCES["howTo"]: (200, "tarif différent opérateur de mobilité disponibilité en temps réel".encode(), "utf-8"),
            discovery.SOURCES["inventoryCsv"]: (200, b"nom_station;adresse_station;id_pdc_itinerance;puissance_nominale\nFixture;Adresse;FR*EVA*E1;50\n", "utf-8"),
        }
        def fetch(url):
            return pages[url]
        def run_discovery(out):
            prior = sys.argv
            try:
                sys.argv = [str(discovery_file), "--out", str(out / "discovery")]
                with patch.object(discovery, "fetch", side_effect=fetch), \
                     patch.object(discovery.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "\n".join(lines), "")), \
                     redirect_stdout(io.StringIO()):
                    discovery.main()
            finally:
                sys.argv = prior
            return json.loads((out / "discovery/discovery.json").read_text())
        prior = sys.argv
        try:
            sys.argv = command[1:]
            with patch.object(final, "run_discovery", side_effect=run_discovery), redirect_stdout(io.StringIO()):
                final.main()
        except RuntimeError:
            return subprocess.CompletedProcess(command, 1)
        finally:
            sys.argv = prior
        return subprocess.CompletedProcess(command, 0)
    return run


class EvadeaOfficialTests(unittest.TestCase):
    def test_image_discovery_grid_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            evadea_official.run(base / "direct", runner=fixture_runner())
            payload = evadea_official.validate_output(base / "direct")
            self.assertEqual(payload["fees"]["occupancy"]["gracePeriodMinutes"], 5)
            self.assertFalse(payload["roaming"]["operatorDirect"])
            source = next(row for row in read_sources() if row["id"] == "FR:evadea_official")
            def process(command, **_):
                evadea_official.run(Path(command[-1]), runner=fixture_runner())
                return subprocess.CompletedProcess(command, 0)
            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_changed_ocr_price_and_output_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "failed"):
                evadea_official.run(base / "changed", runner=fixture_runner(changed=True))
            with self.assertRaisesRegex(RuntimeError, "failed"):
                evadea_official.run(base / "missing-image", runner=fixture_runner(missing_image=True))
            evadea_official.run(base / "valid", runner=fixture_runner())
            output = base / "valid" / evadea_official.OUTPUT
            payload = json.loads(output.read_text())
            payload["operatorDirect"]["motorway"]["lessThan100Kw"]["eurPerKwh"] = 9.99
            output.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "grid"):
                evadea_official.validate_output(base / "valid")


if __name__ == "__main__":
    unittest.main()
