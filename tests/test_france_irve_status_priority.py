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


def static_row():
    row = {field: "" for field in FIELDS}
    row.update({
        "nom_amenageur": "Allego",
        "nom_operateur": "Allego",
        "nom_enseigne": "Allego",
        "id_station_itinerance": "FRALLS0001",
        "id_pdc_itinerance": "FRALLEGO8002611",
        "nom_station": "Allego test",
        "adresse_station": "1 rue Test 78000 Versailles",
        "code_insee_commune": "78646",
        "coordonneesXY": "[2.13, 48.80]",
        "puissance_nominale": "150",
        "prise_type_combo_ccs": "true",
        "gratuit": "false",
        "date_maj": "2026-08-28",
    })
    return row


class FranceIrveStatusPriorityTests(unittest.TestCase):
    def build(self, enrichment_order):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            static = root / "static.csv"
            with static.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";")
                writer.writeheader()
                writer.writerow(static_row())

            paths = {}
            payloads = {
                "direct": {
                    "schemaVersion": "1.0",
                    "provider": "Allego",
                    "sourceKind": "cpo_direct",
                    "records": [{
                        "idPdcItinerance": "FRALLEGO8002611",
                        "status": "unknown",
                    }],
                },
                "dynamic": {
                    "schemaVersion": "1.0",
                    "provider": "PAN IRVE dynamique",
                    "sourceKind": "irve_dynamic",
                    "records": [{
                        "idPdcItinerance": "FRALLEGO8002611",
                        "etat_pdc": "hors_service",
                    }],
                },
            }
            for name, payload in payloads.items():
                path = root / f"{name}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                paths[name] = path

            return fic.build(str(static), [paths[name] for name in enrichment_order])

    def test_unknown_direct_never_masks_dynamic_fallback(self):
        for order in (("direct", "dynamic"), ("dynamic", "direct")):
            with self.subTest(order=order):
                payload = self.build(order)
                status = payload["chargePoints"][0]["status"]
                self.assertEqual(status["state"], "out_of_service")
                self.assertEqual(status["sourceKind"], "irve_dynamic")


if __name__ == "__main__":
    unittest.main()
