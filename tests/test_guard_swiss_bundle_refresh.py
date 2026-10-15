import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from guard_swiss_bundle_refresh import validate_refresh


def bundle(ids, priced=1):
    return {
        "counts": {
            "nationalEvseCount": len(ids),
            "directTariffResolvedEvseCount": priced,
            "noPublicDirectTariffEvseCount": 0,
            "directTariffUnresolvedEvseCount": len(ids) - priced,
        },
        "evses": [{"evseId": value} for value in ids],
    }


class SwissRefreshGuardTest(unittest.TestCase):
    def test_growth_preserves_inventory(self):
        validate_refresh(bundle(["A"]), bundle(["A", "B"]))

    def test_inventory_loss_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "count fell"):
            validate_refresh(bundle(["A", "B"]), bundle(["A"]))

    def test_global_tariff_loss_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "tariffs disappeared"):
            validate_refresh(bundle(["A"]), bundle(["A"], priced=0))

    def test_duplicate_identity_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_refresh(None, bundle(["A", "A"]))


if __name__ == "__main__":
    unittest.main()
