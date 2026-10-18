import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from guard_swiss_bundle_refresh import validate_refresh


def bundle(ids, priced=1):
    return {
        "country": "CH", "nationalSource": "official-swiss", "generatedAt": "2026-10-18T00:00:00Z",
        "counts": {
            "nationalEvseCount": len(ids),
            "directTariffResolvedEvseCount": priced,
            "noPublicDirectTariffEvseCount": 0,
            "directTariffUnresolvedEvseCount": len(ids) - priced,
        },
        "evses": [{"evseId": value, "stationId": value} for value in ids],
    }


class SwissRefreshGuardTest(unittest.TestCase):
    def setUp(self):
        self.old = bundle([str(i) for i in range(100)])

    def candidate(self, count):
        return bundle([str(i) for i in range(count)])

    def test_growth_and_exact_five_percent(self):
        self.assertIsNone(validate_refresh(self.old, self.candidate(101)))
        self.assertIsNone(validate_refresh(self.old, self.candidate(95)))

    def test_above_five_and_exact_thirty_warn(self):
        for count in (94, 70):
            warning = validate_refresh(self.old, self.candidate(count))
            self.assertEqual(warning["evses"]["previous"], 100)
            self.assertEqual(warning["evses"]["current"], count)
            self.assertEqual(len(warning["stations"]["disappearedIds"]), 100-count)
            self.assertEqual(warning["source"], "official-swiss")

    def test_over_thirty_blocks(self):
        with self.assertRaisesRegex(ValueError, "coverage fell"):
            validate_refresh(self.old, self.candidate(69))

    def test_empty_and_duplicate_block(self):
        with self.assertRaises(ValueError):
            validate_refresh(self.old, self.candidate(0))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_refresh(None, bundle(["A", "A"]))

    def test_tariff_loss_and_scope_change_block(self):
        with self.assertRaisesRegex(ValueError, "tariffs disappeared"):
            validate_refresh(self.old, bundle(["A"], priced=0))
        changed = self.candidate(100)
        changed["nationalSource"] = "other"
        with self.assertRaisesRegex(ValueError, "scope"):
            validate_refresh(self.old, changed)

    def test_warning_records_both_metrics_when_only_evse_count_falls(self):
        old = bundle([str(i) for i in range(100)])
        for row in old['evses']:
            row['stationId'] = str(int(row['evseId']) % 50)
        current = bundle([str(i) for i in range(90)])
        for row in current['evses']:
            row['stationId'] = str(int(row['evseId']) % 50)
        warning = validate_refresh(old, current)
        self.assertEqual(warning['evses']['previous'], 100)
        self.assertEqual(warning['stations']['previous'], 50)
        self.assertEqual(warning['stations']['current'], 50)
        self.assertEqual(warning['stations']['disappearedIds'], [])

    def test_missing_station_identity_blocks(self):
        current = self.candidate(100)
        current['evses'][0]['stationId'] = None
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            validate_refresh(self.old, current)


if __name__ == "__main__":
    unittest.main()
