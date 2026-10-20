"""Offline technical checks for the preserved Dutch collection chain."""

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from v9_rebuild.nl_dotnl import run, validate_output


class NetherlandsModuleTests(unittest.TestCase):
    def test_preserved_chain_on_empty_valid_snapshot(self):
        # Zero source records are valid; result volume is never a rejection rule.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            locations, tariffs = root / "locations.gz", root / "tariffs.gz"
            for path in (locations, tariffs):
                with gzip.open(path, "wt", encoding="utf-8") as handle:
                    json.dump([], handle)
            out = root / "artifacts"
            run(out, locations, tariffs, electra=False)
            validate_output(out)
            manifest_path = out / "data/national/netherlands_dotnl/runtime/manifest.json"
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["scope"]["countryCode"], "NL")
            self.assertEqual(manifest["stationCount"], 0)
            self.assertEqual(json.loads((out / "reports/netherlands/dotnl-national-tariff-preservation-latest.json").read_text())["overrideViolations"], 0)
            runtime_file = manifest_path.parent / manifest["allFile"]
            runtime_file.write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                validate_output(out)

    def test_corrupt_input_is_rejected_before_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bad, good = root / "bad.gz", root / "good.gz"
            bad.write_bytes(b"not-gzip")
            with gzip.open(good, "wt", encoding="utf-8") as handle:
                json.dump([], handle)
            with self.assertRaises(OSError):
                run(root / "artifacts", bad, good, electra=False)


if __name__ == "__main__":
    unittest.main()
