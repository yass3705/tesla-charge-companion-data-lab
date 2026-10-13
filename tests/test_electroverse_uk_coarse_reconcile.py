import sys
import unittest
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from reconcile_electroverse_uk_national_tiles import CELL, nearby
import math


class CoarseReconcileTests(unittest.TestCase):
    def test_nearby_is_discovery_only_and_keeps_ambiguity(self):
        grid = defaultdict(list)
        for identifier, longitude in [('one', -0.1000), ('two', -0.1005), ('far', -0.11)]:
            seed = {'latitude': 51.5, 'longitude': longitude, 'sourceFile': 'fixture',
                    'cpo': 'CPO', 'locationId': identifier}
            grid[(math.floor(seed['latitude'] / CELL), math.floor(seed['longitude'] / CELL))].append(seed)
        result = nearby({'latitude': 51.5, 'longitude': -0.1002}, grid)
        self.assertEqual([x['locationId'] for x in result], ['one', 'two'])
        self.assertTrue(all('tariff' not in x and 'evseId' not in x for x in result))


if __name__ == '__main__':
    unittest.main()
