import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v9_rebuild.canonical_registry import BY_SOURCE, CanonicalRoute
from v9_rebuild.snapshot import verify


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_v9_canonical_batch.py"
SPEC = importlib.util.spec_from_file_location("build_v9_canonical_batch", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CanonicalBatchTests(unittest.TestCase):
    def test_repeatable_immutable_two_country_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ids = ["FR:ionity_direct", "GB:ionity_direct"]
            first = MODULE.build(root / "first", ids)
            second = MODULE.build(root / "second", list(reversed(ids)))
            self.assertEqual(first["bundleId"], second["bundleId"])
            bundle = root / "first" / "bundles" / first["bundleId"]
            self.assertEqual(len(verify(bundle)["sources"]), 2)
            self.assertEqual(json.loads((root / "first" / "build-report.json").read_text())["status"], "prepared")
            with self.assertRaisesRegex(ValueError, "new directory"):
                MODULE.build(root / "first", ids)

    def test_missing_archive_never_publishes_partial_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "failed"
            current = BY_SOURCE["FR:ionity_direct"]
            missing = CanonicalRoute(current.source_id, "data/national/missing-archive.json", current.normalizer)
            with patch.dict(BY_SOURCE, {current.source_id: missing}):
                with self.assertRaises(FileNotFoundError):
                    MODULE.build(output, [current.source_id])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
