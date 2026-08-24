import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from atlante_station_tariffs import make_payload, normalize_location, parse_energy_price


def tariff(price=0.54, dimension="ENERGY", conditions=None):
    return {
        "identifiers": {"evseId": "FR*ATL*E1", "connectorId": "c1"},
        "priceComponents": [{
            "priceDimension": dimension,
            "currency": "EUR",
            "price": {"incl_vat": price},
            "conditions": conditions or [],
            "validity": {"relative": {"timeAfterSessionStartValidityInMinutes": None, "displayText": []},
                         "absolute": {"daysOfWeekValidity": []}},
            "surchargeName": None,
        }],
    }


def detail(operator="Atlante", party="ATL", price_power=150):
    return {
        "id": "loc-1", "locationId": "FRATL*L1", "countryCode": "FR", "partyId": party,
        "operatorName": operator, "displayName": "Atlante Test", "coordinates": "48.1,2.2",
        "address": "1 rue Test", "postalCode": "75001", "city": "Paris",
        "evses": [{"evseId": "FR*ATL*E1", "evseStatus": "AVAILABLE", "statusLastUpdated": "2026-08-24T00:00:00Z",
                   "connectors": [{"evseConnectorId": "c1", "externalConnectorId": "1",
                                   "evseCommonConnectorType": "CCS", "evsePowerType": "DC",
                                   "max_electric_power": price_power}]}],
    }


class AtlanteStationTariffTests(unittest.TestCase):
    def test_parses_only_unconditional_energy_price(self):
        self.assertEqual(parse_energy_price(tariff()), 0.54)
        self.assertIsNone(parse_energy_price(tariff(dimension="PARKING_TIME")))
        self.assertIsNone(parse_energy_price(tariff(conditions=[{"kind": "after"}])))

    def test_strict_operator_party_and_country_scope(self):
        summary = {"id": "loc-1", "countryCode": "FR", "partyId": "ATL"}
        location = normalize_location(summary, detail(), [tariff()])
        self.assertEqual(location["connectors"][0]["pricePerKwhEur"], 0.54)
        self.assertEqual(location["connectors"][0]["powerKw"], 150.0)
        self.assertIsNotNone(normalize_location(summary, detail(operator="Atlante France"), [tariff()]))
        self.assertIsNone(normalize_location(summary, detail(operator="Powerdot"), [tariff()]))
        self.assertIsNone(normalize_location(summary, detail(party="PD1"), [tariff()]))

    def test_payload_explicitly_excludes_partners_and_subscription(self):
        summary = {"id": "loc-1", "countryCode": "FR", "partyId": "ATL"}
        location = normalize_location(summary, detail(), [tariff()])
        payload = make_payload({"locations": [summary]}, [location])
        self.assertEqual(payload["counts"]["franceLocationCount"], 1)
        self.assertTrue(payload["scope"]["onlyOperatedLocations"])
        self.assertFalse(payload["scope"]["partnerLocationsIncluded"])
        self.assertFalse(payload["scope"]["atlanteGoIncluded"])


if __name__ == "__main__":
    unittest.main()
