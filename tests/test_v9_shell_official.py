"""Archived Shell representative price with all configured page failures visible."""

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

from v9_rebuild import shell_official
from v9_rebuild.orchestrator import read_sources, run_source


def fixture_runner(*, broken_render=False, changed_price=False, bad_http=False):
    def run(command, **_):
        spec = importlib.util.spec_from_file_location("shell_fixture", command[1])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        archive = json.loads((shell_official.ROOT / shell_official.OUTPUT).read_text())
        price = archive["operatorDirect"]["fastShellRechargeWithShellApp"]["representativeCurrentEurPerKwh"]
        station_by_url = {module.SOURCES[row["key"]]: row for row in module.REPRESENTATIVE_RENDERED_SAMPLES}

        def fetch(url):
            if url in station_by_url:
                return (503 if bad_http and station_by_url[url]["key"] == "cestas" else 200), "Shell Recharge carte de recharge"
            return 200, "Bienvenue au service client Shell France aide et support Shell Recharge"

        def render(url):
            sample = station_by_url[url]
            if broken_render and sample["key"] == "sommesous":
                raise RuntimeError("offline rendered tariff unavailable")
            return {"eurPerKwh": price + (0.01 if changed_price else 0),
                    "sessionFeeEur": None,
                    "powerKwObserved": sample["powerKwObserved"],
                    "evidenceMode": "current_rendered_first_party_station_page"}

        prior = sys.argv
        try:
            sys.argv = command[1:]
            with patch.object(module, "fetch", side_effect=fetch), \
                 patch.object(module, "render_station_tariff", side_effect=render), \
                 redirect_stdout(io.StringIO()):
                module.main()
        except RuntimeError:
            return subprocess.CompletedProcess(command, 1)
        finally:
            sys.argv = prior
        return subprocess.CompletedProcess(command, 0)
    return run


class ShellOfficialTests(unittest.TestCase):
    def test_complete_archived_sample_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            shell_official.run(base / "direct", runner=fixture_runner())
            payload = shell_official.validate_output(base / "direct")
            self.assertEqual(payload["operatorDirect"]["renderedFirstPartySamples"]["count"], 5)
            self.assertIsNone(payload["operatorDirect"]["fastShellRechargeWithShellApp"]["uniformAcrossFastShellRechargeStations"])
            source = next(row for row in read_sources() if row["id"] == "FR:shell_recharge_official")
            def process(command, **_):
                shell_official.run(Path(command[-1]), runner=fixture_runner())
                return subprocess.CompletedProcess(command, 0)
            self.assertEqual(run_source(source, base / "artifacts", attempts=1, runner=process)["status"], "ok")

    def test_partial_render_http_failure_and_price_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "failed"):
                shell_official.run(base / "partial", runner=fixture_runner(broken_render=True))
            with self.assertRaisesRegex(ValueError, "contract"):
                shell_official.run(base / "http", runner=fixture_runner(bad_http=True))
            with self.assertRaisesRegex(ValueError, "contract"):
                shell_official.run(base / "new-price", runner=fixture_runner(changed_price=True))


if __name__ == "__main__":
    unittest.main()
