#!/usr/bin/env python3
"""Collect the operator-supplied PCPR feed without exporting credentials.

Raw feed is evidence only. Direct tariff eligibility and CPO scope must be
verified before replacing the existing exact PAYG overlay.
"""
import gzip
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://open-chargepoints.com/api/ocpi/cpo/2.2.1/'


def retry_delay(error, attempt):
    """Honor server rate-limit headers without logging credentials or bodies."""
    headers = error.headers or {}
    value = headers.get('Retry-After')
    if value:
        try:
            delay = float(value)
        except (TypeError, ValueError):
            try:
                stamp = parsedate_to_datetime(value)
                delay = (stamp - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                delay = None
        if delay is not None:
            return max(2.0, delay)
    reset = headers.get('X-RateLimit-Reset')
    if reset:
        try:
            return max(2.0, float(reset) - time.time())
        except (ValueError, TypeError, OverflowError):
            pass
    return float(min(60 * (2 ** min(attempt, 3)), 480))


def collect(endpoint, token, deadline=None):
    """Fetch an all-or-nothing snapshot, using bounded 429/5xx retries."""
    rows, seen = [], set()
    authorization = token
    url = BASE + endpoint + '?limit=1000&offset=0'
    requests, retries = 0, 0
    if deadline is None:
        deadline = time.monotonic() + 20 * 60
    while url:
        if url in seen:
            raise RuntimeError('Pagination loop')
        seen.add(url)
        if urllib.parse.urlsplit(url).netloc != 'open-chargepoints.com':
            raise RuntimeError('Refusing foreign pagination host')
        while True:
            requests += 1
            if requests > 30:
                raise RuntimeError('Request budget reached; snapshot not published')
            req = urllib.request.Request(url, headers={'Authorization': authorization,
                'Accept': 'application/json', 'User-Agent': 'TeslaChargeCompanion/9 Ubitricity-PCPR'})
            try:
                with urllib.request.urlopen(req, timeout=90) as response:
                    payload, headers = json.load(response), dict(response.headers)
                retries = 0
                break
            except urllib.error.HTTPError as error:
                if error.code == 401 and authorization == token and not token.startswith('Token '):
                    authorization = 'Token ' + token
                    continue
                if error.code in (429, 500, 502, 503, 504):
                    wait = retry_delay(error, retries) if error.code == 429 else min(30 * 2 ** min(retries, 3), 240)
                    remaining = deadline - time.monotonic()
                    if remaining < wait + 5:
                        raise RuntimeError(
                            f'{endpoint} HTTP {error.code}; retry delay {wait:.0f}s '
                            'exceeds run budget; existing snapshot retained'
                        ) from None
                    retries += 1
                    print(f'{endpoint}: HTTP {error.code}, retry {retries} in {wait:.0f}s', flush=True)
                    time.sleep(wait)
                    continue
                raise RuntimeError(f'{endpoint} HTTP {error.code}; response and credentials omitted') from None
            except (TimeoutError, urllib.error.URLError):
                wait = min(30 * 2 ** min(retries, 3), 240)
                if time.monotonic() + wait + 5 > deadline:
                    raise RuntimeError(f'{endpoint} connection error; existing snapshot retained') from None
                retries += 1
                print(f'{endpoint}: connection retry {retries} in {wait:.0f}s', flush=True)
                time.sleep(wait)
        if isinstance(payload, dict) and payload.get('status_code') != 1000:
            raise RuntimeError(f'{endpoint}: unsuccessful OCPI response')
        page = payload.get('data') if isinstance(payload, dict) else payload
        if not isinstance(page, list):
            raise RuntimeError(f'{endpoint}: unexpected response shape')
        if not page and not rows:
            safe_headers = {k.lower(): str(v)[:160] for k, v in headers.items() if k.lower() in ('x-total-count', 'x-limit', 'x-offset', 'x-ratelimit-remaining', 'retry-after')}
            print(json.dumps({'endpoint': endpoint, 'httpStatus': 200, 'ocpiStatus': payload.get('status_code') if isinstance(payload, dict) else None, 'pageSize': 0, 'pagination': safe_headers, 'hasNextLink': bool(headers.get('Link', headers.get('link'))), 'diagnosticOnly': True}), flush=True)
        rows.extend(page)
        link = headers.get('Link', headers.get('link', ''))
        match = re.search(r'<([^>]+)>;\s*rel="?next"?', link)
        total = headers.get('X-Total-Count', headers.get('x-total-count'))
        if match:
            url = urllib.parse.urljoin(url, match.group(1))
        elif len(page) == 1000 and (total is None or len(rows) < int(total)):
            url = BASE + endpoint + '?' + urllib.parse.urlencode({'limit': 1000, 'offset': len(rows)})
        else:
            url = None
        if url:
            time.sleep(1)  # Pace the provider's hourly endpoint quota.
    return rows, requests


def main():
    token = os.environ.get('UBITRICITY_PCPR_TOKEN', '').strip()
    if not token:
        raise SystemExit('No configured Ubitricity secret matched. Supply the secret name, never its value.')
    deadline = time.monotonic() + 20 * 60  # Shared retry allowance across both endpoints.
    locations, location_requests = collect('locations', token, deadline)
    if not locations:
        # One independent tariff probe helps distinguish an empty location scope
        # from a globally empty PCPR account. No snapshot is written on failure.
        tariffs, tariff_requests = collect('tariffs', token, deadline)
        print(json.dumps({'diagnosticOnly': True, 'locationCount': 0, 'locationRequests': location_requests, 'tariffCount': len(tariffs), 'tariffRequests': tariff_requests, 'snapshotPreserved': True}), flush=True)
        raise RuntimeError('Empty location feed; provider scope requires investigation; existing PAYG overlay retained')
    tariffs, tariff_requests = collect('tariffs', token, deadline)
    connectors = [c for loc in locations for e in loc.get('evses', []) for c in e.get('connectors', [])]
    refs = {str(t) for c in connectors for t in c.get('tariff_ids', [])}
    tids = {str(t['id']) for t in tariffs}
    names = Counter(str(loc.get('operator', {}).get('name', 'UNKNOWN')) for loc in locations)
    now = datetime.now(timezone.utc).isoformat()
    report = {'provider': 'Ubitricity', 'source': 'operator_supplied_Eco_Movement_PCPR',
              'collectedAt': now, 'locations': len(locations),
              'evses': sum(len(loc.get('evses', [])) for loc in locations),
              'connectors': len(connectors), 'tariffs': len(tariffs),
              'locationRequests': location_requests, 'tariffRequests': tariff_requests,
              'operators': dict(names), 'countries': dict(Counter(loc.get('country', 'UNKNOWN') for loc in locations)),
              'partyIds': dict(Counter(loc.get('party_id', 'UNKNOWN') for loc in locations)),
              'tariffTypes': dict(Counter(t.get('type', 'UNSPECIFIED') for t in tariffs)),
              'missingTariffIds': sorted(refs - tids), 'credentialsPersisted': False,
              'publishedToV9': False, 'status': 'api_collected_scope_and_pricing_validation_pending',
              'existingPaygOverlayReplaced': False}
    for path, data in [('data/national/uk_ubitricity_pcpr.json.gz',
                        {'collectedAt': now, 'source': report['source'], 'locations': locations, 'tariffs': tariffs}),
                       ('reports/uk/ubitricity-pcpr-latest.json', report)]:
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        body = (json.dumps(data, separators=(',', ':')) + '\n').encode()
        target.write_bytes(gzip.compress(body, mtime=0) if path.endswith('.gz') else body)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
