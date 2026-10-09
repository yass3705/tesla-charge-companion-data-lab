"""Non-network regression tests for Ubitricity UK PCPR quota handling."""
import io
import json
import sys
import time
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import uk_ubitricity_pcpr_collect as collector


def error(status, headers=None):
    return HTTPError(
        "https://open-chargepoints.com/api/ocpi/cpo/2.2.1/locations",
        status, "provider error", headers or {}, None,
    )


class Response(io.BytesIO):
    def __init__(self, data, headers=None):
        super().__init__(json.dumps({"status_code": 1000, "data": data}).encode("utf-8"))
        self.headers = headers or {}


class UbitricityCollectorTests(unittest.TestCase):
    def test_retry_after_seconds(self):
        self.assertEqual(collector.retry_delay(error(429, {"Retry-After": "7"}), 0), 7)

    def test_retry_after_unknown_uses_backoff(self):
        self.assertEqual(collector.retry_delay(error(429), 0), 60)
        self.assertEqual(collector.retry_delay(error(429), 2), 240)

    def test_429_retries_same_page_without_partial_publication(self):
        response = Response([{"id": "one"}], {"X-Total-Count": "1"})
        with mock.patch.object(collector.urllib.request, "urlopen",
                               side_effect=[error(429, {"Retry-After": "2"}), response]) as req:
            with mock.patch.object(collector.time, "sleep") as sleep:
                rows, count = collector.collect("locations", "dummy-token", time.monotonic() + 60)
        self.assertEqual([x["id"] for x in rows], ["one"])
        self.assertEqual(count, 2)
        self.assertEqual(req.call_count, 2)
        sleep.assert_called_once_with(2.0)

    def test_retries_stop_before_deadline(self):
        with mock.patch.object(collector.urllib.request, "urlopen",
                               side_effect=error(429, {"Retry-After": "3600"})):
            with mock.patch.object(collector.time, "sleep") as sleep:
                with self.assertRaisesRegex(RuntimeError, "existing snapshot retained"):
                    collector.collect("locations", "dummy-token", time.monotonic() + 90)
        sleep.assert_not_called()

    def test_documented_token_scheme_used_on_first_request(self):
        with mock.patch.object(collector.urllib.request, 'urlopen', return_value=Response([{'id': 'one'}])) as req:
            rows, count = collector.collect('locations', 'dummy-token', time.monotonic() + 60)
        self.assertEqual((len(rows), count), (1, 1))
        self.assertEqual(req.call_args.args[0].get_header('Authorization'), 'dummy-token')

    def test_token_scheme_is_not_duplicated(self):
        with mock.patch.object(collector.urllib.request, 'urlopen', return_value=Response([{'id': 'one'}])) as req:
            collector.collect('locations', 'Token dummy-token', time.monotonic() + 60)
        self.assertEqual(req.call_args.args[0].get_header('Authorization'), 'Token dummy-token')

    def test_401_with_documented_scheme_fails_closed(self):
        with mock.patch.object(collector.urllib.request, 'urlopen', side_effect=error(401)) as req:
            with self.assertRaisesRegex(RuntimeError, 'HTTP 401'):
                collector.collect('locations', 'dummy-token', time.monotonic() + 60)
        self.assertEqual(req.call_count, 2)

    def test_empty_first_page_returns_no_rows(self):
        with mock.patch.object(collector.urllib.request, "urlopen", return_value=Response([])):
            rows, count = collector.collect("locations", "dummy-token", time.monotonic() + 60)
        self.assertEqual((rows, count), ([], 1))

    def test_non_success_ocpi_status_rejected(self):
        response = Response([])
        response = io.BytesIO(json.dumps({"status_code": 2001, "data": []}).encode())
        response.headers = {}
        with mock.patch.object(collector.urllib.request, "urlopen", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "unsuccessful OCPI"):
                collector.collect("locations", "dummy-token", time.monotonic() + 60)

    def test_pagination_link_follows_next_page(self):
        link = '<https://open-chargepoints.com/api/ocpi/cpo/2.2.1/locations?limit=1000&offset=1>; rel="next"'
        pages = [Response([{"id": "one"}], {"Link": link}),
                 Response([{"id": "two"}], {"X-Total-Count": "2"})]
        with mock.patch.object(collector.urllib.request, "urlopen", side_effect=pages):
            with mock.patch.object(collector.time, "sleep") as sleep:
                rows, count = collector.collect("locations", "dummy-token", time.monotonic() + 90)
        self.assertEqual(count, 2)
        self.assertEqual([x["id"] for x in rows], ["one", "two"])
        sleep.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
