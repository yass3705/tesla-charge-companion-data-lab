import unittest

from scripts.ozecar.extract_ozecar import (
    PUBLIC_IRVE_FIELDS, PUBLIC_LIVE_FIELDS, inventory, norm, parse_text, public_fields,
)


class OzecarExtractTest(unittest.TestCase):
    def test_inventory_keeps_exact_producer_evse_and_latest_row(self):
        rows = [
            {"id_pdc_itinerance": "FROZEE123", "date_maj": "2026-09-01", "puissance_nominale": "22"},
            {"id_pdc_itinerance": "FR*OZE*E123", "date_maj": "2026-09-04", "puissance_nominale": "50"},
            {"id_pdc_itinerance": "FR-OTHER-E123", "date_maj": "2026-09-04"},
        ]
        result = inventory(rows)
        self.assertEqual(set(result), {norm("FROZEE123")})
        self.assertEqual(result[norm("FROZEE123")]["id_pdc_itinerance"], "FR*OZE*E123")
        self.assertEqual(result[norm("FROZEE123")]["puissance_nominale"], "50")

    def test_public_price_components_preserved(self):
        result = parse_text("Available\n0,55 EUR/kWh\nStart fee 1,50 EUR")
        self.assertEqual(result["status"], "available")
        self.assertEqual([(x["value"], x["unit"]) for x in result["priceComponents"]],
                         [(0.55, "kwh"), (1.5, None)])

    def test_isolated_session_total_is_not_a_tariff(self):
        self.assertEqual(parse_text("Session total 9,40 EUR")["priceComponents"], [])

    def test_private_status_is_not_reclassified_as_public(self):
        self.assertEqual(parse_text("Private charger\n0,40 EUR/kWh")["status"], "private charger")

    def test_public_projection_excludes_contacts_and_page_text(self):
        irve = {"id_pdc_itinerance": "FROZEE123", "prise_type_2": "TRUE",
                "contact_operateur": "personal@example.test"}
        live = {"evse": "FROZEE123", "status": "available", "text": "raw page content"}
        self.assertEqual(public_fields(irve, PUBLIC_IRVE_FIELDS),
                         {"id_pdc_itinerance": "FROZEE123", "prise_type_2": "TRUE"})
        self.assertEqual(public_fields(live, PUBLIC_LIVE_FIELDS),
                         {"evse": "FROZEE123", "status": "available"})


if __name__ == "__main__":
    unittest.main()
