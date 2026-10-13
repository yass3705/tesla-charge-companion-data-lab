import gzip
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/national/bump_direct_tariffs_tcc_france.json.gz"
RUNTIME = ROOT / "v9-production-runtime/data/v9/france-bump-offers.json"


class BumpRuntimeOfferIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(gzip.decompress(SOURCE.read_bytes()))
        cls.runtime = json.loads(RUNTIME.read_text())
        cls.source_rankable = {
            point["idPdcItinerance"]: point
            for station in cls.source["stations"]
            for point in station["points"]
            if point.get("rankable")
        }

    def test_exact_evse_accounting_without_foreign_rules(self):
        attached = [evse for offer in self.runtime["directOffers"] for evse in offer["evseIds"]]
        quarantined = [row["evseId"] for row in self.runtime["quarantinedSourceRankableEvse"]]
        self.assertEqual(len(attached), len(set(attached)))
        self.assertEqual(len(quarantined), len(set(quarantined)))
        self.assertFalse(set(attached) & set(quarantined))
        self.assertEqual(set(attached) | set(quarantined), set(self.source_rankable))
        self.assertEqual(len(attached), self.runtime["sourceEvidence"]["rankablePoints"])
        self.assertEqual(len(attached) + len(quarantined), self.source["counts"]["rankablePoints"])
        for offer in self.runtime["directOffers"]:
            self.assertEqual(offer["verifiedScope"], "exact_evse")
            self.assertEqual(offer["pricing"]["type"], "rules")
            self.assertEqual(offer["pricing"]["rules"][0]["scope"], "allDay")
            self.assertNotIn("kind", offer["pricing"]["rules"][0])

    def test_charging_minutes_do_not_become_parking_minutes(self):
        offer = next(offer for offer in self.runtime["directOffers"]
                     if offer["pricing"]["rules"][0].get("chargingTimePerMinuteEur") == 0.01)
        rule = offer["pricing"]["rules"][0]
        self.assertEqual(rule["sessionFeeEur"], 0.555)
        self.assertEqual(offer["pricing"]["minimumTotalEur"], 0.5)
        self.assertNotIn("postChargeFee", offer["pricing"])
        self.assertNotIn("idlePerMinute", rule)

    def test_unrepresented_conditions_stay_unpriced(self):
        reasons = {row["reason"] for row in self.runtime["quarantinedSourceRankableEvse"]}
        self.assertIn("conditional_flat_fee_duration_or_unknown", reasons)
        self.assertIn("unsupported_rule_energy_time_bands", reasons)
        self.assertIn("unsupported_rule_post_charge_occupancy_time_bands", reasons)

    def test_energy_condition_has_exact_strict_threshold(self):
        offer = next(offer for offer in self.runtime["directOffers"]
                     if offer["pricing"].get("conditionalSessionFees"))
        fee = offer["pricing"]["conditionalSessionFees"][0]
        self.assertGreater(fee["amountEur"], 0)
        self.assertEqual([c["kind"] for c in fee["conditions"]], ["energy_above_kwh"])
        self.assertGreater(fee["conditions"][0]["value"], 0)
        self.assertNotIn("sessionFeeEur", offer["pricing"]["rules"][0])


if __name__ == "__main__":
    unittest.main()
