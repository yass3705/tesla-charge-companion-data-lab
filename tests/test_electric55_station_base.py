#!/usr/bin/env python3
from __future__ import annotations

import unittest

from electric55_station_base import build, is_e55c_operator, parse_tariff


class Electric55StationBaseTests(unittest.TestCase):
    def test_operator_filter_is_strict(self) -> None:
        self.assertTrue(is_e55c_operator("Electric 55 Charging"))
        self.assertTrue(is_e55c_operator("E55C"))
        self.assertFalse(is_e55c_operator("Collectivité supervisée par E55C"))
        self.assertFalse(is_e55c_operator("Freshmile"))

    def test_day_night_minute_tariff(self) -> None:
        parsed = parse_tariff(
            "0,09 €/min de 07h à 23h ; 0,06 €/min de 23h à 07h",
            False,
        )
        self.assertEqual(parsed["status"], "parsed_official_station_text")
        self.assertEqual(len(parsed["rules"]), 2)
        self.assertEqual(parsed["rules"][0]["start"], "07:00")
        self.assertEqual(parsed["rules"][0]["timeEurPerMinute"], 0.09)
        self.assertEqual(parsed["rules"][1]["end"], "07:00")
        self.assertEqual(parsed["rules"][1]["timeEurPerMinute"], 0.06)

    def test_build_groups_evse_and_excludes_other_cpo(self) -> None:
        common = {
            "nom_station": "Station test",
            "adresse_station": "1 rue Test 75001 Paris",
            "coordonneesxy": "[2.3522,48.8566]",
            "id_station_itinerance": "FR55CP0001",
            "nom_enseigne": "E55C",
            "nom_amenageur": "Ville test",
            "implantation_station": "Voirie",
            "condition_acces": "Accès libre",
            "horaires": "24/7",
            "nbre_pdc": "2",
            "paiement_acte": "true",
            "paiement_cb": "false",
            "paiement_autre": "true",
            "gratuit": "false",
            "reservation": "false",
            "prise_type_ef": "false",
            "prise_type_2": "true",
            "prise_type_combo_ccs": "false",
            "prise_type_chademo": "false",
            "prise_type_autre": "false",
            "puissance_nominale": "22",
            "tarification": "0,09 €/min de 07h à 23h ; 0,06 €/min de 23h à 07h",
            "date_maj": "2026-08-23",
        }
        rows = [
            {**common, "nom_operateur": "Electric 55 Charging", "id_pdc_itinerance": "FR55CE00011"},
            {**common, "nom_operateur": "E55C", "id_pdc_itinerance": "FR55CE00012"},
            {**common, "nom_operateur": "Autre CPO", "id_pdc_itinerance": "FROTHE00013"},
        ]
        payload = build(
            rows,
            source={"lastModified": "2026-08-23T00:00:00Z", "sha256": "test"},
        )
        self.assertEqual(payload["stats"]["sourceRowCount"], 3)
        self.assertEqual(payload["stats"]["excludedNonE55cOperatorRows"], 1)
        self.assertEqual(payload["stats"]["stationCount"], 1)
        self.assertEqual(payload["stats"]["chargePointCount"], 2)
        station = payload["stations"][0]
        self.assertEqual(station["coordinates"], {"latitude": 48.8566, "longitude": 2.3522})
        self.assertEqual(station["chargePointCount"], 2)
        self.assertEqual(station["offers"][0]["stalls"], 2)
        self.assertFalse(payload["scope"]["dynamicStatusIncluded"])


if __name__ == "__main__":
    unittest.main()
