"""Offline Swiss CPI exact-EVSE archived closeout."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v9_rebuild import swiss_cpi
from v9_rebuild.orchestrator import read_sources, run_source


def fixture_root(root: Path) -> None:
    for relative in (*swiss_cpi.INPUTS, swiss_cpi.SCRIPT):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(swiss_cpi.ROOT / swiss_cpi.SCRIPT, root / swiss_cpi.SCRIPT)
    atlas = {"stations": [{"stationId": "A", "chargePoints": [{"chargePoint": {
        "evse_ids": ["CH*CPI*EONE"]}, "directTariffs": [{"id": "DIRECT-ONE"}]}]}]}
    rec = {"operators": [{"operatorId": "CH*CPI", "nationalEvseCount": 2}]}
    ctx = {"hits": [{"evseId": "CH*CPI*ETWO", "record": {
        "Accessibility": "Restricted access", "AuthenticationModes": []}}]}
    for relative, payload in zip(swiss_cpi.INPUTS, (atlas, rec, ctx)):
        (root / relative).write_text(json.dumps(payload))


class SwissCpiTests(unittest.TestCase):
    def test_reduced_exact_price_and_restricted_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture_root(base / "source")
            with patch.object(swiss_cpi, "ROOT", base / "source"):
                swiss_cpi.run(base / "direct")
            payload = swiss_cpi.validate_output(base / "direct")
            self.assertEqual((payload["nationalEvseCount"], payload["pricedEvseCount"],
                              payload["classifiedNoPublicDirectTariffCount"]), (2, 1, 1))
            spec = next(x for x in read_sources() if x["id"] == "CH:cpi_finalization")

            def process(command, **_):
                with patch.object(swiss_cpi, "ROOT", base / "source"):
                    swiss_cpi.run(Path(command[command.index("--out") + 1]))
                return subprocess.CompletedProcess(command, 0)

            self.assertEqual(run_source(spec, base / "artifacts", runner=process)["status"], "ok")

    def test_archived_full_scope_and_technical_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            swiss_cpi.run(base / "full")
            payload = swiss_cpi.validate_output(base / "full")
            self.assertEqual(payload["nationalEvseCount"], len(payload["evses"]))
            self.assertEqual(payload["pricedEvseCount"] +
                             payload["classifiedNoPublicDirectTariffCount"], len(payload["evses"]))
            fixture_root(base / "source")
            def fail(command, **_):
                return subprocess.CompletedProcess(command, 2)
            with patch.object(swiss_cpi, "ROOT", base / "source"):
                with self.assertRaisesRegex(RuntimeError, "closeout failed"):
                    swiss_cpi.run(base / "failed", runner=fail)
            path = base / "full" / swiss_cpi.OUTPUT
            payload = json.loads(path.read_text())
            payload["evses"][0]["evseId"] = "CH*CPI*EFALSE"
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "scope invalid"):
                swiss_cpi.validate_output(base / "full")


if __name__ == "__main__":
    unittest.main()
