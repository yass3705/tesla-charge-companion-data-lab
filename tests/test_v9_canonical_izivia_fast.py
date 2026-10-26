import copy
import gzip
import hashlib
import json
import unittest
from pathlib import Path

from v9_rebuild.canonical_izivia_fast import normalize_izivia_fast_map

ARCHIVE = Path('data/operator_direct/izivia_fast_inventory_france_2026_10_06.json')


class IziviaFastMapCanonicalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = ARCHIVE.read_bytes()
        cls.payload = json.loads(raw)
        cls.sha = hashlib.sha256(raw).hexdigest()

    def test_real_archive_preserves_technical_groups_without_prices(self):
        result = normalize_izivia_fast_map(self.payload, artifact_sha256=self.sha)
        self.assertEqual(len(result['stations']), len(self.payload['stations']))
        self.assertEqual(result['offers'], [])
        self.assertEqual(result['evses'], [])
        self.assertEqual(result['connectors'], [])
        self.assertEqual({row['sourceStationId'] for row in result['stations']},
                         {row['sourceStationId'] for row in self.payload['stations']})
        self.assertEqual([row['rawSourceFields']['evses'] for row in result['stations']],
                         [next(source['evses'] for source in self.payload['stations']
                               if source['sourceStationId'] == row['sourceStationId'])
                          for row in result['stations']])

    def test_all_station_ids_exist_in_archived_national_inventory(self):
        with gzip.open('data/national/france-irve-static-v9/all.json.gz', 'rt') as source:
            national_ids = {row[0] for row in json.load(source)}
        self.assertFalse({row['sourceStationId'] for row in self.payload['stations']} - national_ids)

    def test_reordering_does_not_change_keys(self):
        shuffled = copy.deepcopy(self.payload)
        shuffled['stations'].reverse()
        for row in shuffled['stations']:
            row['evses'].reverse()
        first = normalize_izivia_fast_map(self.payload, artifact_sha256=self.sha)
        second = normalize_izivia_fast_map(shuffled, artifact_sha256=self.sha)
        for section in ('stations', 'evses', 'connectors'):
            self.assertEqual([row['id'] for row in first[section]],
                             [row['id'] for row in second[section]])

    def test_rejects_mismatched_exact_station_identity(self):
        changed = copy.deepcopy(self.payload)
        changed['stations'][0]['canonicalId'] = 'FR:national:another-station'
        with self.assertRaises(ValueError):
            normalize_izivia_fast_map(changed, artifact_sha256=self.sha)

    def test_rejects_invalid_socket_power(self):
        changed = copy.deepcopy(self.payload)
        changed['stations'][0]['evses'][0]['connectors'][0]['powerKw'] = 0
        with self.assertRaises(ValueError):
            normalize_izivia_fast_map(changed, artifact_sha256=self.sha)


if __name__ == '__main__':
    unittest.main()
