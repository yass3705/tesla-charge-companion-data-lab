import unittest

from scripts.bump_direct_inventory import is_bump_operator, parse_tariff


class BumpInventoryTests(unittest.TestCase):
    def test_operator_match_is_strict(self):
        self.assertTrue(is_bump_operator("Bump"))
        self.assertTrue(is_bump_operator("BUMP SAS"))
        self.assertFalse(is_bump_operator("Electra"))
        self.assertFalse(is_bump_operator("Powerdot"))

    def test_parse_energy_price(self):
        parsed = parse_tariff("0,49 €/kWh")
        self.assertEqual(parsed["classification"], "explicit_price_candidate")
        self.assertEqual(parsed["components"]["energyEurPerKwh"], [0.49])

    def test_parse_combined_tariff(self):
        parsed = parse_tariff("0,39 €/kWh + 0,05 €/minute")
        self.assertEqual(parsed["components"]["energyEurPerKwh"], [0.39])
        self.assertEqual(parsed["components"]["minuteEur"], [0.05])

    def test_app_reference_is_not_rankable(self):
        parsed = parse_tariff("Tarif disponible dans l'application Bump")
        self.assertEqual(parsed["classification"], "app_reference")
        self.assertFalse(parsed["components"])


if __name__ == "__main__":
    unittest.main()
