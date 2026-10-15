import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MacPublishedHistoryTest(unittest.TestCase):
    def test_two_byte_exact_mac_catalogues(self):
        manifest = json.loads((ROOT / 'data/tesla/mac/history/two-historical-lots.json').read_text())
        previous, current = manifest['catalogues']
        rows = []
        for item in (previous, current):
            raw = (ROOT / item['path']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256'])
            self.assertEqual(len(raw), item['bytes'])
            stations = json.loads(raw)
            self.assertEqual(len(stations), item['stationCount'])
            ids = [row['id'] for row in stations]
            self.assertEqual(len(ids), len(set(ids)))
            rows.append(set(ids))
        self.assertEqual((previous['stationCount'], current['stationCount']), (1178, 1179))
        self.assertTrue(rows[0].issubset(rows[1]))


if __name__ == '__main__':
    unittest.main()
