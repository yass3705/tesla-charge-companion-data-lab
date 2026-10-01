import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from france_irve_status_belib import normalize_belib, normalize_belib_status


class BelibStatusAdapterTests(unittest.TestCase):
    def test_status_mapping_ignores_occupation(self):
        self.assertEqual(normalize_belib_status("Disponible"), "in_service")
        self.assertEqual(normalize_belib_status("Occupé (en charge)"), "in_service")
        self.assertEqual(normalize_belib_status("Réservé"), "in_service")
        self.assertEqual(normalize_belib_status("En maintenance"), "out_of_service")
        self.assertEqual(normalize_belib_status("Supprimé"), "out_of_service")
        self.assertEqual(normalize_belib_status("Inconnu"), "unknown")
        self.assertEqual(normalize_belib_status("Mise en service planifiée"), "unknown")
        self.assertEqual(normalize_belib_status("Future valeur inattendue"), "unknown")

    def test_only_current_pan_pdc_are_emitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            static = root / "static.csv"
            source = root / "belib.csv"

            with static.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["id_pdc_itinerance"], delimiter=";")
                w.writeheader()
                w.writerow({"id_pdc_itinerance": "FR*V75*EABC*01*1"})

            with source.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(
                    f,
                    fieldnames=["ID PDC local", "Statut du point de recharge", "Heure mise à jour"],
                    delimiter=";",
                )
                w.writeheader()
                w.writerow({
                    "ID PDC local": "FRV75EABC011",
                    "Statut du point de recharge": "Occupé (en charge)",
                    "Heure mise à jour": "2026-08-28T14:00:00+02:00",
                })
                w.writerow({
                    "ID PDC local": "FR*V75*EABSENT*01*1",
                    "Statut du point de recharge": "Disponible",
                    "Heure mise à jour": "2026-08-28T14:00:00+02:00",
                })

            payload = normalize_belib(str(source), str(static))
            self.assertEqual(len(payload["records"]), 1)
            rec = payload["records"][0]
            self.assertEqual(rec["idPdcItinerance"], "FR*V75*EABC*01*1")
            self.assertEqual(rec["status"], "in_service")
            self.assertEqual(rec["matchConfidence"], "exact")
            self.assertEqual(payload["summary"]["unmatchedCurrentPan"], 1)

    def test_normalization_collision_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            static = root / "static.csv"
            source = root / "belib.csv"

            with static.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["id_pdc_itinerance"], delimiter=";")
                w.writeheader()
                w.writerow({"id_pdc_itinerance": "FR*V75*EABC*01*1"})
                w.writerow({"id_pdc_itinerance": "FRV75EABC011"})

            with source.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(
                    f,
                    fieldnames=["ID PDC local", "Statut du point de recharge", "Heure mise à jour"],
                    delimiter=";",
                )
                w.writeheader()
                w.writerow({
                    "ID PDC local": "FRV75EABC011",
                    "Statut du point de recharge": "Disponible",
                    "Heure mise à jour": "2026-08-28T14:00:00+02:00",
                })

            payload = normalize_belib(str(source), str(static))
            self.assertEqual(payload["records"], [])
            self.assertEqual(payload["summary"]["canonicalNormalizationCollisions"], 1)
            self.assertEqual(payload["summary"]["unmatchedCurrentPan"], 1)


if __name__ == "__main__":
    unittest.main()
