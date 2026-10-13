import unittest
from collections import defaultdict

from scripts.audit_electroverse_uk_national_details import exact_candidates, gps_group_candidates


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

    def test_gps_group_needs_same_kind_power_count_and_price(self):
        seed = {'sourceFile': 'test', 'locationId': 'loc', 'latitude': 51.0,
                'longitude': -1.0, 'evses': [
                    {'status': 'AVAILABLE', 'connectors': [{'kind': 'TYPE2', 'maxElectricPowerW': 22000}]},
                    {'status': 'AVAILABLE', 'connectors': [{'kind': 'TYPE2', 'maxElectricPowerW': 22000}]},
                ]}
        connector = lambda pk, rate: {'pk': pk, 'standard': {'name': 'IEC_62196_T2'},
                                       'kilowatts': 22, 'priceComponents': [
                                           {'__typename': 'ConsumptionRate', 'formattedValue': rate}]}
        row = {'electroversePk': '42', 'nearbyCpoSeeds': [
            {'sourceFile': 'test', 'locationId': 'loc'}], 'source': {
                'coordinates': {'latitude': 51.0, 'longitude': -1.0}, 'evses': [
                    {'status': 'AVAILABLE', 'connectors': [connector('c1', '£0.50/kWh')]},
                    {'status': 'AVAILABLE', 'connectors': [connector('c2', '£0.50/kWh')]},
                ]}}
        by_id = {('test', 'loc'): seed}
        counts, _ = gps_group_candidates({'42': row}, by_id)
        self.assertEqual(counts['homogeneousGpsKindPowerGroupCandidates'], 1)
        row['source']['evses'][1]['connectors'][0]['priceComponents'][0]['formattedValue'] = '£0.60/kWh'
        counts, _ = gps_group_candidates({'42': row}, by_id)
        self.assertEqual(counts['groupsWithNonHomogeneousEmspPrice'], 1)
        row['source']['coordinates']['latitude'] = 52.0
        counts, _ = gps_group_candidates({'42': row}, by_id)
        self.assertFalse(counts)


if __name__ == '__main__':
    unittest.main()
