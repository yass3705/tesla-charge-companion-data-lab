import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts/verify_italy_v9_runtime_parity.py"
spec = importlib.util.spec_from_file_location("italy_parity", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ItalianParityContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture = {
            "schemaVersion": 4, "country": "IT", "allFile": "all.json.gz",
            "allSha256": "candidate-sha",
            "stationCount": 29696,
            "tiles": [{"file": "tile_40_10.json.gz", "sha256": "candidate-tile-sha", "count": 29696}]
        }

    def test_valid_shape_is_not_a_source_switch_approval(self):
        self.assertEqual(module.verify_manifest(self.fixture), [])

    def test_station_regression_rejected(self):
        self.fixture["stationCount"] = 29695
        self.assertTrue(any("regression" in x for x in module.verify_manifest(self.fixture)))

    def test_tile_count_mismatch_rejected(self):
        self.fixture["tiles"][0]["count"] = 42
        self.assertTrue(any("station-count" in x for x in module.verify_manifest(self.fixture)))

    def test_missing_hash_rejected(self):
        self.fixture["tiles"][0]["sha256"] = ""
        self.assertTrue(any("SHA/count" in x for x in module.verify_manifest(self.fixture)))


if __name__ == "__main__":
    unittest.main()
