#!/usr/bin/env python3
"""Probe public WATT.ma read-only charging-data surfaces.

Safety contract:
- GET only
- no login, tokens, cookies or partner credentials
- no OCPI command/session routes
- only invokes /api/chargers after static same-origin public-client evidence
- outputs sanitized schema/count/sample summaries, not raw payload dumps
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
UA = 'TeslaChargeCompanion-PublicReadOnlyProbe/1.1'


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


def numeric(record, *keys):
    if not isinstance(record, dict):
        return None
    for key in keys:
        value = record.get(key)
        if isinstance(value, (int, float)):
            return value
        try:
            if value is not None and str(value).strip():
                return float(value)
        except Exception:
            pass
    return None


def summarize_station_rows(probe: dict) -> dict:
    payload = probe.get('payload')
    rows = records_from(payload, ('data', 'chargers', 'stations', 'locations', 'items', 'results'))
    top_keys = sorted(payload.keys()) if isinstance(payload, dict) else None
    operator_counts = collections.Counter()
    status_counts = collections.Counter()
    city_counts = collections.Counter()
    power_counts = collections.Counter()
    samples = []
    fastvolt_morocco_mall_id = None
    shell_rows = 0
    total_rows = 0
    kilowatt_rows = 0
    fastvolt_rows = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        operator = text(row, 'operator', 'operator_name', 'network', 'networkName', 'cpo', 'party_id')
        status = text(row, 'status', 'availability', 'liveStatus')
        city = text(row, 'city', 'locality')
        power = numeric(row, 'power', 'power_kw', 'maxPower', 'max_power_kw')
        if operator:
            operator_counts[operator] += 1
        if status:
            status_counts[status] += 1
        if city:
            city_counts[city] += 1
        if power is not None:
            power_counts[str(power)] += 1
        name = text(row, 'name', 'station_name', 'stationName', 'title')
        rid = text(row, 'id', 'stationId', 'station_id', 'location_id')
        blob = json.dumps(row, ensure_ascii=False).lower()
        if 'fastvolt' in blob:
            fastvolt_rows += 1
        if 'kilowatt' in blob:
            kilowatt_rows += 1
        if 'totalenergies' in blob or 'total energies' in blob:
            total_rows += 1
        if 'shell' in blob or 'vivo energy' in blob:
            shell_rows += 1
        if 'fastvolt' in blob and 'morocco mall' in blob and rid:
            fastvolt_morocco_mall_id = rid
        if len(samples) < 8:
            samples.append({
                'id': rid,
                'name': name,
                'city': city,
                'operator': operator,
                'status': status,
                'power_kw': power,
                'top_level_fields': sorted(row.keys()),
            })

    return {
        'record_count': len(rows),
        'top_level_keys': top_keys,
        'operator_counts': dict(operator_counts.most_common(40)),
        'status_counts': dict(status_counts.most_common(20)),
        'city_counts_top20': dict(city_counts.most_common(20)),
        'power_counts_top20': dict(power_counts.most_common(20)),
        'network_text_match_counts': {
            'fastvolt': fastvolt_rows,
            'kilowatt': kilowatt_rows,
            'totalenergies': total_rows,
            'shell_or_vivo': shell_rows,
        },
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
    # Documented OCPI-looking paths are retained for diagnostics; they currently render HTML.
    locations = get_json('/locations')
    tariffs = get_json('/tariffs')
    loc_summary = summarize_station_rows(locations)
    tariff_summary = summarize_tariffs(tariffs)

    # /api/chargers was discovered by static inspection of the public same-origin client.
    chargers = get_json('/api/chargers')
    chargers_summary = summarize_station_rows(chargers)

    live = None
    station_id = chargers_summary.get('fastvolt_morocco_mall_id')
    if station_id:
        live = get_json('/api/live-status?stationId=' + urllib.parse.quote(station_id, safe=''))

    out = {
        'schema_version': 2,
        'country': 'MA',
        'surface': 'WATT.ma public roaming/aggregation diagnostic',
        'policy': {
            'read_only': True,
            'http_methods': ['GET'],
            'credentials_used': False,
            'cookies_used': False,
            'session_or_command_routes_used': False,
            'raw_payloads_committed': False,
            'api_chargers_discovery': 'literal same-origin route found by static inspection of public map client; invoked only by GET',
            'modeling_dimensions_kept_separate': [
                'cpo_operator', 'site_brand', 'app_source_access_network', 'tariff_channel', 'status_source'
            ],
            'attribution_rule': 'WATT.ma observation is roaming/aggregation evidence only and never overwrites independently validated native CPO attribution.',
        },
        'locations_endpoint': public_meta(locations),
        'locations_summary': loc_summary,
        'tariffs_endpoint': public_meta(tariffs),
        'tariffs_summary': tariff_summary,
        'chargers_endpoint': public_meta(chargers),
        'chargers_summary': chargers_summary,
        'fastvolt_morocco_mall_live_status_probe': public_meta(live) if live else {'performed': False, 'reason': 'no exact station id discovered from public charger payload'},
        'fastvolt_morocco_mall_live_status_payload_sanitized': live.get('payload') if live and live.get('json') else None,
        'production_decision': 'secondary_diagnostic_only_until_identity_and_provenance_are_reconciled_with_native_cpo_sources',
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({
        'chargers_status': chargers.get('http_status'),
        'chargers_json': chargers.get('json'),
        'chargers_records': chargers_summary.get('record_count'),
        'network_text_match_counts': chargers_summary.get('network_text_match_counts'),
        'operator_counts': chargers_summary.get('operator_counts'),
        'status_counts': chargers_summary.get('status_counts'),
        'fastvolt_morocco_mall_id': station_id,
        'live_status': live.get('http_status') if live else None,
        'live_json': live.get('json') if live else None,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
