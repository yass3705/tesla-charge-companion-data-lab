#!/usr/bin/env python3
"""Collect the operator-supplied PCPR feed without exporting credentials.

Raw feed is evidence only. Direct tariff eligibility and CPO scope must be
verified before replacing the existing exact PAYG overlay.
"""
import gzip
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://open-chargepoints.com/api/ocpi/cpo/2.2.1/'


def collect(endpoint, token):
    rows, seen = [], set()
    authorization = token
    url = BASE + endpoint + '?limit=1000&offset=0'
    requests = 0
    while url:
        if url in seen:
            raise RuntimeError('Pagination loop')
        seen.add(url)
        if urllib.parse.urlsplit(url).netloc != 'open-chargepoints.com':
            raise RuntimeError('Refusing foreign pagination host')
        while True:
            requests += 1
            if requests > 30:
                raise RuntimeError('Hourly request budget reached; snapshot not published')
            req = urllib.request.Request(url, headers={'Authorization': authorization,
                'Accept': 'application/json', 'User-Agent': 'TeslaChargeCompanion/9 Ubitricity-PCPR'})
            try:
                with urllib.request.urlopen(req, timeout=90) as response:
                    payload, headers = json.load(response), dict(response.headers)
                break
            except urllib.error.HTTPError as error:
                if error.code == 401 and authorization == token and not token.startswith('Token '):
                    authorization = 'Token ' + token
                    continue
                raise RuntimeError(f'{endpoint} HTTP {error.code}; response and credentials omitted') from None
        if isinstance(payload, dict) and payload.get('status_code', 1000) != 1000:
            raise RuntimeError(f'{endpoint}: unsuccessful OCPI response')
        page = payload.get('data') if isinstance(payload, dict) else payload
        if not isinstance(page, list):
            raise RuntimeError(f'{endpoint}: unexpected response shape')
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
    return rows, requests


def main():
    token = os.environ.get('UBITRICITY_PCPR_TOKEN', '').strip()
    if not token:
        raise SystemExit('No configured Ubitricity secret matched. Supply the secret name, never its value.')
    locations, location_requests = collect('locations', token)
    tariffs, tariff_requests = collect('tariffs', token)
    if not locations:
        raise RuntimeError('Empty location feed; existing PAYG overlay retained')
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
