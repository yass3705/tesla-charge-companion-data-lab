"""Offline contract tests: Blink CPO identity, public filtering and exact connector pricing."""
import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'scripts/uk_blink_pcpr_collect.py'
spec = importlib.util.spec_from_file_location('blink', SCRIPT)
blink = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blink)


class BlinkPcprTests(unittest.TestCase):
    def test_exact_connector_and_gbp_gross_price(self):
        loc = {'id': '1', 'country': 'GBR', 'country_code': 'GB', 'party_id': 'BLI',
               'operator': {'name': 'Blink Charging'}, 'publish': True,
               'coordinates': {'latitude': '51.5', 'longitude': '-0.1'},
               'evses': [{'evse_id': 'GB*BLI*E1', 'connectors': [
                   {'id': '1', 'max_electric_power': 22000, 'tariff_ids': ['T1']},
                   {'id': '2', 'max_electric_power': 50000, 'tariff_ids': ['UNKNOWN']}]}]}
        tariff = {'id': 'T1', 'country_code': 'GB', 'party_id': 'BLI', 'currency': 'GBP',
                  'elements': [{'price_components': [{'type': 'ENERGY', 'price': 0.5, 'step_size': 1}]}]}
        doc, audit = blink.stage([loc], [tariff], '2026-10-09T00:00:00+00:00')
        assert audit['pricedExactConnectors'] == 1
        assert audit['unpricedPublicConnectors'] == 1
        src = doc['sources'][0]
        assert src['locations'][0]['evses'][0]['connectors'][0]['tariff_ids'] == ['T1']
        assert src['locations'][0]['evses'][0]['connectors'][1]['tariff_ids'] == []
        assert src['tariffs'][0]['elements'][0]['price_components'][0]['price'] == 0.6
        assert src['tariffs'][0]['elements'][0]['price_components'][0]['vat'] is None

    def test_wrong_operator_must_fail(self):
        loc = {'id': '2', 'country': 'GBR', 'country_code': 'GB', 'party_id': 'CPI',
               'operator': {'name': 'ChargePoint'}, 'publish': True,
               'coordinates': {'latitude': '51.5', 'longitude': '-0.1'}, 'evses': []}
        with self.assertRaisesRegex(RuntimeError, 'No public Blink'):
            blink.stage([loc], [], 'now')

    def test_private_and_unknown_component(self):
        loc = {'id': '3', 'country': 'GBR', 'country_code': 'GB', 'party_id': 'BLI',
               'operator': {'name': 'Blink'}, 'publish': True,
               'parking_type': 'PRIVATE', 'coordinates': {'latitude': 51.5, 'longitude': -0.1}}
        assert blink.eligible_location(loc) == 'restricted_access'
        t = {'country_code': 'GB', 'currency': 'GBP',
             'elements': [{'price_components': [{'type': 'UNKNOWN', 'price': 0.1}]}]}
        assert blink.make_tariff(t)[1] == 'unsupported_component'


if __name__ == '__main__':
    unittest.main()
