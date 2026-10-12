import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/v9_tariff_gap_baseline_20261012.py"
SPEC = importlib.util.spec_from_file_location("tariff_gap_baseline", MODULE)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class TariffGapEvidenceBaselineTest(unittest.TestCase):
    def test_nine_countries_are_dated_census_not_tariff_coverage(self):
        result = audit.baseline(ROOT)
        self.assertEqual(set(result["countries"]), set(audit.COUNTRIES))
        self.assertEqual(result["status"], "DATED_BASELINE_NOT_LIVE_EVSE_AUDIT")
        self.assertFalse(result["publication"])
        self.assertGreater(result["globalSourceCensus"]["filesScanned"], 100)
        self.assertIn("NOT priced/public active EVSE", result["countries"]["FR"]["scopeWarning"])

    def test_nl_missing_prices_are_not_equated_with_ambiguous_tariffs(self):
        result = audit.baseline(ROOT)["netherlandsFourCpos"]
        self.assertEqual(result["allMissingDirectTariff"], 3206)
        self.assertEqual(result["availableOrChargingWithMissingDirectTariff"], 2876)
        self.assertEqual(result["operators"]["SPA"]["missingDirectTariff"], 0)
        self.assertEqual(result["operators"]["AGO"]["missingDirectTariff"], 2578)
        self.assertFalse(result["operators"]["LNT"]["connectorTypesType2CcsVerified"])
        self.assertIn("5,246", result["notEquivalentTo"])

    def test_unverified_electra_emsp_fees_remain_uncalculable(self):
        result = audit.baseline(ROOT)["franceAfterMinutes"]
        self.assertEqual(result["offerSample"], 84)
        self.assertEqual(result["directOrSubscriptionRulesProved"], 6)
        self.assertEqual(result["electraEmspUnprovedTimeComponent"], 78)
        self.assertIn("tarif incalculable", result["statusForUnproved"])


if __name__ == "__main__":
    unittest.main()
