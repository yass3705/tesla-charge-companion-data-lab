#!/usr/bin/env python3
"""Normalize the sanitized EVGO public inventory already committed by read-only probes.

No backend requests are made here. The script reads reports/morocco/evgo/latest-pin-hydration.json
and emits a compact station inventory that keeps CPO/operator, site brand, app source, tariff channel
and status source distinct.

EVGO-specific business rule: when the native EVGO data exposes no tariff (tariffId is null), the
station/EVSE is treated as free (0 MAD). This rule applies to EVGO only and must not be generalized
to other operators.
"""
# This derived-data step is intentionally offline: it never contacts the EVGO backend.
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

SRC = Path('reports/morocco/evgo/latest-pin-hydration.json')
OUT = Path('reports/morocco/evgo/latest-normalized-stations.json')


def main() -> None:
    raw = json.loads(SRC.read_text())
    v1 = raw.get('versions', {}).get('v1', {})
    rows = []
    status_counts = Counter()
    tariff_ids = Counter()
    free_evse_count = 0

    for item in v1.get('locations', []):
        loc = item.get('location') or {}
        evses = []
        for zone in loc.get('zones') or []:
            for evse in zone.get('evses') or []:
                status = evse.get('status')
                if status:
                    status_counts[str(status)] += 1
                tariff_id = evse.get('tariffId')
                if tariff_id is not None:
                    tariff_ids[str(tariff_id)] += 1
                is_free = tariff_id is None
                if is_free:
                    free_evse_count += 1
                evses.append({
                    'id': evse.get('id'),
                    'identifier': evse.get('identifier'),
                    'status': status,
                    'isAvailable': evse.get('isAvailable'),
                    'currentType': evse.get('currentType'),
                    'maxPower': evse.get('maxPower'),
                    'operatorId': evse.get('operatorId'),
                    'networkId': evse.get('networkId'),
                    'operatedBy': evse.get('operatedBy'),
                    'tariffId': tariff_id,
                    'isFree': is_free,
                    'priceMAD': 0 if is_free else None,
                    'price_interpretation': (
                        'EVGO-specific rule: missing native price/tariff is treated as free.'
                        if is_free else
                        'A native EVGO tariff reference exists; do not infer its numeric price here.'
                    ),
                    'connectors': [
                        {
                            'id': c.get('id'),
                            'name': c.get('name'),
                            'format': c.get('format'),
                            'status': c.get('status'),
                        }
                        for c in (evse.get('connectors') or [])
                    ],
                })
        rows.append({
            'locationId': loc.get('id', item.get('id')),
            'name': loc.get('name'),
            'address': loc.get('address'),
            'timezone': loc.get('timezone'),
            'updatedAt': loc.get('updatedAt'),
            'site_brand': None,
            'operator_cpo_candidate': 'Nareva Services / EVGO',
            'platform_provider': 'AMPECO',
            'app_source': 'EVGO',
            'status_source': 'EVGO native backend cp.evgo.ma',
            'tariff_channel': 'EVGO native',
            'tariff_interpretation': 'EVGO only: if no native price/tariff is present, treat charging as free (0 MAD).',
            'evses': evses,
        })

    out = {
        'schema_version': 1,
        'source_report': str(SRC),
        'source_host': 'cp.evgo.ma',
        'policy': {
            'derived_from_sanitized_public_report_only': True,
            'backend_requests_made': False,
            'evgo_missing_tariff_means_free': True,
            'evgo_missing_tariff_price_mad': 0,
            'rule_scope': 'EVGO only; never generalize missing-price=free to other operators.',
            'modeling_dimensions_kept_separate': [
                'operator_cpo_candidate', 'site_brand', 'app_source', 'tariff_channel', 'status_source'
            ],
        },
        'summary': {
            'station_count': len(rows),
            'evse_count': sum(len(x['evses']) for x in rows),
            'status_counts': dict(sorted(status_counts.items())),
            'non_null_tariff_ids': dict(sorted(tariff_ids.items())),
            'free_evse_count_by_evgo_missing_tariff_rule': free_evse_count,
        },
        'stations': rows,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(out['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
