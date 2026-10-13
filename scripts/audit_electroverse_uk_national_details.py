#!/usr/bin/env python3
"""Audit source-only UK detail shards; never promote a CPO/eMSP tariff here."""
import gzip
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

QUEUE = Path('data/platforms/electroverse/uk-coarse-location-candidates.json.gz')
SEEDS = Path('data/platforms/electroverse/uk-national-cpo-seeds.json.gz')
SHARDS = Path('reports/emsp-national/electroverse-uk-details')
OUT = Path('reports/emsp-national/electroverse-uk-detail-audit.json')
ALLOWED = {'IEC_62196_T2', 'TYPE_2', 'IEC_62196_T2_COMBO', 'CCS2',
           'DOMESTIC_E', 'DOMESTIC_F', 'CEE_7_3', 'CEE_7_4'}


def norm(value):
    return re.sub('[^A-Z0-9]', '', str(value or '').upper())


def point(value):
    if not value:
        return None
    try:
        lat = float(value.get('latitude', value.get('lat')))
        lon = float(value.get('longitude', value.get('lon', value.get('lng'))))
        if math.isfinite(lat) and math.isfinite(lon):
            return lat, lon
    except (TypeError, ValueError):
        pass
    return None


def distance_m(a, b):
    return round(111195 * math.hypot(a[0] - b[0], (a[1] - b[1]) * math.cos(math.radians(a[0]))))


def kind(standard):
    if standard in {'IEC_62196_T2', 'TYPE_2'}:
        return 'TYPE2'
    if standard in {'IEC_62196_T2_COMBO', 'CCS2'}:
        return 'CCS'
    if standard in ALLOWED:
        return 'NORMAL'
    return None


def exact_candidates(evse, source_point, by_evse_id):
    if evse.get('status') not in {'AVAILABLE', 'CHARGING'} or source_point is None:
        return []
    options = []
    for location, cpo_evse in by_evse_id.get(norm(evse.get('physicalReference')), []):
        cpo_point = (location['latitude'], location['longitude'])
        distance = distance_m(source_point, cpo_point)
        if distance > 120:
            continue
        matching = []
        for connector in evse['connectors']:
            source_kind = kind(connector['standard']['name'])
            source_power = float(connector.get('kilowatts') or 0)
            if any(cpo['kind'] == source_kind and
                   (not cpo.get('maxElectricPowerW') or not source_power or
                    abs(cpo['maxElectricPowerW'] / 1000 - source_power) <= 0.5)
                   for cpo in cpo_evse['connectors']):
                matching.append(connector['pk'])
        if matching:
            options.append({'sourceFile': location['sourceFile'], 'cpo': location['cpo'],
                            'locationId': location['locationId'], 'evseId': cpo_evse['evseId'],
                            'distanceM': distance, 'connectorPks': matching})
    return options


def main():
    with gzip.open(QUEUE, 'rt') as handle:
        queue = json.load(handle)
    with gzip.open(SEEDS, 'rt') as handle:
        seeds = json.load(handle)
    ordered = [row['electroversePk'] for row in queue['candidates']]
    by_evse_id = defaultdict(list)
    by_location_id = {}
    for location in seeds['locations']:
        by_location_id[(location['sourceFile'], str(location['locationId']))] = location
        for evse in location['evses']:
            by_evse_id[norm(evse['evseId'])].append((location, evse))
    rows = {}
    repeats = 0
    conflicts = 0
    shards = []
    for path in sorted(SHARDS.glob('offset-*.json.gz')):
        with gzip.open(path, 'rt') as handle:
            data = json.load(handle)
        if data['status'] not in {'source_details_only_no_evse_link_or_tariff_promotion',
                                  'partial_source_details_no_tariff_promotion'}:
            raise ValueError(f'bad shard status: {path}')
        if data['candidateQueueSize'] != len(ordered):
            raise ValueError(f'queue drift: {path}')
        for i, row in enumerate(data['rows']):
            expected = ordered[data['offset'] + i]
            if row['electroversePk'] != expected:
                raise ValueError(f'PK/offset drift: {path} row {i}')
            for evse in row.get('source', {}).get('evses', []) if row.get('source') else []:
                if any(c['standard']['name'] not in ALLOWED for c in evse['connectors']):
                    raise ValueError(f'unsupported connector: {path} row {i}')
            pk = row['electroversePk']
            if pk in rows:
                repeats += 1
                conflicts += row['source'] != rows[pk]['source']
            else:
                rows[pk] = row
        shards.append({'path': str(path), 'offset': data['offset'], 'requested': data['count'],
                       'covered': len(data['rows']), 'status': data['status'],
                       'requests': data['requests'], 'nextOffset': data.get('nextOffset', data['offset'] + len(data['rows']))})
    counts = Counter()
    exact = []
    for row in rows.values():
        source = row['source']
        if source is None:
            counts['sourceLocationsMissing'] += 1
            continue
        counts['sourceLocationsFound'] += 1
        source_point = point(source.get('coordinates'))
        if source_point is None:
            counts['sourceLocationsWithoutCoordinates'] += 1
        else:
            nearby_ids = {(x['sourceFile'], str(x['locationId'])) for x in row['nearbyCpoSeeds']}
            nearby_locations = [by_location_id[key] for key in nearby_ids if key in by_location_id]
            if not any(distance_m(source_point, (loc['latitude'], loc['longitude'])) <= 250
                       for loc in nearby_locations):
                counts['coarseNearbySeedsNotConfirmedByOfficialGps'] += 1
        for evse in source['evses']:
            counts['sourceEvsesWithAllowedConnector'] += 1
            counts['sourceStatus_' + str(evse.get('status'))] += 1
            options = exact_candidates(evse, source_point, by_evse_id)
            if len(options) == 1:
                counts['uniqueExactIdGpsKindPowerCandidates'] += 1
                if len(exact) < 50:
                    exact.append({'electroversePk': row['electroversePk'],
                                  'sourceEvsePk': evse['pk'], 'physicalReference': evse['physicalReference'],
                                  'match': options[0]})
            elif len(options) > 1:
                counts['ambiguousExactIdCandidates'] += 1
            else:
                counts['noExactIdGpsKindPowerCandidate'] += 1
    out = {'schemaVersion': 1, 'generatedAt': datetime.now(timezone.utc).isoformat(),
           'status': 'source_only_no_tariff_promotion', 'candidateQueueSize': len(ordered),
           'distinctPkWithDetails': len(rows), 'remainingPkWithoutDetails': len(ordered) - len(rows),
           'duplicatePkOccurrences': repeats, 'duplicatePkWithDifferentSourcePayload': conflicts,
           'counts': dict(sorted(counts.items())), 'uniqueExactExamplesFirst50': exact,
           'shards': shards}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: out[k] for k in ('status', 'distinctPkWithDetails', 'remainingPkWithoutDetails',
                                         'duplicatePkOccurrences', 'duplicatePkWithDifferentSourcePayload', 'counts')}))


if __name__ == '__main__':
    main()
