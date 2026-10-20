"""Deterministic archived France evidence build outside the checkout."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from v9_rebuild.france_canonical import OUTPUT, run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source


class FranceCanonicalMigrationTests(unittest.TestCase):
    def test_historical_builder_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec = next(row for row in read_sources() if row["id"] == "FR:canonical")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]))
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            state = root / "artifacts" / Path(*Path(artifact["artifact"]).parts[:3])
            payload = validate_output(state)
            self.assertEqual(payload["counts"]["operatorDirectSources"], len(payload["operatorDirectSources"]))
            self.assertTrue(payload["policy"]["unresolvedDirectPricesRemainUnranked"])
            self.assertEqual(spec["output_file"], OUTPUT.as_posix())
            source = payload["operatorDirectSources"][0]["sourcePath"]
            path = state / source
            path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "payload differs from provenance"):
                validate_output(state)


if __name__ == "__main__":
    unittest.main()
