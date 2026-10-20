"""Offline FX update, fallback and immutable prior state checks."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.electroverse import ROOT
from v9_rebuild.fx import META, RATES, run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
import update_fx as historical  # noqa: E402


class OfflineRunner:
    def __init__(self, fallback=False, fail=False):
        self.fallback = fallback
        self.fail = fail

    def __call__(self, command, **kwargs):
        old = Path.cwd()
        source_rates = json.loads((ROOT / RATES).read_text())["rates"]
        rows = [{"quote": code, "rate": rate, "date": "2026-10-19"}
                for code, rate in source_rates.items() if code != "EUR"]
        def fetch(url):
            if self.fail:
                raise RuntimeError("provider unavailable")
            if url == historical.PRIMARY_URL and self.fallback:
                raise RuntimeError("primary unavailable")
            if url == historical.PRIMARY_URL:
                return rows
            return {"result": "success", "rates": source_rates, "time_last_update_utc": "Mon, 19 Oct 2026 00:00:00 +0000"}
        try:
            os.chdir(kwargs["cwd"])
            with patch.object(historical, "fetch_json", side_effect=fetch), patch("builtins.print"):
                historical.main()
        except RuntimeError:
            return SimpleNamespace(returncode=2)
        finally:
            os.chdir(old)
        return SimpleNamespace(returncode=0)


class FXMigrationTests(unittest.TestCase):
    def test_primary_fallback_and_orchestrator(self):
        for fallback in (False, True):
            with self.subTest(fallback=fallback), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                run(root / "source", runner=OfflineRunner(fallback=fallback))
                rates = validate_output(root / "source")
                self.assertEqual(set(rates["rates"]), set(historical.SUPPORTED))
                spec = next(row for row in read_sources() if row["id"] == "GL:fx")
                def outer(command, **kwargs):
                    run(Path(command[command.index("--out") + 1]), runner=OfflineRunner(fallback=fallback))
                    return SimpleNamespace(returncode=0)
                artifact = run_source(spec, root / "artifacts", runner=outer)
                self.assertEqual(artifact["status"], "ok")
                self.assertEqual(len(artifact["files"]), 2)

    def test_failure_keeps_previous_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "last_good", runner=OfflineRunner())
            before = (root / "last_good" / RATES).read_bytes()
            with self.assertRaisesRegex(RuntimeError, "Historical FX updater failed"):
                run(root / "failed", source=root / "last_good", runner=OfflineRunner(fail=True))
            self.assertEqual((root / "last_good" / RATES).read_bytes(), before)
            (root / "last_good" / META).write_text("{}")
            with self.assertRaisesRegex(ValueError, "technical contract"):
                run(root / "invalid", source=root / "last_good", runner=OfflineRunner())


if __name__ == "__main__":
    unittest.main()
