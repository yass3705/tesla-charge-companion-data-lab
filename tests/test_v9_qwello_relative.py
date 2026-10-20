"""Offline execution of Qwello's historical relative-output PDF method."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.cwd_script import run, validate_output
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source

sys.path.insert(0, str(ROOT / "scripts"))
import qwello_saone_et_loire_official as historical  # noqa: E402

SYDESL = "C’est l’opérateur QWELLO qui a été retenu, désormais le propriétaire des bornes déployées, et a repris les bornes installées initialement par le SYDESL."
PDF_TEXT = "QWELLO 22 kW AC tarif initial de 0,3 €/kWh + 0,02 €/min TTC pour QWELLO"


class Runner:
    def __init__(self, fail=False):
        self.fail = fail

    def __call__(self, command, **kwargs):
        old = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            def fetch(url, attempts=3):
                if self.fail and url == historical.SYDESL_TARIFF_PDF:
                    raise RuntimeError("fixture PDF unavailable")
                return (SYDESL.encode() if url == historical.SYDESL_MOBILITY else b"fixture-pdf"), 200
            with patch.object(historical, "fetch_bytes", side_effect=fetch), patch.object(historical, "pdf_text", return_value=PDF_TEXT), patch("builtins.print"):
                historical.main()
        except RuntimeError:
            return SimpleNamespace(returncode=2)
        finally:
            os.chdir(old)
        return SimpleNamespace(returncode=0)


class QwelloRelativeMigrationTests(unittest.TestCase):
    def test_historical_method_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run(root / "source", "qwello_saone_et_loire", runner=Runner())
            payload = validate_output(root / "source", "qwello_saone_et_loire")
            archived = json.loads((ROOT / "data/operator_direct/qwello_saone_et_loire_official.json").read_text())
            self.assertEqual(payload["operatorDirect"]["saoneEtLoire22KwInitialPublishedTariff"],
                             archived["operatorDirect"]["saoneEtLoire22KwInitialPublishedTariff"])
            self.assertFalse((root / "source/out").exists())
            spec = next(row for row in read_sources() if row["id"] == "FR:qwello_saone_et_loire")
            def outer(command, **kwargs):
                run(Path(command[command.index("--out") + 1]), "qwello_saone_et_loire", runner=Runner())
                return SimpleNamespace(returncode=0)
            artifact = run_source(spec, root / "artifacts", runner=outer)
            self.assertEqual(artifact["status"], "ok")
            self.assertEqual(len(artifact["files"]), 2)

    def test_failed_pdf_does_not_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, "Historical qwello_saone_et_loire method failed"):
                run(root, "qwello_saone_et_loire", runner=Runner(fail=True))
            self.assertFalse((root / "data/operator_direct/qwello_saone_et_loire_official.json").exists())


if __name__ == "__main__":
    unittest.main()
