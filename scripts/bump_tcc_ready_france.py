#!/usr/bin/env python3
"""Build the conservative France-only Bump tariff snapshot for later TCC consolidation.

Inputs are the already-harvested Bump direct-CPO dataset and the deterministic tariff parser.
No new price is inferred. Foreign rows are excluded from the current snapshot by the explicit
Luxembourg postal marker present in Bump's official IRVE source. Unmatched/unmapped/no-price
cases remain quarantined and are never made rankable.
"""
from __future__ import annotations

import gzip
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from bump_variable_tariff_parser import parse_tariff

SRC = Path('data/national/bump_direct_tariffs_graphql_france.json.gz')
OUT = Path('data/national/bump_direct_tariffs_tcc_france.json.gz')
REPORT_JSON = Path('reports/bump/tcc_ready_france_latest.json')
REPORT_MD = Path('reports/bump/tcc_ready_france_latest.md')
LUX_POSTAL = re.compile(r'\bL-\d{4}\b', re.I)


def is_foreign_current_snapshot(station: dict[str, Any]) -> bool:
    # Current official Bump export's only confirmed foreign records are Luxembourg entries whose
    # addresses use the canonical L-#### postal form. This deliberately keeps the malformed
    # Annonay rows (code_insee_commune=7100) because their address/coordinates are in France.
    return bool(LUX_POSTAL.search(str(station.get('address') or '')))


def numeric_tariff(t: dict[str, Any]) -> bool:
    return any(isinstance(t.get(k), (int, float)) for k in ('energyEurPerKwh','timeEurPerHour','flatFeeEur'))


def pricing_components(t: dict[str, Any]) -> dict[str, Any]:
    return {
        'currency': t.get('currency') or 'EUR',
        'energyEurPerKwh': t.get('energyEurPerKwh'),
        'timeEurPerHour': t.get('timeEurPerHour'),
        'flatFeeEur': t.get('flatFeeEur'),
        'minPriceEur': t.get('minPriceEur'),
        'parkingText': t.get('parkingText'),
        'isTariffChangingInTime': bool(t.get('isTariffChangingInTime')),
    }


def source_text(t: dict[str, Any]) -> dict[str, Any]:
    return {'quick': t.get('quick'), 'short': t.get('short'), 'long': t.get('long')}


