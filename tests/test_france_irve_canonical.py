#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import france_irve_canonical as fic  # noqa: E402


FIELDS = [
    "nom_amenageur", "nom_operateur", "nom_enseigne",
    "id_station_itinerance", "id_station_local", "nom_station",
    "adresse_station", "code_insee_commune", "coordonneesXY",
    "id_pdc_itinerance", "id_pdc_local", "puissance_nominale",
    "prise_type_ef", "prise_type_2", "prise_type_combo_ccs",
    "prise_type_chademo", "prise_type_autre", "gratuit",
    "paiement_acte", "paiement_cb", "paiement_autre", "tarification",
    "condition_acces", "reservation", "horaires", "date_maj",
    "date_mise_en_service", "observations",
]


def row(**overrides):
    base = {
        "nom_amenageur": "Example Owner",
        "nom_operateur": "Example CPO",
        "nom_enseigne": "Example",
        "id_station_itinerance": "FR*EXA*S0001",
        "id_station_local": "S1",
        "nom_station": "Station test",
        "adresse_station": "1 rue Test 78000 Versailles",
        "code_insee_commune": "78646",
        "coordonneesXY": "[2.13, 48.80]",
        "id_pdc_itinerance": "FR*EXA*E0001",
        "id_pdc_local": "E1",
        "puissance_nominale": "150",
        "prise_type_ef": "false",
        "prise_type_2": "true",
        "prise_type_combo_ccs": "true",
        "prise_type_chademo": "false",
        "prise_type_autre": "false",
        "gratuit": "false",
        "paiement_acte": "true",
        "paiement_cb": "true",
        "paiement_autre": "false",
        "tarification": "0,39 €/kWh",
        "condition_acces": "Accès libre",
        "reservation": "false",
        "horaires": "24/7",
        "date_maj": "2026-08-28",
        "date_mise_en_service": "2026-01-01",
        "observations": "",
    }
    base.update(overrides)
    return base


class FranceIrveCanonicalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write_static(self, rows):
        path = self.root / "static.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        return path

    def write_enrichment(self, name, source_kind, records):
        path = self.root / f"{name}.json"
        path.write_text(json.dumps({
            "schemaVersion": "1.0",
            "provider": name,
            "sourceKind": source_kind,
            "records": records,
        }), encoding="utf-8")
        return path

    def build(self, rows, enrichments=()):
        static = self.write_static(rows)
        return fic.build(str(static), list(enrichments))

    def test_tesla_identity_rows_are_excluded(self):
        payload = self.build([
            row(id_pdc_itinerance="FR*EXA*E1"),
            row(nom_operateur="Tesla France", id_pdc_itinerance="FR*TES*E1"),
        ])
        self.assertEqual(len(payload["chargePoints"]), 1)
        self.assertEqual(payload["summary"]["tesla_rows_excluded"], 1)

    def test_non_tesla_is_kept_with_pdc_granularity(self):
        payload = self.build([row()])
        p = payload["chargePoints"][0]
        self.assertEqual(p["idPdcItinerance"], "FR*EXA*E0001")
        self.assertEqual(p["nominalPowerKw"], 150.0)
        self.assertIn("CCS", p["connectors"])
        self.assertEqual(payload["rules"]["statusGranularity"], "PDC")

    def test_direct_cpo_status_overrides_irve_dynamic(self):
        dynamic = self.write_enrichment("PAN IRVE dynamique", "irve_dynamic", [{
            "idPdcItinerance": "FR*EXA*E0001",
            "etat_pdc": "hors_service",
            "occupation_pdc": "occupé",
        }])
        direct = self.write_enrichment("Example CPO", "cpo_direct", [{
            "idPdcItinerance": "FR*EXA*E0001",
            "status": "en_service",
        }])
        payload = self.build([row()], [dynamic, direct])
        status = payload["chargePoints"][0]["status"]
        self.assertEqual(status["state"], "in_service")
        self.assertEqual(status["sourceKind"], "cpo_direct")

    def test_irve_dynamic_fills_status_when_direct_missing(self):
        dynamic = self.write_enrichment("PAN IRVE dynamique", "irve_dynamic", [{
            "idPdcItinerance": "FR*EXA*E0001",
            "etat_pdc": "hors_service",
        }])
        payload = self.build([row()], [dynamic])
        self.assertEqual(payload["chargePoints"][0]["status"]["state"], "out_of_service")

    def test_occupancy_is_ignored(self):
        dynamic = self.write_enrichment("PAN IRVE dynamique", "irve_dynamic", [{
            "idPdcItinerance": "FR*EXA*E0001",
            "etat_pdc": "en_service",
            "occupation_pdc": "occupé",
        }])
        payload = self.build([row()], [dynamic])
        point = payload["chargePoints"][0]
        self.assertEqual(point["status"]["state"], "in_service")
        self.assertNotIn("occupation", point)
        self.assertFalse(payload["rules"]["occupancyUsed"])

    def test_direct_electroverse_and_electra_tariffs_coexist(self):
        direct = self.write_enrichment("Example CPO", "cpo_direct", [{
            "idPdcItinerance": "FR*EXA*E0001",
            "offers": [
                {"type": "DIRECT_PUBLIC", "energyEurPerKwh": 0.39},
                {"type": "CPO_SUBSCRIPTION", "plan": "Member", "energyEurPerKwh": 0.29},
            ],
        }])
        electroverse = self.write_enrichment("Electroverse", "electroverse", [{
            "idPdcItinerance": "FR*EXA*E0001",
            "status": "hors_service",
            "offers": [{"energyEurPerKwh": 0.44}],
        }])
        electra = self.write_enrichment("Electra", "electra", [{
            "idPdcItinerance": "FR*EXA*E0001",
            "status": "hors_service",
            "offers": [{"energyEurPerKwh": 0.41}],
        }])
        payload = self.build([row()], [direct, electroverse, electra])
        point = payload["chargePoints"][0]
        self.assertEqual(
            {o["type"] for o in point["tariffOffers"]},
            {"DIRECT_PUBLIC", "CPO_SUBSCRIPTION", "ELECTROVERSE", "ELECTRA"},
        )
        self.assertEqual(point["status"]["state"], "unknown")

    def test_irve_tariff_is_used_only_as_last_resort(self):
        payload = self.build([row(tarification="0,39 €/kWh")])
        offers = payload["chargePoints"][0]["tariffOffers"]
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["type"], "IRVE_FALLBACK_PARSED")
        self.assertEqual(offers[0]["energyEurPerKwh"], 0.39)

        direct = self.write_enrichment("Example CPO", "cpo_direct", [{
            "idPdcItinerance": "FR*EXA*E0001",
            "offers": [{"type": "DIRECT_PUBLIC", "energyEurPerKwh": 0.45}],
        }])
        payload = self.build([row(tarification="0,39 €/kWh")], [direct])
        types = [o["type"] for o in payload["chargePoints"][0]["tariffOffers"]]
        self.assertEqual(types, ["DIRECT_PUBLIC"])

    def test_ambiguous_irve_tariff_is_display_only(self):
        payload = self.build([row(tarification="0,39 €/kWh + 0,10 €/minute de stationnement")])
        point = payload["chargePoints"][0]
        self.assertEqual(point["tariffOffers"], [])
        self.assertEqual(
            point["irveTariff"]["rawText"],
            "0,39 €/kWh + 0,10 €/minute de stationnement",
        )
        self.assertIsNone(point["irveTariff"]["calculativeFallback"])

    def test_free_irve_flag_is_safe_zero_price_fallback(self):
        payload = self.build([row(gratuit="true", tarification="")])
        offer = payload["chargePoints"][0]["tariffOffers"][0]
        self.assertEqual(offer["type"], "IRVE_FALLBACK_PARSED")
        self.assertEqual(offer["energyEurPerKwh"], 0.0)

    def test_status_stays_independent_for_two_pdcs_same_station(self):
        rows = [
            row(id_pdc_itinerance="FR*EXA*E1", puissance_nominale="22"),
            row(id_pdc_itinerance="FR*EXA*E2", id_pdc_local="E2", puissance_nominale="150"),
        ]
        direct = self.write_enrichment("Example CPO", "cpo_direct", [
            {"idPdcItinerance": "FR*EXA*E1", "status": "en_service"},
            {"idPdcItinerance": "FR*EXA*E2", "status": "hors_service"},
        ])
        payload = self.build(rows, [direct])
        statuses = {
            p["idPdcItinerance"]: p["status"]["state"]
            for p in payload["chargePoints"]
        }
        self.assertEqual(statuses["FR*EXA*E1"], "in_service")
        self.assertEqual(statuses["FR*EXA*E2"], "out_of_service")

    def test_unmatched_enrichment_never_drops_irve_point(self):
        direct = self.write_enrichment("Example CPO", "cpo_direct", [{
            "idPdcItinerance": "FR*NOPE*E9999",
            "status": "en_service",
        }])
        payload = self.build([row()], [direct])
        self.assertEqual(len(payload["chargePoints"]), 1)
        stats = payload["summary"]["enrichments"][str(direct)]
        self.assertEqual(stats["unmatched"], 1)


if __name__ == "__main__":
    unittest.main()
