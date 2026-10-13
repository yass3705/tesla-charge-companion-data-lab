import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from electra_nl_emsp_national_stage import stage_items


class NationalStageGuardTests(unittest.TestCase):
    def test_exact_evse_keeps_only_allowed_connector_and_source_grid(self):
        station = {'stationId': 'NL:example', 'coordinates': {'latitude': 52, 'longitude': 5}}
        direct = {'evseId': 'NL*EXAMPLE*1', 'status': 'AVAILABLE', 'connectors': [
            {'id': 'ccs', 'standard': 'IEC_62196_T2_COMBO', 'powerKw': 150, 'tariffKeys': ['direct']},
            {'id': 'chademo', 'standard': 'CHADEMO', 'powerKw': 50, 'tariffKeys': ['other']},
        ]}
        location = {'id': 'emsp-location', 'country': 'NL', 'coordinates': station['coordinates'],
                    'evses': [{'evseId': 'NL-EXAMPLE-1', 'status': 'AVAILABLE'}],
                    'chargeTariffs': [{'chargeTariffId': 'emsp', 'currency': 'EUR'}]}
        counts, result = stage_items([location], {'NLEXAMPLE1': [(station, direct)]})
        self.assertEqual(counts['matchedAllowedConnectors'], 1)
        self.assertEqual(result[0]['matchedAllowedEvses'][0]['connectors'], [
            {'id': 'ccs', 'kind': 'CCS', 'powerKw': 150, 'tariffKeys': ['direct']}])
        self.assertEqual(result[0]['chargeTariffs'][0]['chargeTariffId'], 'emsp')

    def test_duplicate_identity_cannot_be_staged(self):
        station = {'coordinates': {'latitude': 52, 'longitude': 5}}
        evse = {'evseId': 'NL*EXAMPLE*1', 'connectors': [{'standard': 'IEC_62196_T2'}]}
        location = {'country': 'NL', 'evses': [{'evseId': 'NL*EXAMPLE*1'}]}
        counts, result = stage_items([location], {'NLEXAMPLE1': [(station, evse), (station, evse)]})
        self.assertEqual(counts['unmatchedOrDuplicateId'], 1)
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
