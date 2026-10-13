#!/usr/bin/env python3
"""Build a national UK CPO seed queue for read-only Electroverse collection.

Only public, active normal/Type 2/CCS connectors are retained. This queue is
not evidence that a CPO station is partnered with Electroverse or priced there.
"""
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pilot_electra_nl_emsp import kind

SOURCES = (
    'uk_validated_open_feeds', 'uk_gridserve_v9', 'uk_connected_kerb_v9',
    'uk_ubitricity_v9', 'uk_source_ev_pcpr_v9', 'uk_allego_uk_pcpr_v9',
    'uk_blink_pcpr_v9', 'uk_eco_movement_pcpr_v9',
)
OUT = Path('data/platforms/electroverse/uk-national-cpo-seeds.json.gz')
ACTIVE = {'AVAILABLE', 'CHARGING'}


def seeds_for_dataset(data, source_file):
    rows = []
    counts = Counter()
    for source in data.get('sources') or []:
        for loc in source.get('locations') or []:
            counts['locationsSeen'] += 1
            if loc.get('publish') is not True or loc.get('country_code') != 'GB':
                counts['notPublicOrCountryRejected'] += 1
                continue
            coordinates = loc.get('coordinates') or {}
            try:
                lat = float(coordinates.get('latitude'))
                lon = float(coordinates.get('longitude'))
            except (TypeError, ValueError):
                counts['invalidCoordinates'] += 1
                continue
            if not (49 <= lat <= 61.5 and -9 <= lon <= 2.5):
                counts['outsideUkEnvelope'] += 1
                continue
            eligible = []
            for evse in loc.get('evses') or []:
                if evse.get('status') not in ACTIVE:
                    continue
                connectors = [{'id': c.get('id'), 'kind': kind(c.get('standard')),
                               'maxElectricPowerW': c.get('max_electric_power')}
                              for c in evse.get('connectors') or [] if kind(c.get('standard'))]
                if connectors:
                    eligible.append({'evseId': evse.get('evse_id') or evse.get('evseId'),
                                     'status': evse.get('status'), 'connectors': connectors})
            if not eligible:
                counts['withoutEligibleActiveConnector'] += 1
                continue
            counts['eligibleLocations'] += 1
            counts['eligibleEvses'] += len(eligible)
            counts['eligibleConnectors'] += sum(len(e['connectors']) for e in eligible)
            rows.append({'sourceFile': source_file, 'cpo': source.get('name'),
                         'locationId': str(loc.get('id') or ''),
                         'name': loc.get('name'), 'latitude': lat, 'longitude': lon,
                         'evses': eligible})
    return rows, counts


def main():
    rows = []
    reports = {}
    for source in SOURCES:
        path = Path(f'data/national/{source}.json.gz')
        raw = path.read_bytes()
        data = json.loads(gzip.decompress(raw))
        selected, counts = seeds_for_dataset(data, source)
        rows.extend(selected)
        reports[source] = {'sha256': hashlib.sha256(raw).hexdigest(), 'counts': dict(counts)}
    rows.sort(key=lambda x: (x['sourceFile'], x['cpo'] or '', x['locationId'], x['latitude'], x['longitude']))
    payload = {'schemaVersion': 1, 'generatedAt': datetime.now(timezone.utc).isoformat(),
               'country': 'GB', 'status': 'cpo_seed_queue_only_no_emsp_claim',
               'sources': reports, 'locationCount': len(rows), 'locations': rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(gzip.compress(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()))
    print(json.dumps({'path': str(OUT), 'locationCount': len(rows),
                      'bySource': {k: v['counts'] for k, v in reports.items()}}))


if __name__ == '__main__':
    main()
