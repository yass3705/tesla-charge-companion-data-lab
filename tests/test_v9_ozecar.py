"""Offline full OZECAR method, exact EVSE scope and technical error gate."""

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

from v9_rebuild import ozecar
from v9_rebuild.orchestrator import read_sources, run_source


ROWS = [
    {"id_pdc_itinerance": "FR*OZE*E1", "id_station_itinerance": "FR*OZE*S1", "date_maj": "2026-01-01"},
    {"id_pdc_itinerance": "FR*OZE*E2", "id_station_itinerance": "FR*OZE*S2", "date_maj": "2026-01-01"},
    {"id_pdc_itinerance": "FR*OZE*E3", "id_station_itinerance": "FR*OZE*S3", "date_maj": "2026-01-01"},
]


def runner_for(error=False):
    def runner(command, **_):
        spec = importlib.util.spec_from_file_location("ozecar_fixture", command[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        def latest_csv():
            return {"id": "archived-fixture", "url": "offline-fixture"}, b"unused"
        async def run_all(evses, workers):
            first = module.parse_text("Available\n0,55 EUR/kWh\nStart fee 1,50 EUR")
            return [
                {"evse": evses[0], "resolved": True, **first},
                {"evse": evses[1], "resolved": True, **module.parse_text("Private charger")},
                {"evse": evses[2], "resolved": False, "status": None, "priceComponents": [],
                 **({"error": "fixture transport failure"} if error else {})},
            ]
        with patch.object(module, "latest_csv", side_effect=latest_csv), \
             patch.object(module, "decode_csv", return_value=ROWS), \
             patch.object(module, "run_all", side_effect=run_all), \
             patch.object(sys, "argv", command[1:]), redirect_stdout(io.StringIO()):
            module.main()
        return subprocess.CompletedProcess(command, 0)
    return runner


class OzecarMigrationTests(unittest.TestCase):
    def test_public_private_unresolved_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ozecar.run(base / "direct", runner=runner_for())
            payload = ozecar.validate_output(base / "direct")
            self.assertEqual([row["evseKey"] for row in payload["records"]],
                             ["FROZEE1", "FROZEE2", "FROZEE3"])
            self.assertEqual([row["rankableDirect"] for row in payload["records"]], [True, False, False])
            source = next(row for row in read_sources() if row["id"] == "FR:ozecar")
            def process(command, **_):
                ozecar.run(Path(command[-1]), runner=runner_for())
                return subprocess.CompletedProcess(command, 0)
            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_transport_error_and_identity_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with self.assertRaisesRegex(ValueError, "technical collection"):
                ozecar.run(base / "error", runner=runner_for(error=True))
            ozecar.run(base / "valid", runner=runner_for())
            plain = base / "valid" / ozecar.PLAIN
            payload = json.loads(plain.read_text())
            payload["records"][0]["evseKey"] = "FROZEE999"
            plain.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                ozecar.validate_output(base / "valid")


if __name__ == "__main__":
    unittest.main()
