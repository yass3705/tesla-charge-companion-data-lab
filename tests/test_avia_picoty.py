import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_avia_picoty.py"
spec = importlib.util.spec_from_file_location("build_avia_picoty", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_filters_picoty_and_preserves_evse_granularity():
    rows = [
        {
            "id_station_itinerance": "FR*PY2*S0001",
            "id_pdc_itinerance": "FR*PY2*E0001",
            "nom_station": "AVIA VOLT Test",
            "puissance_nominale": "150",
            "prise_type_combo_ccs": "true",
            "tarification": "0,59 €/kWh",
        },
        {
            "id_station_itinerance": "FR*PY2*S0001",
            "id_pdc_itinerance": "FR*PY2*E0002",
            "nom_station": "AVIA VOLT Test",
            "puissance_nominale": "22",
            "prise_type_2": "true",
            "tarification": "0,59 €/kWh",
        },
        {
            "id_station_itinerance": "FR*AAA*S9999",
            "id_pdc_itinerance": "FR*AAA*E9999",
            "nom_station": "Other network",
            "puissance_nominale": "50",
        },
    ]
    dataset = mod.build(rows, "fixture")
    assert dataset["stats"]["stations"] == 1
    assert dataset["stats"]["evses"] == 2
    station = dataset["stations"][0]
    assert station["operator"] == "Picoty"
    assert station["brand"] == "AVIA VOLT"
    assert {e["power_kw"] for e in station["evses"]} == {22.0, 150.0}


def test_explicit_irve_kwh_tariff_can_be_parsed_but_roaming_is_not_inferred():
    tariff = mod.parse_direct_tariff({"tarification": "Paiement direct : 0,59 €/kWh"})
    assert tariff["status"] == "verified_from_irve_text"
    assert tariff["eur_per_kwh"] == 0.59

    unknown = mod.parse_direct_tariff({"tarification": "Tarif selon opérateur de mobilité"})
    assert unknown["status"] == "unknown"
    assert unknown["eur_per_kwh"] is None


def test_unverified_market_candidate_is_never_emitted_as_fallback():
    dataset = mod.build(
        [
            {
                "id_station_itinerance": "FR*PY2*S0002",
                "id_pdc_itinerance": "FR*PY2*E0003",
                "nom_station": "AVIA VOLT No Price",
            }
        ],
        "fixture",
    )
    tariff = dataset["stations"][0]["evses"][0]["direct_tariff"]
    assert tariff["eur_per_kwh"] is None
    assert dataset["policy"]["unverified_0_59_fallback_published"] is False
