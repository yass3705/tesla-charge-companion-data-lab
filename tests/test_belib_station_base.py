#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest

from belib_station_base import build, is_strict_belib, service_class, tariff_profiles


def official_tariffs() -> dict:
    return {
        "dataset": "belib-official-paris",
        "visitor": {
            "flex": {"eurPerKwh": 0.33, "eurPer15MinConnected": 0.57},
            "boost": {"eurPer15MinConnected": 2.30},
            "boostPlus": {"eurPerMinuteConnected": 0.42},
        },
        "subscriptions": {
            "annualFeeEur": 7.0,
            "nonResident": {
                "flex": {"eurPerKwh": 0.33, "eurPer15MinConnected": 0.37},
                "boost": {"eurPer15MinConnected": 2.00},
                "boostPlus": {"eurPerMinuteConnected": 0.38},
            },
            "residentParis": {
                "day": {
                    "flex": {"eurPerKwh": 0.33, "eurPer15MinConnected": 0.37},
                    "boost": {"eurPer15MinConnected": 2.00},
                    "boostPlus": {"eurPerMinuteConnected": 0.38},
                },
                "night2000To2300": {
                    "flex": {"eurPerKwh": 0.33, "connectedTimeComponentEur": 0.0},
                },
                "night2300To0800": {
                    "flex": {"eurPerKwh": 0.25, "connectedTimeComponentEur": 0.0},
                },
            },
        },
        "fees": {
            "longConnection": {"thresholdHours": 14, "eurPerHourAfterThreshold": 10.0},
            "boostPlusPrivateParking": {
                "parkingPaidAtExit": True,
                "parkingStillSiteSpecific": True,
            },
        },
    }


def row(**changes) -> dict:
    base = {
        "id_station_local": "FR*V75*PPX01*01",
        "id_station_itinerance": "FRV75PPX0101",
        "id_pdc_local": "FR*V75*EPX01*01*1",
        "id_pdc_itinerance": "FRV75EPX01011",
        "nom_station": "Paris | Rue Test 1",
        "adresse_station": "1 Rue Test 75001 Paris",
        "coordonneesxy": {"lat": 48.8566, "lon": 2.3522},
        "nom_operateur": "TOTALENERGIES",
        "nom_enseigne": "Belib'",
        "statut_pdc": "En service",
        "station_deux_roues": "False",
        "puissance_nominale": "7",
        "prise_type_2": "True",
        "prise_type_combo_ccs": "False",
        "prise_type_ef": "True",
        "horaires": "24/7",
        "condition_acces": "Accès libre",
        "paiement_cb": "True",
        "paiement_acte": "True",
        "paiement_autre": "True",
        "date_maj": "2026-08-24",
    }
    return {**base, **changes}


class BelibStationBaseTests(unittest.TestCase):
    def test_operator_and_brand_filter_are_both_strict(self) -> None:
        self.assertTrue(is_strict_belib(row()))
        self.assertFalse(is_strict_belib(row(nom_operateur="Autre CPO")))
        self.assertFalse(is_strict_belib(row(nom_enseigne="TotalEnergies")))

    def test_service_classes_follow_official_belib_families(self) -> None:
        self.assertEqual(service_class(3.7), "flex")
        self.assertEqual(service_class(7), "flex")
        self.assertEqual(service_class(22), "boost")
        self.assertEqual(service_class(43), "boostPlus")
        self.assertEqual(service_class(50), "boostPlus")

    def test_tariff_profiles_keep_parking_out(self) -> None:
        profiles = tariff_profiles(official_tariffs())
        self.assertEqual(len(profiles), 9)
        encoded = json.dumps(profiles).lower()
        self.assertNotIn("parkingpaid", encoded)
        self.assertNotIn("parkingcost", encoded)
        self.assertNotIn("parkingper", encoded)
        visitor_flex = next(p for p in profiles if p["profileId"] == "belib-visitor-flex")
        self.assertAlmostEqual(visitor_flex["rules"][0]["connectedTimeEurPerMinute"], 0.038)
        nonresident = next(p for p in profiles if p["profileId"] == "belib-nonresident-flex")
        self.assertEqual(nonresident["subscriptionId"], "belib-nonresident")
        self.assertAlmostEqual(nonresident["rules"][0]["connectedTimeEurPerMinute"], 0.37 / 15)
        resident = next(p for p in profiles if p["profileId"] == "belib-resident-flex")
        self.assertEqual([(r["start"], r["end"]) for r in resident["rules"]], [
            ("08:00", "20:00"), ("20:00", "23:00"), ("23:00", "08:00")
        ])

    def test_build_excludes_roaming_fictitious_moto_and_incompatible_rows(self) -> None:
        rows = [
            row(),
            row(
                id_pdc_local="FR*V75*EPX01*01*2",
                id_pdc_itinerance="FRV75EPX01012",
                puissance_nominale="22",
                prise_type_combo_ccs="True",
            ),
            row(id_pdc_local="", id_pdc_itinerance="", nom_station="Location fictive"),
            row(id_pdc_local="FR*V75*MOTO", station_deux_roues="True"),
            row(id_pdc_local="FR*V75*EF", prise_type_2="False", prise_type_ef="True"),
            row(id_pdc_local="FR*OTHER*1", nom_operateur="Autre CPO"),
            row(id_pdc_local="FR*ROAMING*1", nom_enseigne="Autre réseau"),
        ]
        payload = build(rows, official_tariffs(), source={"url": "test"}, generated_at="2026-08-24T00:00:00Z")
        stats = payload["stats"]
        self.assertEqual(stats["sourceRowCount"], 7)
        self.assertEqual(stats["strictOperatorBrandRowCount"], 5)
        self.assertEqual(stats["excludedMissingIdentifierRows"], 1)
        self.assertEqual(stats["excludedMotorcycleRows"], 1)
        self.assertEqual(stats["excludedTeslaIncompatibleRows"], 1)
        self.assertEqual(stats["stationCount"], 1)
        self.assertEqual(stats["chargePointCount"], 2)
        station = payload["stations"][0]
        self.assertEqual(station["operatorSourceValue"], "TOTALENERGIES")
        self.assertEqual(station["brandSourceValue"], "Belib'")
        self.assertEqual({c["serviceClass"] for c in station["configurations"]}, {"flex", "boost"})
        self.assertTrue(payload["scope"]["thirdPartyRoamingStationsExcluded"])
        self.assertFalse(payload["scope"]["parkingFeesIncluded"])


if __name__ == "__main__":
    unittest.main()
