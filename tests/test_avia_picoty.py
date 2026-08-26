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
            "tarification": "Paiement direct : 0,59 €/kWh",
        },
        {
            "id_station_itinerance": "FR*PY2*S0001",
            "id_pdc_itinerance": "FR*PY2*E0002",
            "nom_station": "AVIA VOLT Test",
            "puissance_nominale": "22",
            "prise_type_2": "true",
            "tarification": "Paiement direct : 0,59 €/kWh",
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


def test_brand_alone_does_not_prove_picoty_cpo():
    rows = [
        {
            "id_station_itinerance": "FR*AAA*S0001",
            "id_pdc_itinerance": "FR*AAA*E0001",
            "nom_operateur": "Other CPO",
            "nom_enseigne": "AVIA VOLT",
        }
    ]
    dataset = mod.build(rows, "fixture")
    assert dataset["stats"]["stations"] == 0
    assert dataset["stats"]["picoty_rows"] == 0


def test_explicit_operator_picoty_is_accepted_when_prefix_is_missing():
    rows = [
        {
            "id_station_itinerance": "LOCAL-STATION-1",
            "id_pdc_itinerance": "LOCAL-EVSE-1",
            "nom_operateur": "PICOTY SA",
            "nom_enseigne": "AVIA VOLT",
        }
    ]
    dataset = mod.build(rows, "fixture")
    assert dataset["stats"]["stations"] == 1


def test_explicit_direct_irve_kwh_tariff_can_be_parsed():
    tariff = mod.parse_direct_tariff({"tarification": "Paiement direct : 0,59 €/kWh"})
    assert tariff["status"] == "verified_from_irve_direct_text"
    assert tariff["eur_per_kwh"] == 0.59
    assert tariff["source"] == "IRVE.tarification"


def test_roaming_or_unlabelled_prices_are_not_inferred_as_direct():
    samples = [
        "Tarif selon opérateur de mobilité",
        "0,65 €/kWh avec badge Chargemap",
        "0,59 €/kWh",
        "Tarif Ulys : 0,42 €/kWh",
    ]
    for text in samples:
        tariff = mod.parse_direct_tariff({"tarification": text})
        assert tariff["status"] == "unknown"
        assert tariff["eur_per_kwh"] is None


def test_coordinates_are_parsed_from_irve_coordonneesxy():
    lat, lon = mod.parse_coordinates({"coordonneesXY": "[2.1234, 48.5678]"})
    assert lat == 48.5678
    assert lon == 2.1234


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
