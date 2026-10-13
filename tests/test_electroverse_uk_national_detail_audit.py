import unittest
from collections import defaultdict

from scripts.audit_electroverse_uk_national_details import exact_candidates


class ExactCandidateTest(unittest.TestCase):
    def test_id_gps_connector_power_and_status_must_all_match(self):
        location = {'sourceFile': 'test', 'cpo': 'Example', 'locationId': 'a',
                    'latitude': 51.0, 'longitude': -1.0}
        cpo_evse = {'evseId': 'GB*ABC*E1', 'connectors': [
            {'kind': 'TYPE2', 'maxElectricPowerW': 22000}]}
        by_id = defaultdict(list, {'GBABCE1': [(location, cpo_evse)]})
        source = {'physicalReference': 'GBABC E1', 'status': 'AVAILABLE',
                  'connectors': [{'pk': 'c1', 'standard': {'name': 'IEC_62196_T2'},
                                  'kilowatts': 22}]}
        self.assertEqual(len(exact_candidates(source, (51.0, -1.0), by_id)), 1)
        self.assertEqual(exact_candidates(source, (52.0, -1.0), by_id), [])
        self.assertEqual(exact_candidates({**source, 'status': 'UNKNOWN'}, (51.0, -1.0), by_id), [])
        source['connectors'][0]['kilowatts'] = 50
        self.assertEqual(exact_candidates(source, (51.0, -1.0), by_id), [])


if __name__ == '__main__':
    unittest.main()
