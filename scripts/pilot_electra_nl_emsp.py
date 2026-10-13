#!/usr/bin/env python3
"""Bounded Electra eMSP → DOT-NL identity and tariff-source pilot, no promotion."""
import collections
import gzip
import hashlib
import json
import math
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path('data/national/netherlands_dotnl/normalized.json.gz')
OUT = Path('reports/emsp-pilots/electra-nl-dotnl.json')
OFFSETS = (0, 50000, 250000, 300000)
QUERY = '''query {locations(limit:100,offset:OFFSET){totalCount items{
 id name country coordinates{latitude longitude} cpo{name} operator{name}
 evses{evseId status physicalReference}
 chargeTariffs{chargeTariffId currency currentPricePerKwh elements{
 restrictions{minPower maxPower startTime endTime minDuration maxDuration}
 priceComponents{type price}}}}}}'''


def norm(value):
    return re.sub('[^A-Z0-9]', '', str(value or '').upper())


def distance(a, b):
    try:
        x, y = float(a['latitude']), float(a['longitude'])
        xx, yy = float(b['latitude']), float(b['longitude'])
        return round(111195 * math.hypot(x - xx, (y - yy) * math.cos(math.radians(x))))
    except (TypeError, ValueError, KeyError):
        return None


def fetch(offset):
    request = urllib.request.Request(
        'https://emsp.go-electra.com/graphql',
        data=json.dumps({'query': QUERY.replace('OFFSET', str(offset))}).encode(),
        headers={'Content-Type': 'application/json', 'Accept': 'application/json',
                 'User-Agent': 'tcc-v9-readonly-nl-emsp-pilot/1.0'},
    )
    with urllib.request.urlopen(request, timeout=35) as response:
        payload = json.load(response)
    if payload.get('errors'):
        raise RuntimeError('Electra GraphQL errors: ' + str([e.get('message') for e in payload['errors']])[:200])
    value = (payload.get('data') or {}).get('locations')
    if not value or len(value.get('items') or []) != 100:
        raise RuntimeError(f'incomplete Electra page at offset {offset}')
    return value


def main():
    source_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    with gzip.open(SOURCE, 'rt') as handle:
        national = json.load(handle)
    by_evse = collections.defaultdict(list)
    for station in national['stations']:
        for evse in station.get('evses') or []:
            key = norm(evse.get('evseId'))
            if key:
                by_evse[key].append((station, evse))
    counts = collections.Counter()
    examples = []
    pages = []
    total_counts = []
    for offset in OFFSETS:
        response = fetch(offset)
        total_counts.append(response['totalCount'])
        items = response['items']
        nl = [location for location in items if location.get('country') == 'NL']
        pages.append({'offset': offset, 'items': len(items), 'nlLocations': len(nl)})
        counts['source_locations'] += len(nl)
        for location in nl:
            tariffs = location.get('chargeTariffs') or []
            counts['source_tariffs'] += len(tariffs)
            counts['source_evses'] += len(location.get('evses') or [])
            for evse in location.get('evses') or []:
                candidates = by_evse.get(norm(evse.get('evseId')), [])
                if not candidates:
                    counts['evse_unmatched'] += 1
                    continue
                if len(candidates) != 1:
                    counts['evse_ambiguous_identity'] += 1
                    continue
                station, direct_evse = candidates[0]
                d = distance(location.get('coordinates') or {}, station.get('coordinates') or {})
                if d is None or d > 120:
                    counts['evse_distance_rejected'] += 1
                    continue
                counts['evse_exact_geoverified'] += 1
                if evse.get('status') in ('AVAILABLE', 'CHARGING', 'OCCUPIED'):
                    counts['evse_emsp_positive_status'] += 1
                if direct_evse.get('status') in ('AVAILABLE', 'CHARGING', 'OCCUPIED'):
                    counts['evse_direct_positive_status'] += 1
                if (evse.get('status') in ('AVAILABLE', 'CHARGING', 'OCCUPIED')
                        and direct_evse.get('status') in ('AVAILABLE', 'CHARGING', 'OCCUPIED')):
                    counts['evse_both_positive_status'] += 1
                if len(tariffs) == 1:
                    counts['evse_at_single_tariff_location'] += 1
                elif len(tariffs) > 1:
                    counts['evse_at_multitariff_location'] += 1
                direct_keys = sorted({key for c in direct_evse.get('connectors') or []
                                      for key in c.get('tariffKeys') or []})
                if direct_keys:
                    counts['evse_with_direct_tariff_reference'] += 1
                if len(examples) < 12 and (len(tariffs) == 1 or len(tariffs) > 1):
                    examples.append({
                        'evseId': evse['evseId'], 'electraLocationId': location['id'],
                        'dotnlStationId': station['stationId'], 'distanceM': d,
                        'electraCpo': (location.get('cpo') or {}).get('name'),
                        'nationalOperator': station.get('operatorName'),
                        'electraEvseStatus': evse.get('status'),
                        'nationalEvseStatus': direct_evse.get('status'),
                        'electraTariffIds': [t.get('chargeTariffId') for t in tariffs],
                        'electraComponents': [e.get('priceComponents') for t in tariffs
                                              for e in t.get('elements') or []],
                        'directTariffKeys': direct_keys,
                        'directTariffObjectsPresent': sum(k in national['tariffs'] for k in direct_keys),
                        'directTariffComponents': [element.get('priceComponents') for key in direct_keys
                                                   for element in (national['tariffs'].get(key) or {}).get('elements') or []],
                        'note': 'identity/source proof only; no eMSP price assigned to a connector',
                    })
    report = {
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'electraSource': 'https://emsp.go-electra.com/graphql',
        'nationalSource': str(SOURCE), 'nationalSha256': source_sha,
        'samplePolicy': 'four fixed pages of 100, non-random and not national coverage',
        'totalCounts': total_counts, 'pages': pages, 'counts': dict(counts),
        'examples': examples,
        'publicationStatus': 'read_only_pilot_no_tariff_promotion',
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'pages': pages, 'counts': report['counts'], 'report': str(OUT)}))


if __name__ == '__main__':
    main()
