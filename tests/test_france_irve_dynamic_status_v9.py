import csv
import importlib.util
import pathlib
import tempfile


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts/france/build_france_irve_dynamic_status_v9.py"
spec = importlib.util.spec_from_file_location("dynamic_status", SCRIPT)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_daily_status_keeps_static_inventory():
    static = [["FRTEST1", "Station", "", 48.0, 2.0, "TEST", 2, 0,
               [["ac", "AC", "AC", 22, 2, [], ["FRTESTE1", "FRTESTE2"]]], "2026-10-07", "TEST"]]
    with tempfile.TemporaryDirectory() as directory:
        source = pathlib.Path(directory) / "dynamic.csv"
        with source.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["id_pdc_itinerance", "etat_pdc", "horodatage"])
            writer.writeheader()
            writer.writerows([
                {"id_pdc_itinerance": "FRTESTE1", "etat_pdc": "en_service", "horodatage": "2026-10-07T00:00:00Z"},
                {"id_pdc_itinerance": "FRTESTE2", "etat_pdc": "hors_service", "horodatage": "2026-10-07T00:00:00Z"},
                {"id_pdc_itinerance": "FRTESTE2", "etat_pdc": "inconnu", "horodatage": "2026-10-07T01:00:00Z"},
                {"id_pdc_itinerance": "FRMISS", "etat_pdc": "hors_service", "horodatage": "2026-10-07T00:00:00Z"},
            ])
        result = builder.build(static, source, "2026-10-07T02:00:00Z")
    assert len(static[0][8][0][6]) == 2
    assert result["matchedPdc"] == 2
    assert result["unmatchedPdc"] == 1
    assert result["displayExcludedPdc"] == 1
    assert result["states"]["en_service"] == 1
    assert [(row["id_pdc_itinerance"], row["etat_pdc"]) for row in result["records"]] == [
        ("FRTESTE2", "inconnu")]


if __name__ == "__main__":
    test_daily_status_keeps_static_inventory()
    print("Daily dynamic status preserves static IRVE rows and keeps latest PDC state")
