import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from guard_swiss_bundle_refresh import validate_refresh


def bundle(ids, priced=0):
    return {
        "country": "CH", "nationalSource": "official-swiss",
        "counts": {
            "nationalEvseCount": len(ids),
            "directTariffResolvedEvseCount": priced,
            "noPublicDirectTariffEvseCount": 0,
            "directTariffUnresolvedEvseCount": len(ids) - priced,
        },
        "evses": [{"evseId": value, "stationId": value} for value in ids],
    }


class SwissRefreshGuardTest(unittest.TestCase):
    def test_any_valid_volume_change_and_tariff_disappearance(self):
        old = bundle([str(i) for i in range(100)], priced=1)
        for ids in ([], ["A"], [str(i) for i in range(150)]):
            self.assertIsNone(validate_refresh(old, bundle(ids)))

    def test_internal_count_and_identity(self):
        candidate = bundle(["A"])
        candidate["counts"]["nationalEvseCount"] = 2
        with self.assertRaisesRegex(ValueError, "count is inconsistent"):
            validate_refresh(None, candidate)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_refresh(None, bundle(["A", "A"]))
        candidate = bundle(["A"])
        candidate["evses"][0]["stationId"] = None
        with self.assertRaisesRegex(ValueError, "incomplete"):
            validate_refresh(None, candidate)

    def test_classification_and_scope(self):
        candidate = bundle(["A"])
        candidate["counts"]["directTariffUnresolvedEvseCount"] = 0
        with self.assertRaisesRegex(ValueError, "classifications"):
            validate_refresh(None, candidate)
        candidate = bundle(["A"])
        candidate["nationalSource"] = "other"
        with self.assertRaisesRegex(ValueError, "scope"):
            validate_refresh(bundle(["A"]), candidate)


if __name__ == "__main__":
    unittest.main()
