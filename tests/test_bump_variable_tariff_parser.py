import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from bump_variable_tariff_parser import parse_tariff


class BumpVariableTariffParserTest(unittest.TestCase):
    def tariff(self, charge_duration=None, parking="0,00", energy="0,69"):
        lines = ["While charging:", f"Energy consumption: {energy} €/kWh"]
        if charge_duration:
            lines += ["", f"Duration: {charge_duration}"]
        lines += ["", "While parking (no energy delivered):", f"Duration: {parking} €/minute", "", "Minimum 0,50 € Inc. VAT"]
        return {"long": "\n".join(lines), "parkingText": f"Duration: {parking} €/minute"}

    def test_charging_duration_and_zero_parking_are_separate(self):
        cases = [("0,01 €/minute", 0.01, 0), ("0,29 €/minute after 1h15 of usage", 0.29, 75),
                 ("0,29 €/minute after 2h of usage", 0.29, 120), ("0,048 €/minute after 4h of usage", 0.048, 240)]
        for label, rate, delay in cases:
            with self.subTest(label=label):
                rules = parse_tariff(self.tariff(label))["rules"]
                charging = [r for r in rules if r["kind"] == "charging_duration_surcharge"]
                self.assertEqual(charging, [{"kind": "charging_duration_surcharge", "eurPerMinute": rate, "afterMinutes": delay}])
                self.assertFalse(any(r["kind"] == "post_charge_occupancy" for r in rules))

    def test_positive_parking_without_grace_is_only_after_charge(self):
        rules = parse_tariff(self.tariff(parking="0,50", energy="0,48"))["rules"]
        self.assertEqual([r for r in rules if r["kind"] == "post_charge_occupancy"],
                         [{"kind": "post_charge_occupancy", "eurPerMinute": 0.5, "graceMinutes": 0}])
        self.assertFalse(any(r["kind"] == "charging_duration_surcharge" for r in rules))

    def test_unknown_duration_unit_remains_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported charging duration rule"):
            parse_tariff(self.tariff("0,01 €/hour"))


if __name__ == "__main__":
    unittest.main()
