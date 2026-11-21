from pathlib import Path
import tempfile
import unittest

from scripts.verify_v9_source_handoff import verify_tariff_generation
from tests.test_v9_electroverse import fixture, save
from v9_rebuild.electroverse import CACHE, MAPPING, read_json, shard_index
from v9_rebuild.electroverse_renewal import job_window


class GenerationTests(unittest.TestCase):
    def test_verified_ancestor_and_current_job_cover_exact_mapping(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root, ["a", "b"])
            start, second = "2026-11-21T08:00:00Z", "2026-11-21T10:00:00Z"
            save(root / CACHE / "checked-at.json", {"checkedAt": {"a": start, "b": second}})
            for pk in ["a", "b"]:
                shard = root / CACHE / f"shard-{shard_index(pk):03d}.json"
                data = read_json(shard)
                data["stations"][pk] = {"electroverseLocationPk": pk, "tariffHash": pk, "tariff": {"fixture": pk}}
                save(shard, data)
            _, proof = job_window(root, start, start)
            receipt = {"runId": 1, "renewalWindow": proof, "jobStartedAt": start, "jobCompletedAt": start}
            self.assertEqual(verify_tariff_generation(root, second, second, [receipt])["verifiedLocations"], 2)
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                verify_tariff_generation(root, second, second, [])
            shard = root / CACHE / f"shard-{shard_index('a'):03d}.json"
            data = read_json(shard)
            data["stations"]["a"]["tariff"] = {}
            save(shard, data)
            with self.assertRaisesRegex(ValueError, "changed"):
                verify_tariff_generation(root, second, second, [receipt])
            data["stations"]["a"]["tariff"] = {"fixture": "a"}
            save(shard, data)
            mapping = read_json(root / MAPPING)
            mapping["mappings"][0]["irveStationId"] = "different"
            save(root / MAPPING, mapping)
            with self.assertRaisesRegex(ValueError, "changed"):
                verify_tariff_generation(root, second, second, [receipt])
