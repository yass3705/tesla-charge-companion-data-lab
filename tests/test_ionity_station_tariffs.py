import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ionity_station_tariffs import CANONICAL_CPO, build, parse_direct_connector


def connector(uuid="connector-1", amount="0.62", power=350000, name="IONITY DIRECT"):
    return {
        "uuid": uuid,
        "number": 1,
        "physicalReference": "01",
        "maxPower": power,
        "type": "CCS",
        "adhocPrice": {"name": name, "unit": "kWh", "amount": amount, "currency": "EUR"},
    }


class IonityStationTariffTests(unittest.TestCase):
    def test_parses_only_direct_eur_kwh_price(self):
        parsed = parse_direct_connector(connector())
        self.assertEqual(parsed["kind"], "DC")
        self.assertEqual(parsed["powerKw"], 350.0)
        self.assertEqual(parsed["pricePerKwhEur"], 0.62)
        self.assertIsNone(parse_direct_connector(connector(name="IONITY POWER")))

    def test_strict_cpo_and_france_filter(self):
        static = {
            "locations": [
                {"uuid": "fr-ionity", "name": "IONITY France", "locationId": "1", "cpoIdentifier": CANONICAL_CPO},
                {"uuid": "fr-partner", "name": "Partner France", "locationId": "2", "cpoIdentifier": "PARTNER_CPO"},
                {"uuid": "de-ionity", "name": "IONITY Germany", "locationId": "3", "cpoIdentifier": CANONICAL_CPO},
            ]
        }
        details = {
            "fr-ionity": {
                "uuid": "fr-ionity", "name": "IONITY France", "cpoIdentifier": CANONICAL_CPO,
                "country": "FR", "latitude": "48.0", "longitude": "2.0", "connectors": [connector()],
            },
            "de-ionity": {
                "uuid": "de-ionity", "name": "IONITY Germany", "cpoIdentifier": CANONICAL_CPO,
                "country": "DE", "latitude": "50.0", "longitude": "8.0", "connectors": [connector()],
            },
        }
        payload = build(static, details)
        self.assertEqual(payload["counts"]["franceLocationCount"], 1)
        self.assertEqual([x["uuid"] for x in payload["locations"]], ["fr-ionity"])
        self.assertTrue(payload["scope"]["onlyOperatedLocations"])
        self.assertFalse(payload["scope"]["subscriberTariffsIncluded"])

    def test_missing_or_invalid_direct_price_fails_closed(self):
        static = {"locations": [{"uuid": "fr", "cpoIdentifier": CANONICAL_CPO}]}
        details = {"fr": {
            "uuid": "fr", "name": "IONITY France", "cpoIdentifier": CANONICAL_CPO,
            "country": "FR", "latitude": "48", "longitude": "2",
            "connectors": [connector(name="N/A", amount="0.0")],
        }}
        with self.assertRaises(ValueError):
            build(static, details)


if __name__ == "__main__":
    unittest.main()
