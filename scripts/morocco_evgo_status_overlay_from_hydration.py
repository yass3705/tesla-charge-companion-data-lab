#!/usr/bin/env python3
"""Derive a sanitized EVGO status overlay from the freshly hydrated public snapshot.

Offline transformer only: reads the output of morocco_evgo_pin_hydration_probe.py,
selects the API version that exposes the complete 17-station / 43-EVSE inventory,
and persists only native fields required for V9 operational status classification.
No network requests, credentials, sessions or mutations are performed here.
"""
from __future__ import annotations

import json
from pathlib import Path

SRC = Path('reports/morocco/evgo/latest-pin-hydration.json')
OUT = Path('reports/morocco/evgo/latest-status-overlay.json')
STATUS_FIELDS = ('id', 'status', 'isAvailable', 'isLongTermUnavailable', 'isTemporarilyUnavailable')


def extract_version(name, entry):
    stations = []
    evse_count = 0
    for item in entry.get('locations') or []:
        loc = item.get('location') if isinstance(item, dict) else None
        if not isinstance(loc, dict):
            continue
        lid = loc.get('id') if loc.get('id') is not None else item.get('id')
        evses = []
        for zone in loc.get('zones') or []:
            if not isinstance(zone, dict):
                continue
            for evse in zone.get('evses') or []:
                if not isinstance(evse, dict) or evse.get('id') is None:
                    continue
                evses.append({k: evse.get(k) for k in STATUS_FIELDS})
        stations.append({
            'locationId': int(lid),
            'updatedAt': loc.get('updatedAt'),
            'evses': evses,
        })
        evse_count += len(evses)
    return {'version': name, 'stations': stations, 'station_count': len(stations), 'evse_count': evse_count}


def main():
    src = json.loads(SRC.read_text())
    candidates = [extract_version(name, entry) for name, entry in (src.get('versions') or {}).items() if isinstance(entry, dict)]
    complete = [c for c in candidates if c['station_count'] == 17 and c['evse_count'] == 43]
    if not complete:
        raise SystemExit('No EVGO public API version yielded the required 17 stations / 43 EVSE: ' + json.dumps(candidates))

    # Prefer the highest API version among complete snapshots, but never combine versions.
    chosen = sorted(complete, key=lambda c: c['version'])[-1]
    ids = [s['locationId'] for s in chosen['stations']]
    if len(ids) != len(set(ids)):
        raise SystemExit('Duplicate EVGO locationId in fresh hydration snapshot')
    all_evse_ids = [str(e['id']) for s in chosen['stations'] for e in s['evses']]
    if len(all_evse_ids) != len(set(all_evse_ids)):
        raise SystemExit('Duplicate EVGO EVSE id in fresh hydration snapshot')

    out = {
        'schema_version': 2,
        'generated_at': src.get('generated_at'),
        'source_generated_at': src.get('generated_at'),
        'source_host': src.get('host'),
        'source_api_version': chosen['version'],
        'policy': {
            'derived_from_same_run_public_hydration': True,
            'read_only': True,
            'no_login': True,
            'no_credentials': True,
            'status_fields_only': True,
        },
        'stations': chosen['stations'],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({
        'source_generated_at': out['source_generated_at'],
        'api_version': out['source_api_version'],
        'stations': chosen['station_count'],
        'evses': chosen['evse_count'],
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
