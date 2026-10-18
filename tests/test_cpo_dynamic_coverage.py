import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "uk_open_feeds", Path(__file__).resolve().parents[1] / "scripts/collect_uk_validated_open_feeds.py"
)
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class DynamicCoverage(unittest.TestCase):
    def test_complete_pagination_accepts_increase_and_decrease(self):
        for total in (1, 84, 1000):
            with self.subTest(total=total):
                def page(url):
                    offset = int(url.split('offset=')[1])
                    limit = int(url.split('limit=')[1].split('&')[0])
                    return {'data': list(range(offset, min(total, offset + limit))), 'meta': {'total': total}}, {}
                with patch.object(collector, 'request_json', side_effect=page):
                    self.assertEqual(total, len(collector.fetch_offset('https://source.test/items', 50)))

    def test_incomplete_pagination_is_incident(self):
        def page(url):
            offset = int(url.split('offset=')[1])
            return {'data': list(range(50)) if offset == 0 else [], 'meta': {'total': 84}}, {}
        with patch.object(collector, 'request_json', side_effect=page):
            with self.assertRaisesRegex(RuntimeError, 'incomplete pagination'):
                collector.fetch_offset('https://source.test/items', 50)

    def test_one_cpo_failure_preserves_dated_last_good(self):
        prior = {'retrievedAt': '2026-10-17T10:00:00Z', 'sources': [
            {'name': 'A', 'summary': {'locations': 1, 'status': 'complete'}, 'locations': [{'id': 'source-a'}]},
            {'name': 'B', 'summary': {'locations': 2, 'status': 'complete'}, 'locations': [{'id': 'source-b'}]},
        ]}
        a = collector.preserve_last_good('A', RuntimeError('API 500'), prior, 'sha-previous')
        self.assertEqual('last_good_stale', a['summary']['status'])
        self.assertEqual('2026-10-17T10:00:00Z', a['sourceAudit']['lastGoodCollectedAt'])
        self.assertEqual('source-b', prior['sources'][1]['locations'][0]['id'])
        self.assertIsNone(collector.preserve_last_good('C', RuntimeError('API 500'), prior, 'sha-previous'))


if __name__ == '__main__':
    unittest.main()
