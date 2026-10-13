"""EnergyVision supplementary CPO catalog must never infer a customer EVSE tariff."""
import copy
import unittest

from scripts.energyvision_datex_independent_cpo import analyze


def sample():
    return {
        "provider": "EnergyVision", "country": "BE",
        "v9PublicationReady": False,
        "collectedAt": "2026-10-13T15:09:30Z",
        "sourceStatic": {"sha256": "a" * 64},
        "static": {"sites": [{
            "sourceSiteId": "SITE1", "sourceSiteType": "onStreet",
            "latitude": "50.85", "longitude": "4.35",
            "city": "Brussel", "postalCode": "1000",
            "stations": [{
                "sourceStationId": "S1",
                "declaredRefillPoints": "1",
                "authenticationMethods": ["rfid", "apps"],
                "stationRatesUnassignedToEvse": [{
                    "sourceRateId": "RATE1", "ratePolicy": "adHoc",
                    "priceComponents": [{"priceType": "pricePerKWh", "amountSource": "0.35"}],
                }],
                "refillPoints": [{
                    "sourceRefillPointId": "P1", "sourcePowerW": "22000",
                    "connectors": [{
                        "sourceExternalIdentifier": "BE*NRG*E1",
                        "sourceConnectorType": "iec62196T2",
                        "sourcePowerW": "22000",
                    }],
                }],
            }],
        }]},
        "dynamic": {"refillPointStatuses": [
            {"sourceReferenceId": "P1", "status": "available"},
            {"sourceReferenceId": "EXTRA", "status": "charging"},
        ]},
    }


class IndependentSupplementTests(unittest.TestCase):
    def test_source_only_no_tariff_in_pdc_even_single_point(self):
        result = analyze(sample(), nap_identity={"unmatchedIds": 1})
        self.assertFalse(result["v9PublicationReady"])
        self.assertEqual(result["v9PricedPDC"], 0)
        self.assertEqual(result["counts"]["activePDC"], 1)
        self.assertEqual(result["counts"]["dynamicReferencesNotInStatic"], 1)
        site = result["sites"][0]
        self.assertFalse(site["publicAccessVerified"])
        self.assertEqual(site["sourceSiteType"], "onStreet")
        self.assertEqual(site["stations"][0]["unassignedStationRateIds"], ["RATE1"])
        self.assertEqual(site["stations"][0]["sourceStationRatesUnassignedToPdc"][0]["priceComponents"][0]["amountSource"], "0.35")
        self.assertEqual(site["stations"][0]["pdc"][0]["sourcePointEnergyRateCount"], None)
        self.assertFalse(site["stations"][0]["pdc"][0]["priceable"])
        point = site["stations"][0]["pdc"][0]
        self.assertFalse(point["priceable"])
        self.assertFalse(point["publicAccessVerified"])
        self.assertNotIn("price", point)
        self.assertNotIn("rate", point)

    def test_crosswalk_overlap_rejected(self):
        with self.assertRaisesRegex(ValueError, "NAP duplicates"):
            analyze(sample(), nap_identity={"exactVerified": 1})

    def test_duplicate_external_id_rejected(self):
        data = sample()
        second = copy.deepcopy(data["static"]["sites"][0]["stations"][0]["refillPoints"][0])
        second["sourceRefillPointId"] = "P2"
        data["static"]["sites"][0]["stations"][0]["refillPoints"].append(second)
        data["dynamic"]["refillPointStatuses"].append({"sourceReferenceId": "P2", "status": "available"})
        with self.assertRaisesRegex(ValueError, "Duplicate or missing external"):
            analyze(data)

    def test_missing_status_not_available(self):
        data = sample()
        data["dynamic"]["refillPointStatuses"] = []
        result = analyze(data)
        self.assertEqual(result["counts"].get("activePDC", 0), 0)
        self.assertEqual(result["counts"]["ambiguousOrMissingStatusPDC"], 1)

    def test_connector_and_power_guards(self):
        data = sample()
        data["static"]["sites"][0]["stations"][0]["refillPoints"][0]["connectors"][0]["sourcePowerW"] = "nan"
        with self.assertRaisesRegex(ValueError, "Invalid connector watts"):
            analyze(data)

    def test_wrong_provider_or_published_stage_rejected(self):
        data = sample()
        data["provider"] = "OTHER"
        with self.assertRaises(ValueError):
            analyze(data)
        data = sample()
        data["v9PublicationReady"] = True
        with self.assertRaises(ValueError):
            analyze(data)


if __name__ == "__main__":
    unittest.main()
