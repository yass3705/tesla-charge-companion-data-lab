#!/usr/bin/env python3
"""Probe documented public WATT.ma OCPI/read-only surfaces.

Safety contract:
- GET only
- no login, tokens, cookies or partner credentials
- no OCPI command/session routes
- outputs a sanitized schema/count/sample summary, not raw payload dumps
"""
from __future__ import annotations

import collections
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = 'https://map.watt.ma'
OUT = Path('artifacts/morocco-watt-ocpi-public-probe/summary.json')
UA = 'TeslaChargeCompanion-PublicReadOnlyProbe/1.0'


def get_json(path: str) -> dict:
    url = BASE + path
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            ctype = r.headers.get('content-type', '')
            status = r.status
    except urllib.error.HTTPError as e:
        raw = e.read()
        ctype = e.headers.get('content-type', '') if e.headers else ''
        status = e.code
    result = {
        'url': url,
        'http_status': status,
        'content_type': ctype,
        'bytes': len(raw),
        'json': False,
        'payload': None,
        'body_prefix': raw[:160].decode('utf-8', errors='replace'),
    }
    try:
        result['payload'] = json.loads(raw.decode('utf-8'))
        result['json'] = True
        result['body_prefix'] = None
    except Exception:
        pass
    return result


def records_from(payload, keys):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def text(record, *keys):
    if not isinstance(record, dict):
        return None
    for key in keys:
        value = record.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()
    return None


def summarize_locations(probe: dict) -> dict:
    payload = probe.get('payload')
    rows = records_from(payload, ('data', 'locations', 'items', 'results'))
    top_keys = sorted(payload.keys()) if isinstance(payload, dict) else None
    operator_counts = collections.Counter()
    status_counts = collections.Counter()
    samples = []
    fastvolt_morocco_mall_id = None

    for row in rows:
        if not isinstance(row, dict):
            continue
        operator = text(row, 'operator', 'operator_name', 'network', 'cpo', 'party_id')
        status = text(row, 'status')
        if operator:
            operator_counts[operator] += 1
        if status:
            status_counts[status] += 1
        name = text(row, 'name', 'station_name', 'title')
        rid = text(row, 'id', 'stationId', 'station_id', 'location_id')
        blob = json.dumps(row, ensure_ascii=False).lower()
        if 'fastvolt' in blob and 'morocco mall' in blob and rid:
            fastvolt_morocco_mall_id = rid
        if len(samples) < 5:
            samples.append({
                'id': rid,
                'name': name,
                'operator': operator,
                'status': status,
                'top_level_fields': sorted(row.keys()),
            })

    return {
        'record_count': len(rows),
        'top_level_keys': top_keys,
        'operator_counts': dict(operator_counts.most_common(30)),
        'status_counts': dict(status_counts.most_common(20)),
        'sample_records_sanitized': samples,
        'fastvolt_morocco_mall_id': fastvolt_morocco_mall_id,
    }


def summarize_tariffs(probe: dict) -> dict:
    payload = probe.get('payload')
    rows = records_from(payload, ('data', 'tariffs', 'items', 'results'))
    top_keys = sorted(payload.keys()) if isinstance(payload, dict) else None
    currency_counts = collections.Counter()
    samples = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        currency = text(row, 'currency')
        if currency:
            currency_counts[currency] += 1
        if len(samples) < 5:
            samples.append({
                'id': text(row, 'id', 'tariff_id'),
                'currency': currency,
                'top_level_fields': sorted(row.keys()),
            })
    return {
        'record_count': len(rows),
        'top_level_keys': top_keys,
        'currency_counts': dict(currency_counts.most_common(20)),
        'sample_records_sanitized': samples,
    }


def public_meta(probe: dict) -> dict:
    return {k: probe.get(k) for k in ('url', 'http_status', 'content_type', 'bytes', 'json', 'body_prefix')}


def main() -> None:
    locations = get_json('/locations')
    tariffs = get_json('/tariffs')
    loc_summary = summarize_locations(locations)
    tariff_summary = summarize_tariffs(tariffs)

    live = None
    station_id = loc_summary.get('fastvolt_morocco_mall_id')
    if station_id:
        live = get_json('/api/live-status?stationId=' + urllib.parse.quote(station_id, safe=''))

    out = {
        'schema_version': 1,
        'country': 'MA',
        'surface': 'WATT.ma public OCPI/roaming diagnostic',
        'policy': {
            'read_only': True,
            'http_methods': ['GET'],
            'credentials_used': False,
            'cookies_used': False,
            'session_or_command_routes_used': False,
            'raw_payloads_committed': False,
            'modeling_dimensions_kept_separate': [
                'cpo_operator', 'site_brand', 'app_source_access_network', 'tariff_channel', 'status_source'
            ],
            'attribution_rule': 'WATT.ma observation is roaming/aggregation evidence only and never overwrites independently validated native CPO attribution.',
        },
        'locations_endpoint': public_meta(locations),
        'locations_summary': loc_summary,
        'tariffs_endpoint': public_meta(tariffs),
        'tariffs_summary': tariff_summary,
        'fastvolt_morocco_mall_live_status_probe': public_meta(live) if live else {'performed': False, 'reason': 'no exact station id discovered from public locations payload'},
        'fastvolt_morocco_mall_live_status_payload': live.get('payload') if live and live.get('json') else None,
        'production_decision': 'diagnostic_only_until_source_contract_and_identity_mapping_are_validated',
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({
        'locations_status': locations.get('http_status'),
        'locations_json': locations.get('json'),
        'locations_records': loc_summary.get('record_count'),
        'tariffs_status': tariffs.get('http_status'),
        'tariffs_json': tariffs.get('json'),
        'tariff_records': tariff_summary.get('record_count'),
        'fastvolt_morocco_mall_id': station_id,
        'live_status': live.get('http_status') if live else None,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
