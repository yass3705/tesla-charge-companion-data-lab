#!/usr/bin/env python3
"""Apply the sanitized fresh EVGO native-status overlay to the V9-oriented dataset.

This script is intentionally offline/read-only with respect to EVGO: it performs no
network requests. It keeps station metadata, geo, tariff and modeling dimensions
from the normalized sanitized dataset, and replaces only native status fields from
the newer sanitized status overlay. Matching is strict and fails closed.
"""
from __future__ import annotations

import collections
import copy
import json
from pathlib import Path

BASE = Path('reports/morocco/evgo/latest-normalized-stations.json')
OVERLAY = Path('reports/morocco/evgo/latest-status-overlay.json')
OUT = Path('reports/morocco/evgo/latest-production-stations.json')

ACTIVE_OCCUPIED = {'charging', 'suspendedev', 'finishing', 'preparing'}
OUT_OF_SERVICE = {'unavailable', 'faulted', 'offline', 'unknown'}


def operational_class(evse):
    status = str(evse.get('status') or '').lower()
    if evse.get('isLongTermUnavailable') or evse.get('isTemporarilyUnavailable'):
        return 'out_of_service'
    if status in ACTIVE_OCCUPIED:
        return 'occupied_or_active_session'
    if status == 'available' and evse.get('isAvailable') is True:
        return 'available'
    if status in OUT_OF_SERVICE:
        return 'out_of_service'
    return 'unknown'


def main():
    base = json.loads(BASE.read_text())
    overlay = json.loads(OVERLAY.read_text())
    out = copy.deepcopy(base)

    stations = out.get('stations') or []
    overlay_stations = overlay.get('stations') or []
    by_lid = {int(s['locationId']): s for s in overlay_stations}
    base_ids = {int(s['locationId']) for s in stations}
    overlay_ids = set(by_lid)
    if base_ids != overlay_ids:
        raise SystemExit(f'EVGO station-set mismatch: base={sorted(base_ids)} overlay={sorted(overlay_ids)}')

    native_counts = collections.Counter()
    op_counts = collections.Counter()
    updated = 0

    for station in stations:
        lid = int(station['locationId'])
        fresh = by_lid[lid]
        fresh_evses = {str(e['id']): e for e in (fresh.get('evses') or [])}
        base_evses = station.get('evses') or []
        base_evse_ids = {str(e['id']) for e in base_evses}
        if base_evse_ids != set(fresh_evses):
            raise SystemExit(
                f'EVGO EVSE-set mismatch locationId={lid}: '
                f'base={sorted(base_evse_ids)} overlay={sorted(fresh_evses)}'
            )

        station['updatedAt'] = fresh.get('updatedAt')
        station['status_source'] = 'EVGO native backend cp.evgo.ma'
        station['status_source_generated_at'] = overlay.get('source_generated_at')

        for evse in base_evses:
            f = fresh_evses[str(evse['id'])]
            for key in ('status', 'isAvailable', 'isLongTermUnavailable', 'isTemporarilyUnavailable'):
                evse[key] = f.get(key)
            evse['operational_class'] = operational_class(evse)
            native_counts[str(evse.get('status'))] += 1
            op_counts[evse['operational_class']] += 1
            updated += 1

    if len(stations) != 17 or updated != 43:
        raise SystemExit(f'EVGO cardinality invariant failed: stations={len(stations)} evses={updated}')

    for station in stations:
        lat, lon = station.get('latitude'), station.get('longitude')
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise SystemExit(f'EVGO missing GPS locationId={station.get("locationId")}')
        if not (20 <= lat <= 37 and -18 <= lon <= 0):
            raise SystemExit(f'EVGO non-Morocco GPS locationId={station.get("locationId")}: {lat},{lon}')

    overlay_generated_at = overlay.get('generated_at')
    source_generated_at = overlay.get('source_generated_at')
    if not overlay_generated_at or not source_generated_at:
        raise SystemExit('EVGO status overlay is missing generated_at/source_generated_at')

    out['schema_version'] = max(int(out.get('schema_version') or 0), 4)
    # Use the overlay publication timestamp rather than wall-clock time so the
    # complete snapshot is byte-reproducible for a given public overlay.
    out['generated_at'] = overlay_generated_at
    out['source_generated_at'] = source_generated_at
    out['source_status_overlay'] = str(OVERLAY)
    out.setdefault('policy', {})['fresh_native_status_overlay_applied'] = True
    out['policy']['fresh_status_fields_only'] = [
        'status', 'isAvailable', 'isLongTermUnavailable', 'isTemporarilyUnavailable', 'updatedAt'
    ]
    out['policy']['status_precedence'] = (
        'long/temporary unavailable flags -> out_of_service; '
        'charging/suspendedEV/finishing/preparing -> occupied_or_active_session; '
        'available requires isAvailable=true; unavailable/faulted/offline/unknown -> out_of_service; '
        'otherwise unknown'
    )
    out['policy']['modeling_dimensions_kept_separate'] = [
        'operator_cpo_candidate', 'site_brand', 'app_source', 'tariff_channel', 'status_source'
    ]
    out.setdefault('summary', {})['station_count'] = len(stations)
    out['summary']['station_count_with_native_geo'] = len(stations)
    out['summary']['evse_count'] = updated
    out['summary']['native_status_counts'] = dict(sorted(native_counts.items()))
    out['summary']['operational_class_counts'] = dict(sorted(op_counts.items()))

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({
        'source_generated_at': out.get('source_generated_at'),
        'stations': len(stations),
        'evses': updated,
        'gps_ok': len(stations),
        'native_status_counts': out['summary']['native_status_counts'],
        'operational_class_counts': out['summary']['operational_class_counts'],
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
