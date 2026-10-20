"""Offline isolated Atlante adapter checks using the preserved parser."""

import gzip
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_atlante_station_tariffs import detail, tariff
from atlante_station_tariffs import make_payload, normalize_location
from v9_rebuild.orchestrator import ROOT, read_sources, run_source


class AtlanteAdapterTests(unittest.TestCase):
    def test_technically_complete_one_location_and_missing_secret(self):
        spec = next(row for row in read_sources() if row["id"] == "FR:atlante_direct")
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            with patch.dict(os.environ, {"ATLANTE_API_SUBSCRIPTION_KEY": ""}):
                self.assertEqual(run_source(spec, out)["reason"], "missing_required_secret")
            summary = {"id": "loc-1", "countryCode": "FR", "partyId": "ATL"}
            location = normalize_location(summary, detail(), [tariff()])
            payload = make_payload({"locations": [summary]}, [location])
            def fixture_runner(command, **kwargs):
                path = Path(command[command.index("--out") + 1])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(gzip.compress(json.dumps(payload).encode("utf-8"), mtime=0))
                return SimpleNamespace(returncode=0)
            with patch.dict(os.environ, {"ATLANTE_API_SUBSCRIPTION_KEY": "fixture-only"}):
                result = run_source(spec, out, runner=fixture_runner)
            self.assertEqual(result["status"], "ok")
            self.assertTrue((out / result["artifact"]).is_file())
            self.assertFalse((ROOT / "objects").exists())


if __name__ == "__main__":
    unittest.main()
