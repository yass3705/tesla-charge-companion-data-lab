import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/suc_tracker'))
from core import write, convert_station
from update import refresh
from compare_mac import resolve_codes, compare_files, completed_lot


def source():
    station = {'id': '123', 'country': 'FR', 'name': 'Example', 'lat': 48, 'lon': 2,
               'maxPowerKw': 250, 'stallCount': 8, 'lifecycle': 'active', 'lastSuccessfulAt': '2026-09-11T10:00:00Z',
               'pricing': {'tesla': {'currency': 'EUR', 'pricingStatus': 'available', 'pricingUnit': 'kwh',
                                     'prices': [{'days': 127, 'start': 0, 'end': 1440, 'price': 350000}]}}}
    return {'schemaVersion': 2, 'generatedAt': '2026-09-11T22:00:00Z', 'stats': {'stations': 1}, 'stations': [station]}


CFG = {'france': {'countryCode': 'FR', 'enabled': True}, 'spain': {'countryCode': 'ES', 'enabled': True}}


class PipelineTests(unittest.TestCase):
    def test_explicit_scope_required(self):
        with self.assertRaises(ValueError):
            resolve_codes(CFG)
        self.assertEqual(resolve_codes(CFG, ['france', 'ES']), {'FR', 'ES'})

    def test_unknown_access_remains_unknown_after_refresh(self):
        raw = source()
        first = convert_station(raw['stations'][0], None, raw['generatedAt'])
        second = convert_station(raw['stations'][0], first, raw['generatedAt'])
        self.assertEqual(second['sucTracker']['accessSource'], 'unknown')
        self.assertTrue(second['access']['limited'])
        self.assertEqual(second['access']['days'], {})

    def test_update_and_read_github_country_slice(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root / 'input.json', source())
            refresh(root / 'published', {'FR'}, root / 'input.json')
            snap = {name: json.loads((root/'published'/name).read_text()) for name in ['tesla_stations.json', 'europe.json', 'metadata.json']}
            mac = copy.deepcopy(snap['tesla_stations.json'])
            mac.append(dict(mac[0], id='unrelated-es', countryCode='ES'))
            write(root/'mac.json', mac)
            report = compare_files(root/'mac.json', snap, root/'report', {'FR'}, 'test', 'a'*40)
            self.assertEqual(report['countries'], ['FR'])
            self.assertEqual(report['summary']['macStations'], 1)
            self.assertEqual(report['summary']['same_tariff'], 1)
            self.assertTrue(all(s['country'] == 'FR' for s in report['stations']))
            # Consumers compare the saved normalized GitHub catalogue itself.
            snap['tesla_stations.json'][0]['pricing']['rules'][0]['pricePerKwh'] = 999
            with self.assertRaises(ValueError):
                compare_files(root/'mac.json', snap, root/'report', {'FR'}, 'test', 'a'*40)

    def test_access_seed_restores_known_legacy_access(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = source()
            write(root/'input.json', raw)
            first = convert_station(raw['stations'][0], None, raw['generatedAt'])
            self.assertEqual(first['sucTracker']['accessSource'], 'unknown')
            out = root/'published'
            out.mkdir()
            write(out/'europe.json', raw)
            write(out/'tesla_stations.json', [first])
            key = 'FR|123'
            write(out/'access-seed.json', {
                'schemaVersion': 1,
                'entries': {
                    key: {
                        'access': {'limited': False},
                        'accessSource': 'Mac/TCC baseline',
                        'accessReferenceAt': '2026-09-03'
                    }
                }
            })
            refresh(out, {'FR'}, root/'input.json')
            rows = read(out/'tesla_stations.json')
            self.assertEqual(rows[0]['sucTracker']['accessSource'], 'Mac/TCC baseline')
            self.assertFalse(rows[0]['access']['limited'])

    def test_regressed_source_does_not_replace_published_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root/'source.json', source())
            refresh(root/'out', {'FR'}, root/'source.json')
            before = {p.name: p.read_bytes() for p in (root/'out').iterdir()}
            raw = source()
            raw['generatedAt'] = '2026-08-01T00:00:00Z'
            write(root/'source.json', raw)
            with self.assertRaises(ValueError):
                refresh(root/'out', {'FR'}, root/'source.json')
            self.assertEqual(before, {p.name: p.read_bytes() for p in (root/'out').iterdir()})

    def test_failed_lot_country_is_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root/'lot-summary.json', {'countries': [{'country': 'france', 'status': 'published'}, {'country': 'spain', 'status': 'blocked_scan'}]})
            write(root/'france/export-report.json', {'status': 'ready', 'countryCode': 'FR'})
            write(root/'france/publish-candidate.json', [{'id': 'FR1', 'countryCode': 'FR'}, {'id': 'ES1', 'countryCode': 'ES'}])
            codes, rows, skipped = completed_lot(root/'lot-summary.json', CFG)
            self.assertEqual(codes, {'FR'})
            self.assertEqual([r['id'] for r in rows], ['FR1'])
            self.assertEqual(skipped, ['spain'])
