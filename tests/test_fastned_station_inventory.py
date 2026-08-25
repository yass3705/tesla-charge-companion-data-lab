import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fastned_station_inventory import (
    canonical_location_url,
    discover_location_urls,
    make_payload,
    parse_country_tariff,
    parse_location_page,
)


TARIFF_TEXT = """
Prix standard € 0,61 en France
Bénéficiez de 10 % de réduction sur le prix standard sans frais supplémentaires via l'appli Fastned.
Prix abonné € 0,43 (€ 0,43 par kWh en France)
Économisez 30% sur le prix standard avec un abonnement Gold Member.
Valable aux 400+ stations de recharge Fastned pour 3 véhicules par foyer.
€5,99 par mois jusqu'au 30 septembre 2026 ; résiliable à tout moment après 30 jours.
"""

FR_HTML = """
<html><body>
<h1>Aire de Test</h1>
<div>Address Aire de Test A1, Paris, France Opening times Ouvert 24/7 Chargers 8 points de recharge</div>
<div>Type de connecteurs CCS, CCS, CHADEMO, AC Puissance maximale Jusqu'à 400 kW Nombre de points de recharge 8</div>
<div>A partir de EUR 0,43/kWh (avec une réduction de 30 % pour les membres Gold), tarif standard : 0,61/kWh</div>
<a href="https://www.google.com/maps/dir/?api=1&amp;destination=48.8566%2C2.3522&amp;travelmode=driving">Me rendre</a>
</body></html>
"""

DE_HTML = FR_HTML.replace("Paris, France", "Köln, Germany")


class FastnedStationInventoryTests(unittest.TestCase):
    def test_country_tariff_and_subscription(self):
        tariff = parse_country_tariff(TARIFF_TEXT)
        self.assertEqual(tariff["standardEurPerKwh"], 0.61)
        self.assertEqual(tariff["appDirectEurPerKwh"], 0.549)
        self.assertEqual(tariff["goldEurPerKwh"], 0.43)
        self.assertEqual(tariff["goldMonthlyFeeEur"], 5.99)
        self.assertEqual(tariff["goldMonthlyFeePromotionEnd"], "2026-09-30")

    def test_location_page_france_filter_and_metadata(self):
        tariff = parse_country_tariff(TARIFF_TEXT)
        station = parse_location_page(
            "https://www.fastnedcharging.com/fr/emplacements/aire-de-test", FR_HTML, tariff
        )
        self.assertEqual(station["stationId"], "fastned:aire-de-test")
        self.assertEqual(station["country"], "FR")
        self.assertEqual(station["chargingPoints"], 8)
        self.assertEqual(station["maxPowerKw"], 400)
        self.assertEqual(station["connectorTypes"], ["CCS", "CHADEMO", "AC"])
        self.assertAlmostEqual(station["latitude"], 48.8566)
        self.assertAlmostEqual(station["longitude"], 2.3522)
        self.assertIsNone(parse_location_page(
            "https://www.fastnedcharging.com/fr/emplacements/koeln", DE_HTML, tariff
        ))

    def test_station_price_mismatch_fails_closed(self):
        tariff = parse_country_tariff(TARIFF_TEXT)
        with self.assertRaises(ValueError):
            parse_location_page(
                "https://www.fastnedcharging.com/fr/emplacements/aire-de-test",
                FR_HTML.replace("tarif standard : 0,61", "tarif standard : 0,70"),
                tariff,
            )

    def test_sitemap_recursion_and_path_filter(self):
        index = """<?xml version='1.0'?><sitemapindex xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
        <sitemap><loc>https://www.fastnedcharging.com/a.xml</loc></sitemap></sitemapindex>"""
        many = "".join(
            f"<url><loc>https://www.fastnedcharging.com/fr/emplacements/station-{i}</loc></url>"
            for i in range(300)
        )
        urlset = f"<?xml version='1.0'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>{many}<url><loc>https://www.fastnedcharging.com/fr/recharge/tarifs</loc></url></urlset>"
        def fake_fetch(url):
            if url.endswith("sitemap.xml"):
                return index
            if url.endswith("a.xml"):
                return urlset
            raise AssertionError(url)
        root, urls, sitemap_count = discover_location_urls(fake_fetch)
        self.assertTrue(root.endswith("sitemap.xml"))
        self.assertEqual(len(urls), 300)
        self.assertEqual(sitemap_count, 2)
        self.assertEqual(
            canonical_location_url("https://fastnedcharging.com/fr/emplacements/x/?foo=1"),
            "https://www.fastnedcharging.com/fr/emplacements/x",
        )

    def test_payload_keeps_subscription_separate(self):
        tariff = parse_country_tariff(TARIFF_TEXT)
        location = parse_location_page(
            "https://www.fastnedcharging.com/fr/emplacements/aire-de-test", FR_HTML, tariff
        )
        locations = []
        for i in range(50):
            row = dict(location)
            row["stationId"] = f"fastned:test-{i}"
            row["slug"] = f"test-{i}"
            row["name"] = f"Test {i}"
            locations.append(row)
        payload = make_payload("https://www.fastnedcharging.com/sitemap.xml", 1, [f"u{i}" for i in range(300)], locations, tariff)
        profiles = {x["id"]: x for x in payload["pricingProfiles"]}
        self.assertFalse(profiles["fastned-app-direct"]["subscriptionRequired"])
        self.assertTrue(profiles["fastned-gold"]["subscriptionRequired"])
        self.assertFalse(payload["scope"]["fastnedDiscountsApplyAtPartnerOperators"])
        self.assertFalse(payload["scope"]["roamingTariffsIncluded"])


if __name__ == "__main__":
    unittest.main()
