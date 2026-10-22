"""Offline national/Monta exact-ID PowerUp collector migration."""

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

from v9_rebuild import swiss_powerup
from v9_rebuild.orchestrator import read_sources, run_source


NATIONAL = {"stations": [{"evseId": "CH*POW*E1"}, {"evseId": "CH*POW*E2"}]}
MONTA = {"data": [{"evse_id": "CH*POW*E1", "currency": "CHF", "price_kw": 0.55},
                  {"evse_id": "CH*POW*E3", "currency": "CHF", "price_kw": 0.60}]}


def offline_runner(command, **kwargs):
    def urlopen(request, **_):
        payload = NATIONAL if "geo.admin" in request.full_url else MONTA
        return io.BytesIO(json.dumps(payload).encode())
    old = Path.cwd()
    try:
        os.chdir(kwargs["cwd"])
        with patch("urllib.request.urlopen", side_effect=urlopen), redirect_stdout(io.StringIO()):
            runpy.run_path(command[1], run_name="__main__")
    finally:
        os.chdir(old)
    return subprocess.CompletedProcess(command, 0)


class SwissPowerupTests(unittest.TestCase):
    def test_exact_intersection_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            swiss_powerup.run(base / "direct", runner=offline_runner)
            payload = swiss_powerup.validate_output(base / "direct")
            self.assertEqual([r["evseId"] for r in payload["evses"]], ["CH*POW*E1"])
            self.assertEqual(payload["missingCurrentEvseIds"], ["CH*POW*E2"])
            self.assertEqual(payload["montaExtraEvseIds"], ["CH*POW*E3"])
            self.assertEqual(payload["counts"]["currentPricedEvseCount"], 1)
            spec = next(x for x in read_sources() if x["id"] == "CH:powerup_monta")

            def process(command, **_):
                swiss_powerup.run(Path(command[command.index("--out") + 1]), runner=offline_runner)
                return subprocess.CompletedProcess(command, 0)

            self.assertEqual(run_source(spec, base / "artifacts", runner=process)["status"], "ok")

    def test_failure_and_bad_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            def fail(command, **_):
                return subprocess.CompletedProcess(command, 2)
            with self.assertRaisesRegex(RuntimeError, "method failed"):
                swiss_powerup.run(base / "failed", runner=fail)
            swiss_powerup.run(base / "good", runner=offline_runner)
            path = base / "good" / swiss_powerup.DATA
            data = json.loads(path.read_text())
            data["evses"][0]["evseId"] = "CH*POW*EFALSE"
            path.write_text(json.dumps(data))
            # Counts alone do not establish an exact source identity: the missing/extra
            # sets and intersection must still be consistent with the generated rows.
            with self.assertRaises(ValueError):
                swiss_powerup.validate_output(base / "good")


if __name__ == "__main__":
    unittest.main()
