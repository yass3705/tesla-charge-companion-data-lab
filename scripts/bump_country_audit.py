#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from bump_direct_inventory import DATASET_API, decode_csv, get_bytes, get_json, is_bump_operator, norm, resolve_csv_resource

OUT = Path('reports/bump/country_audit_latest.json')
INSEE_FR = re.compile(r'^(?:\d{5}|2[ABab]\d{3})$')


def main() -> None:
    ds = get_json(DATASET_API)
    res = resolve_csv_resource(ds)
    rows, headers = decode_csv(get_bytes(str(res.get('url') or res.get('latest'))))
    rows = [r for r in rows if is_bump_operator(r.get('nom_operateur'))]

    valid = []
    invalid = []
    blank = []
    formats = Counter()
    for r in rows:
        code = norm(r.get('code_insee_commune'))
        formats['blank' if not code else ('fr_insee' if INSEE_FR.fullmatch(code) else 'other')] += 1
        sample = {
            'idStation': norm(r.get('id_station_itinerance')),
            'idPdc': norm(r.get('id_pdc_itinerance')),
            'name': norm(r.get('nom_station')),
            'address': norm(r.get('adresse_station')),
            'inseeCode': code,
            'coordinates': norm(r.get('coordonneesXY')),
        }
        if not code:
            blank.append(sample)
        elif INSEE_FR.fullmatch(code):
            valid.append(sample)
        else:
            invalid.append(sample)

    def unique_stations(items):
        return len({x['idStation'] for x in items if x['idStation']})

    payload = {
        'schemaVersion': '1.0.0',
        'sourceRowsBump': len(rows),
        'headers': headers,
        'classification': {
            'validFrenchInseePoints': len(valid),
            'validFrenchInseeStations': unique_stations(valid),
            'blankInseePoints': len(blank),
            'blankInseeStations': unique_stations(blank),
            'nonFrenchFormatPoints': len(invalid),
            'nonFrenchFormatStations': unique_stations(invalid),
        },
        'nonFrenchFormatExamples': invalid[:100],
        'blankInseeExamples': blank[:100],
        'decision': 'No country filter is applied by this audit. It only measures whether code_insee_commune can safely define the France perimeter.'
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload['classification'], ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
