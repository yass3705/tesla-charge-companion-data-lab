import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from electroverse_uk_national_seeds import seeds_for_dataset


class UkNationalSeedTests(unittest.TestCase):
    def test_only_public_active_allowed_connectors(self):
        def location(identifier, published=True):
            return {'id': identifier, 'country_code': 'GB', 'publish': published,
                    'coordinates': {'latitude': '51.5', 'longitude': '-0.1'},
                    'evses': [{'evse_id': identifier, 'status': 'AVAILABLE', 'connectors': [
                        {'id': 'ccs', 'standard': 'IEC_62196_T2_COMBO'},
                        {'id': 'chademo', 'standard': 'CHADEMO'}]},
                        {'evse_id': 'inactive', 'status': 'OUTOFORDER', 'connectors': [
                            {'id': 't2', 'standard': 'IEC_62196_T2'}]}]}
        source = {'sources': [{'name': 'Fixture', 'locations': [location('public'), location('private', False)]}]}
        rows, counts = seeds_for_dataset(source, 'fixture')
        self.assertEqual(counts['eligibleLocations'], 1)
        self.assertEqual(rows[0]['locationId'], 'public')
        self.assertEqual(rows[0]['evses'][0]['connectors'], [
            {'id': 'ccs', 'kind': 'CCS', 'maxElectricPowerW': None}])


if __name__ == '__main__':
    unittest.main()
