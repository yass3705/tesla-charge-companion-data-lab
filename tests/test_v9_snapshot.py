import json
import tempfile
import unittest
from pathlib import Path

from v9_rebuild.canonical import normalize_swiss
from v9_rebuild.snapshot import prepare, verify


class SnapshotTest(unittest.TestCase):
    def test_immutable_reproducible_and_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "canonical.json"
            payload = {"schemaVersion": 3, "country": "CH", "evses": []}
            first = normalize_swiss(payload, artifact_sha256="a" * 64)
            source.write_text(json.dumps(first))
            old = prepare({"CH:swiss_integration": source}, root / "snapshots")
            self.assertEqual(prepare({"CH:swiss_integration": source}, root / "snapshots"), old)
            self.assertEqual(verify(old)["sources"][0]["source"], "CH:swiss_integration")
            second = normalize_swiss(payload, artifact_sha256="b" * 64)
            source.write_text(json.dumps(second))
            newer = prepare({"CH:swiss_integration": source}, root / "snapshots")
            self.assertNotEqual(old, newer)
            self.assertEqual(verify(old)["sources"][0]["sourceArtifactSha256"], "a" * 64)
            self.assertEqual(verify(newer)["sources"][0]["sourceArtifactSha256"], "b" * 64)

    def test_corruption_and_source_mismatch_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "canonical.json"
            source.write_text(json.dumps(normalize_swiss({"schemaVersion": 3, "country": "CH", "evses": []}, artifact_sha256="a" * 64)))
            with self.assertRaisesRegex(ValueError, "Source ID"):
                prepare({"FR:ionity_direct": source}, root / "snapshots")
            bundle = prepare({"CH:swiss_integration": source}, root / "snapshots")
            (bundle / "CH__swiss_integration.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "SHA"):
                verify(bundle)
            with self.assertRaisesRegex(ValueError, "SHA"):
                prepare({"CH:swiss_integration": source}, root / "snapshots")


if __name__ == "__main__":
    unittest.main()