def main() -> None:
    raw = json.loads(gzip.decompress(SRC.read_bytes()))
    foreign = [s for s in raw.get('stations', []) if is_foreign_current_snapshot(s)]
    stations = [s for s in raw.get('stations', []) if not is_foreign_current_snapshot(s)]
    foreign_points = sum(len(s.get('points') or []) for s in foreign)

    # Snapshot guard: audit established 8 Luxembourg stations / 16 PDC on 2026-08-26.
    if len(foreign) != 8 or foreign_points != 16:
        raise RuntimeError(f'Unexpected foreign boundary drift: {len(foreign)} stations / {foreign_points} points')

    out_stations=[]
    point_counts=Counter()
    station_counts=Counter()
    tariff_groups=set()
    variable_patterns=Counter()
    variable_parse_failures=[]

    for s in stations:
        sid=s.get('idStationItinerance') or s.get('stationKey')
        match=s.get('match') or {}
        record={
            'stationId': sid,
            'name': s.get('name'),
            'address': s.get('address'),
            'latitude': s.get('latitude'),
            'longitude': s.get('longitude'),
            'matchStatus': match.get('status'),
            'locationId': match.get('locationId'),
            'points': [],
        }
        station_rankable=False
        station_unresolved=False

        if match.get('status') != 'matched':
            station_counts['unmatched_station'] += 1
            for p in s.get('points') or []:
                record['points'].append({
                    'idPdcItinerance': p.get('idPdcItinerance'),
                    'powerKw': p.get('powerKw'),
                    'status': 'unresolved_station_match',
                    'rankable': False,
                })
                point_counts['unresolved_station_match'] += 1
            out_stations.append(record)
            continue

        for p in match.get('points') or []:
            base={
                'idPdcItinerance': p.get('idPdcItinerance'),
                'powerKw': p.get('powerKw'),
                'appEvseId': p.get('appEvseId'),
                'tariffGroupId': p.get('tariffGroupId'),
            }
            if not p.get('mapped') or not isinstance(p.get('tariff'), dict):
                base.update({'status':'unresolved_evse_mapping','rankable':False})
                point_counts['unresolved_evse_mapping'] += 1
                station_unresolved=True
                record['points'].append(base)
                continue

            t=p['tariff']
            if p.get('tariffGroupId'):
                tariff_groups.add(str(p['tariffGroupId']))
            base['tariffId']=t.get('tariffId')
            base['tariffName']=t.get('name')
            base['components']=pricing_components(t)
            base['sourceText']=source_text(t)

            if bool(t.get('isTariffChangingInTime')):
                try:
                    parsed=parse_tariff(t)
                    base.update({'status':'rankable_rule_based','rankable':True,'rules':parsed['rules']})
                    key=json.dumps(parsed['rules'],ensure_ascii=False,sort_keys=True)
                    variable_patterns[key]+=1
                    point_counts['rankable_rule_based'] += 1
                    station_rankable=True
                except Exception as exc:
                    base.update({'status':'unresolved_variable_rule','rankable':False,'parseError':f'{type(exc).__name__}: {exc}'})
                    point_counts['unresolved_variable_rule'] += 1
                    station_unresolved=True
                    variable_parse_failures.append({'stationId':sid,'idPdc':p.get('idPdcItinerance'),'error':base['parseError']})
            elif numeric_tariff(t):
                # Static explicit API components are safe for ranking. Preserve the exact driver
                # text and attach deterministic rules when the known parser can express them.
                base.update({'status':'rankable_static','rankable':True})
                try:
                    base['rules']=parse_tariff(t)['rules']
                except Exception:
                    base['rules']=None
                point_counts['rankable_static'] += 1
                station_rankable=True
            else:
                base.update({'status':'unresolved_no_numeric_price','rankable':False})
                point_counts['unresolved_no_numeric_price'] += 1
                station_unresolved=True
            record['points'].append(base)

        if station_rankable:
            station_counts['with_rankable_point'] += 1
        if station_unresolved:
            station_counts['with_unresolved_point'] += 1
        out_stations.append(record)

    total_points=sum(len(s.get('points') or []) for s in out_stations)
    rankable_points=point_counts['rankable_static']+point_counts['rankable_rule_based']
    unresolved_points=total_points-rankable_points
    payload={
        'schemaVersion':'1.0.0',
        'dataset':'bump-direct-tariffs-tcc-france',
        'operator':'Bump',
        'country':'FR',
        'sourceGeneratedAt':raw.get('generatedAt'),
        'scope':{
            'directCpoOnly':True,
            'roamingIncluded':False,
            'anonymousDriverFacingTariff':True,
            'foreignStationsExcluded':True,
            'unresolvedCasesNeverRankable':True,
        },
        'counts':{
            'franceStations':len(out_stations),
            'francePoints':total_points,
            'excludedForeignStations':len(foreign),
            'excludedForeignPoints':foreign_points,
            'rankablePoints':rankable_points,
            'rankableCoveragePct':round(100*rankable_points/total_points,3) if total_points else 0,
            'unresolvedPoints':unresolved_points,
            'distinctResolvedTariffGroups':len(tariff_groups),
            'distinctRulePatterns':len(variable_patterns),
            **dict(point_counts),
            **{f'stations_{k}':v for k,v in station_counts.items()},
        },
        'variableParseFailures':variable_parse_failures,
        'excludedForeignStations':[
            {'stationId':s.get('idStationItinerance'),'name':s.get('name'),'address':s.get('address')} for s in foreign
        ],
        'stations':out_stations,
    }
    if variable_parse_failures:
        raise RuntimeError(f'Variable tariff parser failures: {len(variable_parse_failures)}')
    if total_points != 2252 or len(out_stations) != 1506:
        raise RuntimeError(f'Unexpected France snapshot size: {len(out_stations)} stations / {total_points} points')

    OUT.parent.mkdir(parents=True,exist_ok=True)
    REPORT_JSON.parent.mkdir(parents=True,exist_ok=True)
    encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
    OUT.write_bytes(gzip.compress(encoded,compresslevel=9,mtime=0))
    summary={k:v for k,v in payload.items() if k not in ('stations',)}
    REPORT_JSON.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    c=payload['counts']
    lines=[
        '# Bump France — TCC-ready snapshot', '',
        f"- France stations: **{c['franceStations']}**",
        f"- France charge points: **{c['francePoints']}**",
        f"- Rankable points: **{c['rankablePoints']} ({c['rankableCoveragePct']}%)**",
        f"- Static points: **{c.get('rankable_static',0)}**",
        f"- Rule-based points: **{c.get('rankable_rule_based',0)}**",
        f"- Unresolved EVSE mappings: **{c.get('unresolved_evse_mapping',0)}**",
        f"- Unresolved station-match points: **{c.get('unresolved_station_match',0)}**",
        f"- Tariff objects without numeric price: **{c.get('unresolved_no_numeric_price',0)}**",
        f"- Foreign excluded: **{c['excludedForeignStations']} stations / {c['excludedForeignPoints']} points**",
        f"- Resolved tariff groups represented: **{c['distinctResolvedTariffGroups']}**",
        f"- Parsed rule patterns represented: **{c['distinctRulePatterns']}**",
        '',
        'Unresolved cases are intentionally retained but non-rankable. No roaming tariff is included.', ''
    ]
    REPORT_MD.write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(c,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
