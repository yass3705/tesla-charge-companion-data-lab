"""Frozen REVE compact schema: source IDs, ambiguous IDs and technical integrity."""
import copy
import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_v9_canonical_batch as batch
from v9_rebuild.canonical_registry import CanonicalRoute
from v9_rebuild.canonical_spain_reve import normalize_spain_reve


class SpainReveCanonicalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = (batch.ROOT / "data/reve_v2/validated_runtime/spain-static/all.json.gz").read_bytes()
        cls.archive_sha = hashlib.sha256(raw).hexdigest()
        cls.rows = json.loads(gzip.decompress(raw))

    def test_source_and_official_identity_remain_distinct(self):
        exact = copy.deepcopy(self.rows[0])
        ambiguous = next(copy.deepcopy(row) for row in self.rows
                         if any(not config[0].startswith("ES*") or "*E" not in config[0]
                                for config in row[8]))
        result = normalize_spain_reve({"rows": [exact, ambiguous],
                                      "generatedAt": "2026-09-27T09:08:02.333Z"},
                                     artifact_sha256=self.archive_sha)
        self.assertEqual(len(result["stations"]), 2)
        self.assertEqual(result["source"]["generatedAt"], "2026-09-27T09:08:02.333Z")
        self.assertEqual(result["offers"], [])
        self.assertEqual(len(result["connectors"]), len(exact[8]) + len(ambiguous[8]))
        self.assertTrue(all(row["officialConnectorId"] is None and row["sourceConnectorId"] is None
                            for row in result["connectors"]))
        evses = {row["sourceEvseId"]: row for row in result["evses"]}
        self.assertEqual(evses[exact[8][0][0]]["officialEvseId"], exact[8][0][0])
        source_only = next(config[0] for config in ambiguous[8]
                           if not config[0].startswith("ES*") or "*E" not in config[0])
        self.assertIsNone(evses[source_only]["officialEvseId"])
        self.assertEqual(result["stations"][0]["country"], "ES")
        self.assertTrue(all(row["powerKw"] is None or row["powerKw"] > 0 for row in result["connectors"]))

    def test_reordering_keeps_ids_and_bad_schema_fails(self):
        sample = self.rows[:2]
        first = normalize_spain_reve({"rows": sample}, artifact_sha256=self.archive_sha)
        second = normalize_spain_reve({"rows": list(reversed(sample))}, artifact_sha256=self.archive_sha)
        for section in ("cpos", "stations", "evses", "connectors"):
            self.assertEqual(first[section], second[section])
        bad = copy.deepcopy(sample)
        bad[0][8][0][2] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "configuration schema"):
            normalize_spain_reve({"rows": bad}, artifact_sha256=self.archive_sha)

    def test_manifest_sha_and_tile_set_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "source"
            target.mkdir()
            rows = self.rows[:1]
            raw = gzip.compress(json.dumps(rows).encode(), mtime=0)
            (target / "all.json.gz").write_bytes(raw)
            (target / "tile.json.gz").write_bytes(raw)
            manifest = {"schemaVersion": 4, "country": "ES", "source": "REVE",
                        "generatedAt": "2026-09-27T09:08:02.333Z", "allFile": "all.json.gz",
                        "allSha256": hashlib.sha256(raw).hexdigest(), "stationCount": 1,
                        "tiles": [{"file": "tile.json.gz", "count": 1,
                                   "sha256": hashlib.sha256(raw).hexdigest()}]}
            (target / "manifest.json").write_text(json.dumps(manifest))
            route = CanonicalRoute("ES:reve_static", "source/all.json.gz", normalize_spain_reve,
                                   "source/manifest.json", spain_reve_manifest=True)
            with patch.object(batch, "ROOT", root):
                payload, digest, manifest_sha = batch.read_route(route, "ES:reve_static")
                self.assertEqual(payload["rows"], rows)
                self.assertEqual(digest, hashlib.sha256(raw).hexdigest())
                self.assertEqual(len(manifest_sha), 64)
                (target / "tile.json.gz").write_bytes(b"broken")
                with self.assertRaises((ValueError, OSError)):
                    batch.read_route(route, "ES:reve_static")


if __name__ == "__main__":
    unittest.main()
