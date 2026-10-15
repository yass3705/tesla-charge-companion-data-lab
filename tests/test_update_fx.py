import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import update_fx


class FXFallbackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.previous = Path.cwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, self.previous)
        Path('data/fx').mkdir(parents=True)
        rates = {code: 1.0 for code in update_fx.SUPPORTED}
        self.original = {'base': 'EUR', 'rates': rates}
        Path('data/fx/exchange_rates.json').write_text(json.dumps(self.original))

    def test_two_provider_failures_preserve_last_good(self):
        with patch.object(update_fx, 'fetch_json', side_effect=OSError('offline')):
            with self.assertRaises(OSError):
                update_fx.main()
        self.assertEqual(json.loads(Path('data/fx/exchange_rates.json').read_text()), self.original)

    def test_fallback_preserves_missing_quote(self):
        fresh = {code: 2.0 for code in update_fx.SUPPORTED if code != 'MAD'}
        with patch.object(update_fx, 'fetch_json', side_effect=[OSError('primary'), {'result': 'success', 'rates': fresh, 'time_last_update_utc': '2026-10-15'}]):
            update_fx.main()
        rates = json.loads(Path('data/fx/exchange_rates.json').read_text())['rates']
        self.assertEqual(rates['MAD'], 1.0)
        self.assertEqual(rates['CHF'], 2.0)


if __name__ == '__main__':
    unittest.main()
