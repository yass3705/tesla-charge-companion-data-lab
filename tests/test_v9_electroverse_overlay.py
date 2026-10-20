"""Offline overlay gate tests; no Electroverse endpoint is contacted."""

import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests.test_v9_electroverse_status import fixture
from tests.test_v9_electroverse import save
from v9_rebuild.electroverse_overlay import OUT, REPORT, run, validate_output


class ElectroverseOverlayTests(unittest.TestCase):
    def test_rejects_partial_status_before_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source, status, out = base / "source", base / "status", base / "out"
            fixture(source, [])
            fixture(status, [])
            with self.assertRaises(Exception):
                run(out, source=source, status_source=status)
            self.assertFalse(out.exists())

    def test_tile_and_audit_integrity(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            tile = OUT / "t_0_0.json.gz"
            (out / tile).parent.mkdir(parents=True)
            with gzip.open(out / tile, "wt", encoding="utf-8") as handle:
                json.dump({"emspOffers": [{"id": "exact-evse", "evseIds": ["FR*ABC*E1"]}]}, handle)
            data = (out / tile).read_bytes()
            manifest = {"country": "FR", "dataset": "electroverse-france-evse-national-overlay", "tileCount": 1,
                        "tiles": [{"file": tile.name, "count": 1, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}]}
            save(out / OUT / "manifest.json", manifest)
            save(out / REPORT, {"offers": 1, "invalidPublishedSourceRefs": 0,
                                  "missingProvenanceOffers": 0, "statusPkConflicts": 0})
            self.assertEqual(validate_output(out), manifest)
            (out / tile).write_bytes(data + b"corruption")
            with self.assertRaisesRegex(ValueError, "integrity"):
                validate_output(out)


if __name__ == "__main__":
    unittest.main()
