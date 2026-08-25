import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "labornebleue_station_inventory.py"
spec = importlib.util.spec_from_file_location("labornebleue_station_inventory", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)


def row(station, pdc, power=22.0, network="La Borne Bleue", ccs="false"):
    return {
        "nom_enseigne": network,
        "nom_operateur": "Bouygues Energies & Services",
        "nom_amenageur": "SIPPEREC",
        "nom_station": f"LBB {station}",
        "id_station_itinerance": station,
        "id_pdc_itinerance": pdc,
        "adresse_station": "1 rue du Test 78000 Versailles",
        "coordonneesXY": "[2.13, 48.80]",
        "puissance_nominale": str(power),
        "prise_type_combo_ccs": ccs,
        "prise_type_chademo": "false",
        "date_maj": "2026-08-25",
    }


class LaBorneBleueInventoryTests(unittest.TestCase):
    def test_strict_network_identity(self):
        self.assertTrue(mod.is_lbb(row("FRLBB1", "FRLBB1*1")))
        self.assertFalse(mod.is_lbb(row("FRECO1", "FRECO1*1", network="Ecocharge77")))
        self.assertFalse(mod.is_lbb({"nom_enseigne": "Autre", "nom_operateur": "SIPPEREC"}))

    def test_official_tariff_models(self):
        public_74 = mod.public_exact("AC", 7.4)
        sub_74 = mod.subscriber_exact("AC", 7.4)
        self.assertAlmostEqual(public_74["windows"][0]["ratePerMinute"] * 60, 4.50)
        self.assertAlmostEqual(public_74["windows"][1]["ratePerMinute"] * 60, 3.50)
        self.assertAlmostEqual(sub_74["windows"][0]["ratePerMinute"] * 60, 3.50)
        self.assertAlmostEqual(sub_74["windows"][1]["ratePerMinute"] * 60, 2.50)
        self.assertEqual(sub_74["windows"][1]["capEur"], 12.0)
        self.assertEqual(mod.public_exact("DC", 50), None)
        self.assertEqual(mod.public_exact("DC", 51)["pricePerKwh"], 0.50)
        self.assertEqual(mod.subscriber_exact("DC", 51)["pricePerKwh"], 0.45)
        self.assertEqual(mod.subscriber_exact("DC", 51)["afterRatePerMinute"], 0.20)

    def test_build_is_direct_only_and_subscription_is_explicit(self):
        rows = []
        for s in range(200):
            sid = f"FRLBB{s:05d}"
            for p in range(4):
                rows.append(row(sid, f"{sid}*P{p}", power=22))
        rows.append(row("FRECO00001", "FRECO00001*P1", power=22, network="Ecocharge77"))
        payload = mod.build(rows)
        self.assertEqual(payload["counts"]["strictSourceStations"], 200)
        self.assertEqual(payload["counts"]["strictSourceChargePoints"], 800)
        self.assertEqual(payload["counts"]["publishedStations"], 200)
        self.assertEqual(payload["counts"]["publishedConfigurations"], 400)
        self.assertFalse(payload["scope"]["partnerLocationsIncluded"])
        self.assertFalse(payload["scope"]["partnerTariffsIncluded"])
        self.assertFalse(payload["scope"]["subscriptionDiscountAtPartnerOperators"])
        configs = payload["stations"][0]["configurations"]
        self.assertEqual({c["subscriptionId"] for c in configs}, {None, "labornebleue-annual"})
        self.assertTrue(all(c["labornebleueOwnNetworkOnly"] for c in configs))


if __name__ == "__main__":
    unittest.main()
