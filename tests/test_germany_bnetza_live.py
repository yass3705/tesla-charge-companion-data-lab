import unittest

from scripts import germany_bnetza_live as live


class GermanyBNetzALiveLayoutTest(unittest.TestCase):
    def test_finds_header_after_long_preamble(self):
        rows = [["Ladesäulenregister Bundesnetzagentur", ""]]
        rows += [[f"Hinweis {i}", ""] for i in range(25)]
        rows.append([
            "Betreiber (Unternehmen)",
            "Straße",
            "Breitengrad [WGS84]",
            "Längengrad [WGS84]",
        ])
        self.assertEqual(live.find_live_header_row(rows), 26)

    def test_rejects_descriptive_rows(self):
        rows = [["Betreiberinformationen", "Stand Juli 2026"], ["Breitengrad erklärt", ""]]
        with self.assertRaises(RuntimeError):
            live.find_live_header_row(rows)


if __name__ == "__main__":
    unittest.main()
