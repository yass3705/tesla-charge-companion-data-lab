import gzip
import json
import tempfile
import unittest
from pathlib import Path

from scripts.germany_bnetza_catalog import build, discover_csv_urls, parse_csv


SAMPLE = """Hinweis;Quelle\nBetreiber;Straße;Hausnummer;Postleitzahl;Ort;Bundesland;Kreis/kreisfreie Stadt;Breitengrad;Längengrad;Inbetriebnahmedatum;Anschlussleistung;Art der Ladeeinrichtung;Anzahl Ladepunkte;Steckertypen1;P1 [kW];EVSE-ID1;Steckertypen2;P2 [kW];EVSE-ID2\nTest CPO;Hauptstraße;1;10115;Berlin;Berlin;Berlin;52,5200;13,4050;01.01.2026;350;Schnellladeeinrichtung;2;DC Kupplung Combo;175;DE*ABC*E1;DC Kupplung Combo;175;DE*ABC*E2\n"""


class GermanyBNetzATest(unittest.TestCase):
    def test_discovers_latest_csv(self):
        page = '''<a href="/x/Ladesaeulenregister_BNetzA_2026-07-07.csv">old</a>
        <a href="https://data.example/Ladesaeulenregister_BNetzA_2026-07-28.csv">new</a>'''
        urls = discover_csv_urls(page, "https://www.bundesnetzagentur.de/base/")
        self.assertTrue(urls[0].endswith("2026-07-28.csv"))

    def test_normalizes_bnetza_row(self):
        stations, meta = parse_csv(SAMPLE.encode("utf-8"))
        self.assertEqual(len(stations), 1)
        station = stations[0]
        self.assertEqual(station["operator"], "Test CPO")
        self.assertEqual(station["address"]["countryCode"], "DE")
        self.assertAlmostEqual(station["coordinates"]["latitude"], 52.52)
        self.assertAlmostEqual(station["coordinates"]["longitude"], 13.405)
        self.assertEqual(station["chargePointCount"], 2)
        self.assertEqual([c["powerKw"] for c in station["connectors"]], [175.0, 175.0])
        self.assertEqual([c["evseId"] for c in station["connectors"]], ["DE*ABC*E1", "DE*ABC*E2"])
        self.assertEqual(station["operationalStatus"], "unknown")
        self.assertEqual(meta["headerRow"], 2)

    def test_build_marks_static_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.csv"
            output = Path(tmp) / "baseline.json.gz"
            source.write_text(SAMPLE, encoding="utf-8")
            result = build(None, output, source)
            self.assertTrue(output.exists())
            self.assertFalse(result["scope"]["dynamicStatusIncluded"])
            self.assertFalse(result["scope"]["tariffsIncluded"])
            self.assertFalse(result["scope"]["teslaExcluded"])
            with gzip.open(output, "rt", encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual(saved["dataset"], "germany-bnetza-static-baseline")
            self.assertEqual(saved["stats"]["stationRows"], 1)
            self.assertEqual(saved["source"]["attribution"], "bundesnetzagentur.de")


if __name__ == "__main__":
    unittest.main()
