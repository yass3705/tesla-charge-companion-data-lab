#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

from electric55_direct_tariffs import enrich, extract_map_links, parse_tariff_profile
from electric55_station_base import build


def tariff_payload() -> dict:
    return {
        "paymentMethodRequired": True,
        "definitions": [{
            "_id": "profile-22",
            "name": "Electric 55 Charging x E55C",
            "description": "E55C EMSP",
            "method": "ROAMING_EMPS",
            "isPrivate": False,
            "isMatching": True,
            "currencyCode": "EUR",
            "options": {"isDiscount": False},
            "where": {"allSiteAreas": True},
            "who": {"allUsersAndTags": True},
            "items": [
                {
                    "dimensions": {
                        "flatFee": {"active": True, "price": 0.5, "vat": 20},
                    },
                },
                {
                    "dimensions": {
                        "chargingTime": {"active": True, "price": 4.2, "vat": 20},
                        "parkingTime": {"active": True, "price": 4.2, "vat": 20},
                    },
                    "restrictions": {"timeFrom": "07:00", "timeTo": "23:00"},
                },
                {
                    "dimensions": {
                        "chargingTime": {"active": True, "price": 3.12, "vat": 20},
                        "parkingTime": {"active": True, "price": 3.12, "vat": 20},
                    },
                    "restrictions": {"timeFrom": "23:00", "timeTo": "07:00"},
                },
            ],
        }],
        "translations": {
            "fr": "0,60 € TTC par recharge | 5,04 € TTC par heure de charge et de parking"
        },
    }


class Electric55DirectTariffTests(unittest.TestCase):
    def test_extracts_only_exact_e55c_payment_links(self) -> None:
        features = [{
            "id": "station-1",
            "properties": {
                "description": (
                    '<a href="https://ev-qr.com/?t=e55c&amp;b=FR%2A55C%2AEFR39000%2AP7PPFG%2A1&amp;c=1">B01</a>'
                    '<a href="https://ev-qr.com/?t=other&amp;b=FR%2AOTH%2A1&amp;c=1">other</a>'
                )
            },
        }]
        links = extract_map_links(features)
        self.assertEqual(list(links), ["FR*55C*EFR39000*P7PPFG*1"])
        link = links["FR*55C*EFR39000*P7PPFG*1"]
        self.assertEqual(link["connectorId"], 1)
        self.assertIn("t=e55c", link["paymentUrl"])
        self.assertIn("b=FR%2A55C%2AEFR39000%2AP7PPFG%2A1", link["paymentUrl"])

    def test_tariff_parser_keeps_charging_and_parking_separate(self) -> None:
        profile = parse_tariff_profile(tariff_payload())
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertTrue(profile["globalScopeEvidence"])
        self.assertTrue(profile["chargingAndParkingDimensionsMustRemainSeparate"])
        self.assertEqual(profile["rules"][0]["flatEur"], 0.6)
        self.assertEqual(profile["rules"][1]["chargingTimeEurPerMinute"], 0.084)
        self.assertEqual(profile["rules"][1]["parkingTimeEurPerMinute"], 0.084)
        self.assertEqual(profile["rules"][2]["chargingTimeEurPerMinute"], 0.0624)

    def test_enrichment_is_exact_evse_scoped_and_status_free(self) -> None:
        local_evse_id = "FR*55C*EFR39000*P7PPFG*1"
        row = {
            "nom_station": "PARKING PLACE GUILLERMET - LONS-LE-SAUNIER",
            "adresse_station": "Rue Lecourbe 39000 Lons-le-Saunier",
            "coordonneesxy": "[5.548529,46.674931]",
            "id_station_itinerance": "FR55CP39000LSAP7PPFG",
            "id_pdc_itinerance": "FR55CEFR39000P7PPFG1",
            "id_pdc_local": local_evse_id,
            "nom_operateur": "Electric 55 Charging",
            "nom_enseigne": "E55C",
            "nom_amenageur": "E55C",
            "nbre_pdc": "1",
            "paiement_acte": "true",
            "gratuit": "false",
            "prise_type_2": "true",
            "puissance_nominale": "22.08",
        }
        payload = build([row], source={"lastModified": "2026-08-23T00:00:00Z", "sha256": "test"})
        links = {
            local_evse_id: {
                "chargingStationId": local_evse_id,
                "connectorId": 1,
                "paymentUrl": "https://ev-qr.com/?t=e55c&b=exact&c=1",
                "mapFeatureId": "station-1",
            }
        }
        result = {local_evse_id: {"ok": True, "payload": tariff_payload(), "url": "https://example.test"}}
        enriched = enrich(
            payload,
            links=links,
            tariff_results=result,
            map_evidence={"paymentLinkCount": 1},
            full_refresh=True,
        )
        point = enriched["stations"][0]["chargePoints"][0]
        self.assertEqual(point["pricing"]["status"], "resolved_e55c_scan_pay")
        self.assertNotIn("rules", point["pricing"])
        self.assertEqual(point["directAccess"]["chargingStationId"], local_evse_id)
        self.assertTrue(point["directAccess"]["available"])
        self.assertNotIn("status", point)
        self.assertFalse(enriched["scope"]["dynamicStatusIncluded"])
        self.assertEqual(enriched["stats"]["directTariffCoverageRatio"], 1.0)
        self.assertEqual(enriched["stations"][0]["offers"][0]["pricingProfileId"], point["pricing"]["profileId"])
        self.assertEqual(enriched["directTariffProfiles"][0]["rules"][1]["chargingTimeEurPerMinute"], 0.084)

    def test_endpoint_404_does_not_keep_a_stale_cached_tariff(self) -> None:
        local_evse_id = "FR*55C*EFR39000*P7PPFG*1"
        row = {
            "nom_station": "Station test",
            "adresse_station": "Rue Test 39000 Lons-le-Saunier",
            "coordonneesxy": "[5.548529,46.674931]",
            "id_station_itinerance": "FR55CPTEST",
            "id_pdc_itinerance": "FR55CETEST1",
            "id_pdc_local": local_evse_id,
            "nom_operateur": "E55C",
            "paiement_acte": "true",
            "gratuit": "false",
            "prise_type_2": "true",
            "puissance_nominale": "22.08",
        }
        source = {"lastModified": "2026-08-23T00:00:00Z", "sha256": "test"}
        links = {
            local_evse_id: {
                "chargingStationId": local_evse_id,
                "connectorId": 1,
                "paymentUrl": "https://ev-qr.com/?t=e55c&b=exact&c=1",
                "mapFeatureId": "station-1",
            }
        }
        previous = enrich(
            build([copy.deepcopy(row)], source=source),
            links=links,
            tariff_results={local_evse_id: {"ok": True, "payload": tariff_payload()}},
            map_evidence={"paymentLinkCount": 1},
            full_refresh=True,
        )
        current = enrich(
            build([copy.deepcopy(row)], source=source),
            links=links,
            tariff_results={local_evse_id: {"ok": False, "httpStatus": 404}},
            map_evidence={"paymentLinkCount": 1},
            previous=previous,
            full_refresh=False,
        )
        point = current["stations"][0]["chargePoints"][0]
        self.assertEqual(point["pricing"]["status"], "missing_direct_tariff")
        self.assertFalse(point["directAccess"]["available"])


if __name__ == "__main__":
    unittest.main()
