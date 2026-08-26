#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path


def family_of(station_id: object) -> str:
    value = ''.join(ch for ch in str(station_id or '').upper() if ch.isalnum())
    for prefix in ('FRETI', 'FRESE', 'FRG10', 'FRCAR', 'FRSUA'):
        if value.startswith(prefix):
            return prefix
    return value[:5] or 'UNKNOWN'


def in_box(lat: float, lon: float, lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> bool:
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def looks_like_france(lat: float, lon: float) -> bool:
    # Metropolitan France + Corsica, then the principal French overseas territories.
    boxes = (
        (41.0, 52.0, -6.5, 11.0),       # metropolitan France + Corsica
        (15.5, 16.7, -62.0, -60.8),     # Guadeloupe / Saint-Martin area
        (14.2, 15.1, -61.5, -60.6),     # Martinique
        (2.0, 6.0, -55.5, -51.0),       # French Guiana
        (-22.0, -20.0, 54.5, 56.0),     # Réunion
        (-13.2, -12.4, 44.8, 45.5),     # Mayotte
        (46.6, 47.2, -56.7, -56.0),     # Saint-Pierre-et-Miquelon
    )
    return any(in_box(lat, lon, *box) for box in boxes)


def normalize_pair(lat: object, lon: object) -> tuple[float | None, float | None, bool]:
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return None, None, False

    current_ok = looks_like_france(lat_f, lon_f)
    swapped_ok = looks_like_france(lon_f, lat_f)
    if current_ok or not swapped_ok:
        return lat_f, lon_f, False
    return lon_f, lat_f, True


def normalize_inventory(path: Path) -> dict:
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        data = json.load(handle)

    corrected = Counter()
    unresolved = Counter()
    for station in data.get('stations', []):
        family = family_of(station.get('stationId'))
        lat, lon, swapped = normalize_pair(station.get('latitude'), station.get('longitude'))
        if lat is None or lon is None:
            unresolved[family] += 1
            continue
        if swapped:
            station['latitude'] = lat
            station['longitude'] = lon
            corrected[family] += 1

    summary = {
        'correctedStations': sum(corrected.values()),
        'correctedByFamily': dict(corrected),
        'missingOrInvalidByFamily': dict(unresolved),
        'policy': 'keep coordinates already located in France; otherwise swap only when the swapped orientation lands in France',
    }
    data['coordinateNormalization'] = summary

    with gzip.open(path, 'wt', encoding='utf-8', compresslevel=9) as handle:
        json.dump(data, handle, ensure_ascii=False, separators=(',', ':'))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('path', nargs='?', default='data/national/etotem_direct_stations_france.json.gz')
    args = parser.parse_args()
    summary = normalize_inventory(Path(args.path))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
