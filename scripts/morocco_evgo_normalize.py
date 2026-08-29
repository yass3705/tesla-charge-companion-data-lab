#!/usr/bin/env python3
"""Normalize the sanitized EVGO public report into a V9-oriented station model.

No network calls are made here. The input is the already-sanitized public report
written by morocco_evgo_pin_hydration_probe.py. Pin geo is joined to locations by
underlyingLocationIds/location id, while raw native EVSE state remains preserved.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
from pathlib import Path

SRC = Path('reports/morocco/evgo/latest-pin-hydration.json')
OUT = Path('reports/morocco/evgo/latest-normalized-stations.json')

ACTIVE_OCCUPIED = {'charging', 'suspendedev', 'finishing', 'preparing'}
OUT_OF_SERVICE = {'unavailable', 'faulted', 'offline', 'unknown'}


def parse_geo(value):
    if not isinstance(value, str):
        return None, None
    try:
        a, b = [x.strip() for x in value.split(',', 1)]
        lat, lon = float(a), float(b)
    except Exception:
        return None, None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, None
    return lat, lon


def operational_class(evse):
    status = str(evse.get('status') or '').lower()
    if evse.get('isLongTermUnavailable') or evse.get('isTemporarilyUnavailable'):
        return 'out_of_service'
    if evse.get('isAvailable') is True and status == 'available':
        return 'available'
    if status in ACTIVE_OCCUPIED:
        return 'occupied_or_active_session'
    if status in OUT_OF_SERVICE:
        return 'out_of_service'
    return 'unknown'


def station_brand(name):
    n = (name or '').strip()
    if n.lower().startswith('marjane'):
        return 'Marjane'
    return None


def main():
    src = json.loads(SRC.read_text())
    # v1 and v2 are currently equivalent. Prefer v1 deterministically and retain
    # source version metadata so a future divergence can be detected explicitly.
    data = src['versions']['v1']
    pins = {}
    for p in data.get('pins') or []:
        ids = p.get('underlyingLocationIds') or []
        for lid in ids:
            pins[int(lid)] = p

    stations = []
    status_counts = collections.Counter()
    op_counts = collections.Counter()
    evse_count = 0

    for item in data.get('locations') or []:
        loc = item.get('location')
        if not isinstance(loc, dict):
            continue
        lid = int(loc['id'])
        pin = pins.get(lid, {})
        lat, lon = parse_geo(pin.get('geo'))
        evses = []
        for zone in loc.get('zones') or []:
            for raw in zone.get('evses') or []:
                if not isinstance(raw, dict):
                    continue
                status = raw.get('status')
                op = operational_class(raw)
                status_counts[str(status)] += 1
                op_counts[op] += 1
                evse_count += 1
                tariff_id = raw.get('tariffId')
                evses.append({
                    'id': raw.get('id'),
                    'identifier': raw.get('identifier'),
                    'status': status,
                    'operational_class': op,
                    'isAvailable': raw.get('isAvailable'),
                    'isLongTermUnavailable': raw.get('isLongTermUnavailable'),
                    'isTemporarilyUnavailable': raw.get('isTemporarilyUnavailable'),
                    'currentType': raw.get('currentType'),
                    'maxPower': raw.get('maxPower'),
                    'operatorId': raw.get('operatorId'),
                    'networkId': raw.get('networkId'),
                    'operatedBy': raw.get('operatedBy'),
                    'tariffId': tariff_id,
                    'isFree': tariff_id is None,
                    'priceMAD': 0 if tariff_id is None else None,
                    'price_interpretation': 'EVGO-specific rule: missing native price/tariff is treated as free.' if tariff_id is None else 'Resolve referenced native tariff separately.',
                    'connectors': [
                        {k: c.get(k) for k in ('id', 'name', 'format', 'status')}
                        for c in (raw.get('connectors') or []) if isinstance(c, dict)
                    ],
                })

        stations.append({
            'locationId': lid,
            'name': loc.get('name'),
            'address': loc.get('address'),
            'latitude': lat,
            'longitude': lon,
            'geo_source': 'EVGO native public /app/pins geo',
            'timezone': loc.get('timezone'),
            'updatedAt': loc.get('updatedAt'),
            'site_brand': station_brand(loc.get('name')),
            'operator_cpo_candidate': 'Nareva Services / EVGO',
            'platform_provider': 'AMPECO',
            'app_source': 'EVGO',
            'status_source': 'EVGO native backend cp.evgo.ma',
            'tariff_channel': 'EVGO native',
            'tariff_interpretation': 'EVGO only: if no native price/tariff is present, treat charging as free (0 MAD).',
            'pin_availability': pin.get('av'),
            'evses': evses,
        })

    out = {
        'schema_version': 2,
        'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'source_generated_at': src.get('generated_at'),
        'source_report': str(SRC),
        'source_host': src.get('host'),
        'source_api_version': 'v1',
        'policy': {
            'derived_from_sanitized_public_report_only': True,
            'backend_requests_made': False,
            'geo_from_native_public_pins': True,
            'evgo_missing_tariff_means_free': True,
            'evgo_missing_tariff_price_mad': 0,
            'rule_scope': 'EVGO only; never generalize missing-price=free to other operators.',
            'suspendedEV_operational_class': 'occupied_or_active_session',
            'modeling_dimensions_kept_separate': [
                'operator_cpo_candidate', 'site_brand', 'app_source',
                'tariff_channel', 'status_source'
            ],
        },
        'summary': {
            'station_count': len(stations),
            'station_count_with_native_geo': sum(1 for s in stations if s['latitude'] is not None and s['longitude'] is not None),
            'evse_count': evse_count,
            'native_status_counts': dict(sorted(status_counts.items())),
            'operational_class_counts': dict(sorted(op_counts.items())),
        },
        'stations': stations,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(out['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
