import copy
import unittest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/suc_tracker'))
from core import convert_pricing, schedule, compare


def tariff(price=350000, currency='EUR'):
    return {'pricingStatus': 'available', 'pricingUnit': 'kwh', 'currency': currency,
            'prices': [{'days': 127, 'start': 0, 'end': 1440, 'price': price}]}


class TariffTests(unittest.TestCase):
    def test_millionth_units_and_free(self):
        self.assertEqual(convert_pricing(tariff())['rules'][0]['pricePerKwh'], .35)
        self.assertEqual(convert_pricing(tariff(0))['rules'][0]['pricePerKwh'], 0)

    def test_no_currency_conversion(self):
        rule = convert_pricing(tariff(3200000, 'MAD'))['rules'][0]
        self.assertEqual((rule['currency'], rule['pricePerKwh']), ('MAD', 3.2))

    def test_power_minute_native_currency(self):
        t = {'pricingStatus': 'available', 'currency': 'MAD', 'pricingUnit': 'minute', 'minutePrices': [
            {'days': 127, 'start': 0, 'end': 1440, 'tiers': [
                {'minPowerKw': 0, 'maxPowerKw': 60, 'price': 1100000},
                {'minPowerKw': 60, 'maxPowerKw': None, 'price': 2300000}]}]}
        r = convert_pricing(t)['rules'][0]
        self.assertEqual(r['billing'], 'powerMinute')
        self.assertEqual(r['powerBands'], [dict(minKw=0, maxKw=60, ratePerMinute=1.1), dict(minKw=60, maxKw=1000, ratePerMinute=2.3)])

    def test_equivalent_splits_do_not_report_difference(self):
        base = convert_pricing(tariff())
        split = {'type': 'rules', 'rules': [dict(base['rules'][0], scope='timeWindow', start='00:00', end='09:00'),
                                          dict(base['rules'][0], scope='timeWindow', start='09:00', end='00:00')]}
        self.assertEqual(schedule(base), schedule(split))

    def test_changed_window_is_detected(self):
        a = tariff()
        b = copy.deepcopy(a)
        b['prices'] = [dict(a['prices'][0], end=540), dict(a['prices'][0], start=540, price=420000)]
        self.assertNotEqual(schedule(convert_pricing(a)), schedule(convert_pricing(b)))

    def test_weekly_schedule_rejected_not_flattened(self):
        t = tariff()
        t['prices'][0]['days'] = 31
        with self.assertRaises(ValueError):
            convert_pricing(t)

    def test_missing_negative_or_conflicting_price_rejected(self):
        for value in (None, -1, True, float('nan')):
            with self.assertRaises(ValueError):
                convert_pricing(tariff(value))
        t = tariff()
        t['prices'].append(dict(t['prices'][0]))
        with self.assertRaises(ValueError):
            convert_pricing(t)

    def test_missing_hours_rejected(self):
        t = tariff()
        t['prices'][0]['end'] = 1300
        with self.assertRaises(ValueError):
            convert_pricing(t)

    def test_no_fabricated_fees(self):
        r = convert_pricing(tariff())['rules'][0]
        self.assertNotIn('idlePerMinute', r)
        self.assertNotIn('connectionFee', r)

    def test_preserves_input_ids_and_dates_and_missing_station(self):
        mac = [{'id': 'existing-id', 'name': 'Existing', 'countryCode': 'FR', 'teslaUrl': 'https://www.tesla.com/fr_FR/findus/location/supercharger/123',
                'pricing': convert_pricing(tariff()), 'latitude': 48., 'longitude': 2., 'powerKw': 250, 'stalls': 8,
                'lastUpdated': '2026-09-03', 'access': {'limited': False}},
               {'id': 'missing-id', 'name': 'Missing', 'countryCode': 'FR', 'pricing': convert_pricing(tariff()), 'teslaUrl': 'https://www.tesla.com/findus/location/supercharger/999'}]
        src = {'schemaVersion': 2, 'generatedAt': '2026-09-11T22:00:00Z', 'stats': {'stations': 1}, 'stations': [
            {'id': '123', 'country': 'FR', 'name': 'Station', 'lat': 48., 'lon': 2., 'maxPowerKw': 250, 'stallCount': 8,
             'lastSuccessfulAt': '2026-09-11T10:00:00Z', 'lifecycle': 'active', 'pricing': {'tesla': tariff()}}]}
        original = copy.deepcopy(mac)
        export, report = compare(mac, src, 'test')
        self.assertEqual(mac, original)
        self.assertEqual(export[0]['id'], 'existing-id')
        self.assertEqual(export[0]['lastUpdated'], '2026-09-11')
        self.assertEqual(report['summary']['same_tariff'], 1)
        self.assertEqual(report['summary']['only_mac'], 1)


if __name__ == '__main__':
    unittest.main()
