#!/usr/bin/env python3
"""Build a sanitized station-level Kilowatt tariff overlay for V9.

Offline/read-only transformer: reads the committed public Kilowatt station inventory,
adds only station-specific tariff evidence, keeps CPO/site brand/access/tariff/status
provenance separate, and leaves unmatched tariffs unresolved.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

SRC = Path('reports/morocco/kilowatt/latest-public-station-inventory.json')
OUT = Path('reports/morocco/kilowatt/latest-v9-tariff-overlay.json')

ATLAS_FREE_URL = 'https://atlasrecharge.com/bornes/gratuites'
EXISTING_REPORT = 'reports/morocco/kilowatt/public-free-tariff-evidence-2026-08-24.json'

# Each rule is deliberately station/site-specific. We do not use a city-only matcher.
FREE_RULES = [
    {'id': 'al-mazar-mall', 'all': ['al', 'mazar'], 'site_brand': 'Al Mazar Mall'},
    {'id': 'carrefour-socco-alto', 'all': ['carrefour', 'socco', 'alto'], 'site_brand': 'Carrefour'},
    {'id': 'ibn-batouta-mall', 'all': ['ibn', 'batouta', 'mall'], 'site_brand': 'Ibn Batouta Mall'},
    {'id': 'totalenergies-tamesna', 'all': ['totalenergies', 'tamesna'], 'site_brand': 'TotalEnergies'},
    {'id': 'aswak-assalam-hay-riad', 'all': ['aswak', 'assalam', 'riad'], 'site_brand': 'Aswak Assalam'},
    {'id': 'sela-gallery', 'all': ['sela', 'gallery'], 'site_brand': 'Sela Gallery'},
    {'id': 'commune-agadir', 'all': ['commune', 'agadir'], 'site_brand': 'Commune d’Agadir'},
    {'id': 'parking-inbiaat-agadir', 'all': ['parking', 'inbiaat'], 'site_brand': None},
    {'id': 'almaz-mall-casablanca', 'all': ['almaz'], 'site_brand': 'Almaz Mall'},
    {'id': 'shell-exit-casablanca', 'all': ['shell', 'exit', 'casablanca'], 'site_brand': 'Shell'},
    {'id': 'shell-benguerir', 'all': ['shell', 'benguerir'], 'site_brand': 'Shell'},
    {'id': 'totalenergies-relais-mazagan', 'all': ['totalenergies', 'mazagan'], 'site_brand': 'TotalEnergies'},
    {'id': 'moulay-bousselham', 'all': ['moulay', 'bousselham'], 'site_brand': None},
    {'id': 'commune-saidia', 'all': ['commune', 'saidia'], 'site_brand': 'Commune de Saïdia'},
    {'id': 'marina-saidia', 'all': ['marina', 'saidia'], 'site_brand': 'Marina Saïdia'},
    {'id': 'carrefour-market-sale', 'all': ['carrefour', 'sale'], 'site_brand': 'Carrefour'},
    {'id': 'totalenergies-amskroud', 'any_sets': [['totalenergies', 'amskroud'], ['totalenergies', 'amsekroud']], 'site_brand': 'TotalEnergies'},
    {'id': 'winxo-argana', 'all': ['winxo', 'argana'], 'site_brand': 'Winxo'},
    {'id': 'station-sp-azemmour', 'all': ['station', 'sp', 'azemmour'], 'site_brand': 'SP'},
    {'id': 'hotel-barbas', 'all': ['hotel', 'barbas'], 'site_brand': 'Hotel Barbas'},
    {'id': 'petrom-boujdour', 'all': ['petrom', 'boujdour'], 'site_brand': 'Petrom'},
    {'id': 'residence-equinox-tantan', 'all': ['equinox', 'tantan'], 'site_brand': 'Résidence Equinox'},
    {'id': 'shell-safsaf', 'all': ['shell', 'safsaf'], 'site_brand': 'Shell'},
    {'id': 'alakhawayn-station', 'all': ['alakhawayn', 'station'], 'site_brand': None},
    {'id': 'parking-marchica-nador', 'all': ['marchica', 'nador'], 'site_brand': 'Parking Marchica'},
    {'id': 'winxo-ouarzazate', 'all': ['winxo', 'ouarzazate'], 'site_brand': 'Winxo'},
    {'id': 'winxo-oum-rabii', 'all': ['winxo', 'oum', 'rabii'], 'site_brand': 'Winxo'},
    {'id': 'carrefour-market-safi', 'all': ['carrefour', 'safi'], 'site_brand': 'Carrefour'},
    {'id': 'winxo-selouane', 'all': ['winxo', 'selouane'], 'site_brand': 'Winxo'},
    {'id': 'totalenergies-relais-taourirt', 'all': ['totalenergies', 'taourirt'], 'site_brand': 'TotalEnergies'},
    {'id': 'agora-park-taza', 'all': ['agora', 'taza'], 'site_brand': 'Agora Park'},
    {'id': 'aswak-assalam-temara', 'all': ['aswak', 'assalam', 'temara'], 'site_brand': 'Aswak Assalam'},
    {'id': 'sirocco-kasbah-zagora', 'all': ['sirocco', 'zagora'], 'site_brand': 'Sirocco Kasbah'},
]

EXPLICIT_SITE_BRANDS = [
    (['totalenergies'], 'TotalEnergies'),
    (['carrefour'], 'Carrefour'),
    (['ikea'], 'IKEA'),
    (['aswak', 'assalam'], 'Aswak Assalam'),
    (['aswakassalam'], 'Aswak Assalam'),
    (['shell'], 'Shell'),
    (['winxo'], 'Winxo'),
    (['sela', 'gallery'], 'Sela Gallery'),
    (['almaz'], 'Almaz Mall'),
]


def norm(value: str | None) -> str:
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = ''.join(ch for ch in value if not unicodedata.combining(ch)).lower()
    return ' '.join(re.findall(r'[a-z0-9]+', value))


def station_text(station: dict) -> str:
    return norm(' '.join(str(station.get(k) or '') for k in ('name', 'address', 'city')))


def matches(rule: dict, text: str) -> bool:
    tokens = set(text.split())
    if rule.get('all'):
        return all(norm(x) in tokens for x in rule['all'])
    for group in rule.get('any_sets') or []:
        if all(norm(x) in tokens for x in group):
            return True
    return False


def explicit_site_brand(station: dict, text: str) -> str | None:
    if station.get('site_brand'):
        return station['site_brand']
    tokens = set(text.split())
    for required, brand in EXPLICIT_SITE_BRANDS:
        if all(norm(x) in tokens for x in required):
            return brand
    return None


def main() -> None:
    src = json.loads(SRC.read_text())
    stations = [s for s in (src.get('stations') or []) if s.get('production_candidate') is True]
    if len(stations) != 43:
        raise SystemExit(f'expected 43 Kilowatt production candidates, got {len(stations)}')

    rows = []
    matched_rule_ids = set()
    free_count = 0
    unresolved_count = 0

    for station in stations:
        text = station_text(station)
        hits = [rule for rule in FREE_RULES if matches(rule, text)]
        if len(hits) > 1:
            raise SystemExit(f'ambiguous tariff evidence match for {station.get("id")}: {[h["id"] for h in hits]}')
        hit = hits[0] if hits else None
        brand = explicit_site_brand(station, text)
        if hit and hit.get('site_brand'):
            brand = hit['site_brand']

        row = {
            'station_id': str(station.get('id')),
            'name': station.get('name'),
            'address': station.get('address'),
            'city': station.get('city'),
            'latitude': station.get('latitude'),
            'longitude': station.get('longitude'),
            'cpo_operator': 'Kilowatt',
            'site_brand': brand,
            'app_source_access_network': station.get('app_source_access_network') or 'Kilowatt public web map',
            'status': station.get('status'),
            'status_source': station.get('status_source') or 'Kilowatt public web map',
            'tariff_channel': 'Kilowatt direct/public access',
            'tariff_currency': 'MAD',
            'tariff_mad': 0 if hit else None,
            'tariff_state': 'free_station_specific_public_evidence' if hit else 'unresolved',
            'tariff_production_eligible': bool(hit),
            'tariff_source': ATLAS_FREE_URL if hit else None,
            'tariff_source_role': 'station-specific public directory corroboration; not native Kilowatt tariff payload' if hit else None,
            'tariff_evidence_rule': hit['id'] if hit else None,
            'native_tariff_field_present': False,
            'production_candidate': True,
        }
        if hit:
            matched_rule_ids.add(hit['id'])
            free_count += 1
        else:
            unresolved_count += 1
        rows.append(row)

    unmatched_rules = sorted(rule['id'] for rule in FREE_RULES if rule['id'] not in matched_rule_ids)
    out = {
        'schema_version': 1,
        'country': 'MA',
        'network': 'Kilowatt',
        'source_inventory': str(SRC),
        'evidence_reports': [EXISTING_REPORT],
        'policy': {
            'read_only_offline_transformer': True,
            'station_specific_free_only': True,
            'no_city_only_paid_rule': True,
            'missing_native_tariff_does_not_mean_free': True,
            'modeling_dimensions_kept_separate': [
                'cpo_operator', 'site_brand', 'app_source_access_network', 'tariff_channel', 'status_source'
            ],
        },
        'summary': {
            'production_station_count': len(rows),
            'free_tariff_count': free_count,
            'unresolved_tariff_count': unresolved_count,
            'matched_free_evidence_rules': sorted(matched_rule_ids),
            'unmatched_free_evidence_rules': unmatched_rules,
        },
        'stations': rows,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(out['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
