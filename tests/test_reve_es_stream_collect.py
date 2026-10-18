import unittest
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from scripts import reve_es_stream_collect as collector
from scripts.reve_es_stream_collect import default_state, validate_checkpoint, tariff_key, status_key, retry_after_seconds


class FreshReveCheckpointTest(unittest.TestCase):
    def test_new_cycle_starts_at_first_page(self):
        state = default_state()
        self.assertEqual((state['nextTariffPage'], state['nextStatusPage']), (1, 1))
        validate_checkpoint(state, {}, {})

    def test_gap_and_missing_rows_are_rejected(self):
        state = default_state()
        state.update(nextTariffPage=3, tariffPagesCollected=[1, 3], tariffRowsStored=1)
        with self.assertRaisesRegex(ValueError, 'missing pages'):
            validate_checkpoint(state, {'C': {'connector_id': 'C'}}, {})

    def test_exact_identifiers(self):
        self.assertEqual(tariff_key({'connector_id': 'ES*ABC*1'}), 'ES*ABC*1')
        self.assertEqual(status_key({'evse_id': 'ES*ABC*E1'}), 'evse:ES*ABC*E1')

    def test_retry_after_is_respected(self):
        self.assertEqual(retry_after_seconds('7200'), 7200)
        self.assertEqual(retry_after_seconds('invalid'), 3600)

    def test_complete_cycle_requires_supplier_totals(self):
        state = default_state()
        state.update(complete=True, nextTariffPage=2, nextStatusPage=2,
                     tariffPagesCollected=[1], statusPagesCollected=[1],
                     tariffTotalPages=1, statusTotalPages=1,
                     tariffTotalCount=2, statusTotalCount=1,
                     tariffRowsStored=1, statusRowsStored=1)
        with self.assertRaisesRegex(ValueError, 'complete count'):
            validate_checkpoint(state, {'a': {}}, {'b': {}})
        state['tariffTotalCount'] = 1
        validate_checkpoint(state, {'a': {}}, {'b': {}})

    def test_full_recent_budget_skips_supplier_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = default_state()
            (root/'state.json').write_text(json.dumps(state))
            (root/'last.json').write_text(json.dumps({
                'requestsAttempted': 5,
                'generatedAt': datetime.now(timezone.utc).isoformat(),
            }))
            with patch.multiple(collector, DATA=root, STATE=root/'state.json',
                                TARIFF_STORE=root/'tariffs.gz', STATUS_STORE=root/'statuses.gz',
                                LAST_RUN=root/'last.json'), patch.dict(os.environ, {'REVE_API_KEY': 'test'}), \
                    patch.object(collector, 'api_get', side_effect=AssertionError('quota exceeded')):
                self.assertEqual(collector.collect(), 0)
                saved = json.loads((root/'state.json').read_text())
                self.assertEqual((saved['nextTariffPage'], saved['nextStatusPage']), (1, 1))
                self.assertIsNotNone(saved['quotaUntil'])
