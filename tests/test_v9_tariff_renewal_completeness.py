import tempfile
import unittest
from pathlib import Path
from scripts.verify_v9_source_handoff import verify_full_tariff_renewal
from tests.test_v9_electroverse import fixture, save


class RenewalCompletenessTests(unittest.TestCase):
    def test_mapping_membership_and_run_window_not_historical_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp);fixture(state, ["a", "b"])
            checked = state / "data/electroverse/tariff_cache/checked-at.json"
            start, end = "2026-11-14T10:00:00Z", "2026-11-14T11:00:00Z"
            save(checked, {"checkedAt": {"a": start, "b": end, "old-unmapped": "2025-01-01T00:00:00Z"}})
            self.assertTrue(verify_full_tariff_renewal(state,start,end)["allMappedLocationsRenewed"])
            for rows in [{"a":start}, {"a":start,"b":"2026-11-13T00:00:00Z"}]:
                save(checked, {"checkedAt":rows})
                with self.assertRaises(ValueError):verify_full_tariff_renewal(state,start,end)
            fixture(state, [])
            save(checked, {"checkedAt":{}})
            self.assertEqual(verify_full_tariff_renewal(state,start,end)["mappedLocationsCheckedThisJob"],0)


if __name__ == "__main__":
    unittest.main()
