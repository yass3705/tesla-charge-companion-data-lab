import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "etotem_direct_station_inventory.py"
spec = importlib.util.spec_from_file_location("etotem_inventory", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class EtotemInventoryTests(unittest.TestCase):
    def test_operator_filter_is_strict(self):
        self.assertTrue(mod.is_etotem_operator({"nom_operateur": "E-TOTEM"}))
        self.assertTrue(mod.is_etotem_operator({"nom_operateur": "e Totem SAS"}))
        self.assertFalse(mod.is_etotem_operator({"nom_operateur": "EFFIA"}))
        self.assertFalse(mod.is_etotem_operator({"nom_operateur": "Carrefour Energies"}))
        self.assertFalse(mod.is_etotem_operator({"nom_operateur": ""}))

    def test_tariff_hints_extract_energy_and_duration(self):
        hints = mod.extract_tariff_hints("Recharge 0,49 €/kWh. Post-charge : 3 € / 15 min")
        self.assertEqual(hints["pricePerKwhCandidatesEur"], [0.49])
        self.assertEqual(hints["durationFeeCandidates"][0]["priceEur"], 3.0)
        self.assertEqual(hints["durationFeeCandidates"][0]["minutes"], 15)

    def test_build_inventory_drops_non_etotem_rows_and_groups_pdcs(self):
        dataset = {"id": "d1", "title": "IRVE e-Totem Infrastructures"}
        resource = {"id": "r1", "url": "https://example.test/r1.csv"}
        base = {
            "nom_operateur": "E-TOTEM",
            "id_station_itinerance": "FRETIP12345A",
            "nom_station": "e-Totem - Test",
            "nom_enseigne": "Réseau e-Totem Infrastructures",
            "nom_amenageur": "E-TOTEM",
            "adresse_station": "1 rue Test",
            "code_insee_commune": "12345",
            "coordonneesXY": "[2.1,48.1]",
            "horaires": "24/7",
            "condition_acces": "Accès libre",
            "paiement_acte": "true",
            "paiement_cb": "true",
            "gratuit": "false",
            "prise_type_2": "true",
        }
        row1 = dict(base, id_pdc_itinerance="FRETIE12345A11", puissance_nominale="22", tarification="0,39 €/kWh")
        row2 = dict(base, id_pdc_itinerance="FRETIE12345A12", puissance_nominale="180", tarification="0,49 €/kWh", prise_type_combo_ccs="true")
        other = dict(base, nom_operateur="EFFIA", id_station_itinerance="FRP01P99999A", id_pdc_itinerance="FRP01E99999A1")
        payload = mod.build_inventory([(dataset, resource, row1), (dataset, resource, row2), (dataset, resource, other)])
        self.assertEqual(payload["counts"]["stationCount"], 1)
        self.assertEqual(payload["counts"]["pdcCount"], 2)
        station = payload["stations"][0]
        self.assertEqual(station["stationId"], "FRETIP12345A")
        self.assertEqual(station["maxPowerKw"], 180.0)
        self.assertEqual(station["tariffHints"]["pricePerKwhCandidatesEur"], [0.39, 0.49])
        self.assertEqual(station["latitude"], 48.1)
        self.assertEqual(station["longitude"], 2.1)

    def test_csv_semicolon_detection(self):
        content = b"nom_operateur;id_station_itinerance;id_pdc_itinerance\nE-TOTEM;FRETIP1;FRETIE1\n"
        rows = mod.read_csv_rows(content)
        self.assertEqual(rows[0]["nom_operateur"], "E-TOTEM")
        self.assertEqual(rows[0]["id_station_itinerance"], "FRETIP1")


if __name__ == "__main__":
    unittest.main()
