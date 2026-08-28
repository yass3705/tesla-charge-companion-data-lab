import csv
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from scripts.france_irve_canonical import build, canonicalize, is_tesla


FIELDS = [
    "nom_amenageur", "nom_operateur", "nom_enseigne", "id_station_itinerance",
    "id_station_local", "nom_station", "implantation_station", "adresse_station",
    "code_insee_commune", "coordonneesXY", "nbre_pdc", "id_pdc_itinerance",
    "id_pdc_local", "puissance_nominale", "prise_type_ef", "prise_type_2",
    "prise_type_combo_ccs", "prise_type_chademo", "prise_type_autre", "gratuit",
    "paiement_acte", "paiement_cb", "paiement_autre", "tarification",
    "condition_acces", "reservation", "horaires", "date_mise_en_service",
    "date_maj", "cable_t2_attache"
]


def row(**overrides):
    base = {field: "" for field in FIELDS}
    base.update({
        "nom_operateur": "Example CPO",
        "nom_enseigne": "Example",
        "id_station_itinerance": "FREXAS0001",
        "nom_station": "Example station",
        "implantation_station": "Voirie",
        "adresse_station": "1 rue Test 75000 Paris",
        "coordonneesXY": "[2.35,48.85]",
        "nbre_pdc": "1",
        "id_pdc_itinerance": "FREXAE0001",
        "puissance_nominale": "150",
        "prise_type_combo_ccs": "true",
        "gratuit": "false",
        "paiement_acte": "true",
        "condition_acces": "Accès libre",
        "reservation": "false",
        "horaires": "24/7",
        "date_maj": "2026-08-27",
    })
    base.update(overrides)
    return base


class FranceIrveCanonicalTests(unittest.TestCase):
    def test_tesla_is_excluded_by_identity(self):
        self.assertTrue(is_tesla(row(nom_operateur="Tesla France")))
        self.assertFalse(is_tesla(row(nom_operateur="Example CPO")))

    def test_simple_energy_tariff_is_safe_fallback(self):
        record = canonicalize(row(tarification="0,39 €/kWh"))
        fallback = record["tariff_fallback"]
        self.assertEqual(fallback["parse_status"], "parsed")
        self.assertEqual(fallback["kind"], "energy")
        self.assertAlmostEqual(fallback["energy_eur_per_kwh"], 0.39)
        self.assertEqual(record["status"]["value"], "inconnu")
        self.assertEqual(record["tariff_offers"], [])

    def test_subscription_or_multi_component_tariff_is_text_only(self):
        subscription = canonicalize(row(tarification="Non-abonné : 0,39 €/kWh"))
        mixed = canonicalize(row(tarification="0,39 €/kWh + 0,05 €/minute"))
        self.assertEqual(subscription["tariff_fallback"]["parse_status"], "text_only")
        self.assertEqual(mixed["tariff_fallback"]["parse_status"], "text_only")

    def test_free_flag_is_machine_readable(self):
        record = canonicalize(row(gratuit="true", tarification="Recharge gratuite"))
        self.assertEqual(record["tariff_fallback"]["parse_status"], "parsed")
        self.assertEqual(record["tariff_fallback"]["kind"], "free")
        self.assertEqual(record["tariff_fallback"]["energy_eur_per_kwh"], 0.0)

    def test_build_streams_non_tesla_and_deduplicates_pdc(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "irve.csv"
            output = root / "canonical.jsonl.gz"
            stats_path = root / "stats.json"
            rows = [
                row(id_pdc_itinerance="FREXAE0001", tarification="0,39 €/kWh"),
                row(id_pdc_itinerance="FREXAE0001", tarification="0,39 €/kWh"),
                row(id_pdc_itinerance="FRTSLE0001", nom_operateur="Tesla", nom_enseigne="Tesla"),
                row(id_pdc_itinerance="FREXAE0002", tarification="Voir application"),
            ]
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)

            stats = build(source, output, stats_path)
            self.assertEqual(stats["rows_seen"], 4)
            self.assertEqual(stats["rows_written"], 2)
            self.assertEqual(stats["tesla_rows_excluded"], 1)
            self.assertEqual(stats["duplicate_pdc_ids_skipped"], 1)

            with gzip.open(output, "rt", encoding="utf-8") as handle:
                records = [json.loads(line) for line in handle]
            self.assertEqual({r["pdc"]["id"] for r in records}, {"FREXAE0001", "FREXAE0002"})


if __name__ == "__main__":
    unittest.main()
