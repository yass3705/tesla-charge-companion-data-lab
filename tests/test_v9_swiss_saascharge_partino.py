"""Saascharge tariff bands and Partino access classification on reduced feeds."""

import json
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_v9_swiss_fastned import Response
from v9_rebuild.cwd_script import METHODS, run, validate_output
from v9_rebuild.electroverse import ROOT
from v9_rebuild.orchestrator import read_sources, run_source


class FixtureRunner:
    def __init__(self, method, fail=False):
        self.method = method
        self.fail = fail

    def __call__(self, command, **kwargs):
        if self.fail:
            return SimpleNamespace(returncode=2)
        operator = "CH*SCH" if self.method == "swiss_saascharge" else "CH*PAR"
        if self.method == "swiss_saascharge":
            rows = [
                {"EvseID": operator + "*E1", "ChargingFacilities": [{"power": 22, "powertype": "AC_3_PHASE"}], "Plugs": ["Type 2"]},
                {"EvseID": operator + "*E2", "ChargingFacilities": [{"power": 75, "powertype": "DC"}], "Plugs": ["CCS"]},
            ]
        else:
            rows = [
                {"EvseID": operator + "*E1", "Accessibility": "Restricted access", "AuthenticationModes": []},
                {"EvseID": operator + "*E2", "Accessibility": "Paying publicly accessible", "AuthenticationModes": ["REMOTE"]},
            ]
        fixture = {"stations": [{"OperatorID": operator, "EVSEs": rows},
                                 {"OperatorID": "CH*OTHER", "EVSEs": [{"EvseID": "CH*OTHER*E1"}]}]}
        cwd = Path.cwd()
        try:
            os.chdir(kwargs["cwd"])
            with patch("urllib.request.urlopen", return_value=Response(json.dumps(fixture).encode())), patch("builtins.print"):
                runpy.run_path(str(ROOT / METHODS[self.method][0]), run_name="__main__")
        finally:
            os.chdir(cwd)
        return SimpleNamespace(returncode=0)


class SwissSaaschargePartinoTests(unittest.TestCase):
    def test_exact_tariff_band_and_no_public_price(self):
        for method, source_id in (("swiss_saascharge", "CH:saascharge_official"),
                                  ("swiss_partino", "CH:partino_restricted")):
            with self.subTest(method=method), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                run(root / "source", method, runner=FixtureRunner(method))
                payload = validate_output(root / "source", method)
                self.assertEqual(payload["counts"]["nationalEvseCount"], 2)
                self.assertEqual(payload["counts"]["unresolvedEvseCount"], 1)
                if method == "swiss_saascharge":
                    self.assertEqual(payload["evses"][0]["tariffCategory"], "AC_CH_Max_AC")
                    self.assertEqual(payload["unresolved"][0]["evseId"], "CH*SCH*E2")
                else:
                    self.assertEqual(payload["evses"][0]["classification"], "no_public_direct_tariff")
                    self.assertEqual(payload["evses"][1]["classification"], "unresolved")
                spec = next(row for row in read_sources() if row["id"] == source_id)
                def outer(command, **kwargs):
                    run(Path(command[command.index("--out") + 1]), method, runner=FixtureRunner(method))
                    return SimpleNamespace(returncode=0)
                self.assertEqual(run_source(spec, root / "artifacts", runner=outer)["status"], "ok")

    def test_failures_and_corruption(self):
        for method in ("swiss_saascharge", "swiss_partino"):
            with self.subTest(method=method), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with self.assertRaisesRegex(RuntimeError, f"Historical {method} method failed"):
                    run(root / "failed", method, runner=FixtureRunner(method, fail=True))
                run(root / "source", method, runner=FixtureRunner(method))
                (root / "source" / METHODS[method][1]).write_text("{}")
                with self.assertRaises(ValueError):
                    validate_output(root / "source", method)


if __name__ == "__main__":
    unittest.main()
