"""Archived-price preserving Delmonicos watcher, with offline page fixtures."""

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

from v9_rebuild import delmonicos_watch
from v9_rebuild.orchestrator import read_sources, run_source


PAGE = "tarif borne recharge"


def fixture_seed(base: Path) -> Path:
    data = json.loads((delmonicos_watch.ROOT / delmonicos_watch.DATA).read_text())
    signature = hashlib.sha256(PAGE.encode()).hexdigest()
    data["refresh"]["sourceHashes"] = {url: signature for url in data["refresh"]["sourceHashes"]}
    path = base / "seed.json"
    path.write_text(json.dumps(data))
    return path


def runner(command, **kwargs):
    old = Path.cwd()
    try:
        os.chdir(kwargs["cwd"])
        with patch("urllib.request.urlopen", side_effect=lambda *_args, **_kwargs: io.BytesIO(PAGE.encode())), redirect_stdout(io.StringIO()):
            try:
                runpy.run_path(command[1], run_name="__main__")
                code = 0
            except SystemExit as error:
                code = int(error.code)
    finally:
        os.chdir(old)
    return subprocess.CompletedProcess(command, code)


class DelmonicosWatchTests(unittest.TestCase):
    def test_historical_watch_preserves_prices_and_orchestrates(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seed = fixture_seed(base)
            delmonicos_watch.run(base / "direct", seed=seed, runner=runner)
            data = delmonicos_watch.validate_output(base / "direct", seed)
            self.assertEqual(data["refresh"]["lastResult"], "validated")
            source = next(row for row in read_sources() if row["id"] == "FR:delmonicos_watch")

            def process(command, **_):
                delmonicos_watch.run(Path(command[-1]), seed=seed, runner=runner)
                return subprocess.CompletedProcess(command, 0)

            result = run_source(source, base / "artifacts", attempts=1, runner=process)
            self.assertEqual(result["status"], "ok")

    def test_changed_source_and_price_mutation_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seed = fixture_seed(base)
            changed = json.loads(seed.read_text())
            changed["refresh"]["sourceHashes"] = {key: "0" * 64 for key in changed["refresh"]["sourceHashes"]}
            altered = base / "altered.json"
            altered.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "source changed"):
                delmonicos_watch.run(base / "review", seed=altered, runner=runner)
            delmonicos_watch.run(base / "valid", seed=seed, runner=runner)
            path = base / "valid" / delmonicos_watch.DATA
            data = json.loads(path.read_text())
            data["directMapped"]["stations"][0]["directTariff"]["energyEurPerKwh"] = 9.99
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "tariff altered"):
                delmonicos_watch.validate_output(base / "valid", seed)


if __name__ == "__main__":
    unittest.main()
