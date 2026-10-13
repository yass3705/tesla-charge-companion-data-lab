#!/usr/bin/env python3
"""Checkpointed, read-only Electra NL eMSP source staging against DOT-NL.

Each invocation fetches at most 60 global GraphQL pages. Only exact, unique
DOT-NL EVSEs with normal/Type 2/CCS connectors enter the persisted inventory.
No tariff is attached to Production or declared payable by this collector.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import json
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pilot_electra_nl_emsp import distance, kind, norm

SOURCE = Path('data/national/netherlands_dotnl/normalized.json.gz')
OUT_DIR = Path('data/platforms/electra/netherlands/emsp-source-staging')
PAGE_SIZE = 100
MAX_PAGES = 60
QUERY = '''query National($offset:Int!){locations(limit:100,offset:$offset){totalCount items{
 id name country coordinates{latitude longitude} connectorTypes maxPower cpo{name} operator{name}
 evses{evseId status physicalReference}
 chargeTariffs{chargeTariffId currency currentPricePerKwh elements{
  restrictions{dayOfWeek startTime endTime minDuration maxDuration startDate endDate minKwh maxKwh minPower maxPower}
  priceComponents{type price}}}}}}'''


def fetch_page(page):
    offset = page * PAGE_SIZE
    request = urllib.request.Request(
        'https://emsp.go-electra.com/graphql',
        data=json.dumps({'query': QUERY, 'variables': {'offset': offset}}).encode(),
        headers={'Content-Type': 'application/json', 'Accept': 'application/json',
                 'User-Agent': 'tcc-v9-readonly-national-emsp-stage/1.0'},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = json.load(response)
            if payload.get('errors'):
                raise RuntimeError(str([e.get('message') for e in payload['errors']])[:160])
            result = (payload.get('data') or {}).get('locations') or {}
            items = result.get('items')
            total = result.get('totalCount')
            if not isinstance(items, list) or not isinstance(total, int):
                raise RuntimeError('missing items or totalCount')
            expected = min(PAGE_SIZE, max(0, total - offset))
            if len(items) != expected:
                raise RuntimeError(f'page {page}: expected {expected} items, got {len(items)}')
            return page, total, items
        except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError) as exc:
            if attempt == 2:
                raise RuntimeError(f'page {page} failed after three attempts: {exc}') from exc
            time.sleep(1.5 * (attempt + 1))


def stage_items(items, national_index):
    counts = Counter()
    accepted = []
    for location in items:
        if location.get('country') != 'NL':
            continue
        counts['nlLocationsSeen'] += 1
        matched = []
        for source_evse in location.get('evses') or []:
            counts['nlSourceEvsesSeen'] += 1
            pairs = national_index.get(norm(source_evse.get('evseId')), [])
            if len(pairs) != 1:
                counts['unmatchedOrDuplicateId'] += 1
                continue
            station, national_evse = pairs[0]
            gap = distance(location.get('coordinates') or {}, station.get('coordinates') or {})
            if gap is None or gap > 120:
                counts['gpsRejected'] += 1
                continue
            connectors = [{'id': c.get('id'), 'kind': kind(c.get('standard')),
                           'powerKw': c.get('powerKw'), 'tariffKeys': c.get('tariffKeys') or []}
                          for c in national_evse.get('connectors') or [] if kind(c.get('standard'))]
            if not connectors:
                counts['unsupportedConnectorOnly'] += 1
                continue
            counts['matchedAllowedEvses'] += 1
            counts['matchedAllowedConnectors'] += len(connectors)
            matched.append({'sourceEvseId': source_evse.get('evseId'),
                            'sourceStatus': source_evse.get('status'),
                            'nationalStationId': station.get('stationId'),
                            'nationalEvseId': national_evse.get('evseId'),
                            'nationalStatus': national_evse.get('status'),
                            'distanceM': gap, 'connectors': connectors})
        if matched:
            accepted.append({'locationId': location.get('id'), 'name': location.get('name'),
                             'country': 'NL', 'coordinates': location.get('coordinates'),
                             'cpo': (location.get('cpo') or {}).get('name'),
                             'operator': (location.get('operator') or {}).get('name'),
                             'connectorTypes': location.get('connectorTypes') or [],
                             'maxPowerW': location.get('maxPower'),
                             'chargeTariffs': location.get('chargeTariffs') or [],
                             'matchedAllowedEvses': matched})
    return counts, accepted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-page', type=int, required=True)
    parser.add_argument('--pages', type=int, default=60)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    if args.start_page < 0 or not 1 <= args.pages <= MAX_PAGES or not 1 <= args.workers <= 4:
        parser.error('start-page >= 0, pages 1..60 and workers 1..4 required')
    source_bytes = SOURCE.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    national = json.loads(gzip.decompress(source_bytes))
    index = defaultdict(list)
    for station in national.get('stations') or []:
        for evse in station.get('evses') or []:
            key = norm(evse.get('evseId'))
            if key:
                index[key].append((station, evse))
    pages = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch_page, p) for p in range(args.start_page, args.start_page + args.pages)]
        for future in as_completed(futures):
            page, total, items = future.result()
            pages[page] = (total, items)
    totals = {x[0] for x in pages.values()}
    if len(totals) != 1:
        raise RuntimeError(f'totalCount drift within batch: {sorted(totals)}')
    counts = Counter()
    locations = []
    for page in sorted(pages):
        c, rows = stage_items(pages[page][1], index)
        counts.update(c)
        locations.extend(rows)
    counts['sourcePages'] = len(pages)
    counts['matchedAllowedLocations'] = len(locations)
    payload = {'schemaVersion': 1, 'generatedAt': datetime.now(timezone.utc).isoformat(),
               'source': 'https://emsp.go-electra.com/graphql', 'nationalSource': str(SOURCE),
               'nationalSha256': source_sha, 'pageSize': PAGE_SIZE,
               'startPage': args.start_page, 'pages': args.pages, 'sourceTotalCount': totals.pop(),
               'counts': dict(counts), 'locations': locations,
               'status': 'source_staging_only_no_tariff_promotion'}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f'pages-{args.start_page:04d}-{args.start_page+args.pages-1:04d}.json.gz'
    if out.exists():
        raise RuntimeError(f'existing immutable shard: {out}')
    out.write_bytes(gzip.compress(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()))
    print(json.dumps({'path': str(out), 'sourceTotalCount': payload['sourceTotalCount'],
                      'counts': payload['counts']}))


if __name__ == '__main__':
    main()
