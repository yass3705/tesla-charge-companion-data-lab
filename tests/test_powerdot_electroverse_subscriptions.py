"""Fail-closed subscription evidence tests: no cross-CPO or cross-country leakage."""
import unittest
from scripts.powerdot_official import parse_electroverse_subscriptions

PAGE = """Abonnements Electroverse
IONITY
Tarifs d'abonnement IONITY par pays France: 40 %.
Le coût de l'abonnement varie selon la localisation, 11,99 € par mois.
Abonnement Electroverse France, Espagne, Portugal et Belgique:
Powerdot
Rechargez chez Powerdot pour seulement 1,99 € par mois.
France : 22 % de réduction
Espagne : 29 % de réduction
Belgique : 30 % de réduction
Portugal : 25 % de réduction
Royaume-Uni uniquement
Be.EV
France: 51 % Royaume-Uni
Pologne Powerdot France : 28 %.
"""


class SubscriptionEvidenceTests(unittest.TestCase):
    def test_different_operator_percentages_are_independent(self):
        rules = parse_electroverse_subscriptions(PAGE)
        self.assertEqual(rules["ionity"]["FR"]["discountPercent"], 40)
        self.assertEqual(rules["powerdot"]["FR"]["discountPercent"], 22)
        self.assertEqual(rules["powerdot"]["ES"]["discountPercent"], 29)
        self.assertEqual(rules["powerdot"]["BE"]["discountPercent"], 30)
        self.assertEqual(rules["powerdot"]["PT"]["discountPercent"], 25)
        self.assertEqual(rules["ionity"]["FR"]["monthlyFeeEurIndicative"], 11.99)

    def test_missing_powerdot_country_fails(self):
        with self.assertRaisesRegex(RuntimeError, "espagne"):
            parse_electroverse_subscriptions(PAGE.replace("Espagne : 29 %", ""))

    def test_duplicate_conflicting_powerdot_country_fails(self):
        with self.assertRaisesRegex(RuntimeError, "france"):
            parse_electroverse_subscriptions(PAGE.replace(
                "France : 22 %", "France : 22 % France : 28 %"))

    def test_missing_ionity_fails(self):
        with self.assertRaises(RuntimeError):
            parse_electroverse_subscriptions(PAGE.replace("IONITY", "Other"))

    def test_missing_fee_fails(self):
        with self.assertRaisesRegex(RuntimeError, "Powerdot monthly fee"):
            parse_electroverse_subscriptions(PAGE.replace("pour seulement 1,99 €", "pour seulement 2,99 €"))

    def test_missing_section_boundary_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "terminator"):
            parse_electroverse_subscriptions(PAGE.replace(
                "Royaume-Uni uniquement\nBe.EV", "Unknown area"))


if __name__ == "__main__":
    unittest.main()
