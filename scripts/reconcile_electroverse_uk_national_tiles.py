#!/usr/bin/env python3
"""Build a coarse GraphQL lookup queue; never attach an EVSE or tariff here."""
import gzip
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SEEDS = Path('data/platforms/electroverse/uk-national-cpo-seeds.json.gz')
TILES = Path('reports/emsp-national/electroverse-uk-tiles')
OUT = Path('data/platforms/electroverse/uk-coarse-location-candidates.json.gz')
REPORT = Path('reports/emsp-national/electroverse-uk-coarse-candidates.json')
CELL = 0.005


def distance_m(a, b):
    lat = math.radians(a['latitude'])
    return round(111195 * math.hypot(a['latitude'] - b['latitude'],
                                      (a['longitude'] - b['longitude']) * math.cos(lat)))


def nearby(hit, grid, limit_m=250):
    cell = (math.floor(hit['latitude'] / CELL), math.floor(hit['longitude'] / CELL))
    found = []
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for seed in grid.get((cell[0] + di, cell[1] + dj), ()):
                meters = distance_m(hit, seed)
                if meters <= limit_m:
                    found.append({'sourceFile': seed['sourceFile'], 'cpo': seed['cpo'],
                                  'locationId': seed['locationId'], 'distanceM': meters})
    return sorted(found, key=lambda x: (x['distanceM'], x['sourceFile'], x['locationId']))


def main():
    with gzip.open(SEEDS, 'rt') as handle:
        seeds = json.load(handle)
    grid = defaultdict(list)
    for seed in seeds['locations']:
        grid[(math.floor(seed['latitude'] / CELL), math.floor(seed['longitude'] / CELL))].append(seed)
    hits = {}
    conflict = set()
    covered_tiles = set()
    for path in sorted(TILES.glob('batch-*.json.gz')):
        with gzip.open(path, 'rt') as handle:
            batch = json.load(handle)
        if batch['status'] != 'tile_ids_only_no_emsp_tariffs' or batch['errors']:
            raise RuntimeError(f'incomplete tile batch: {path}')
        for row in batch['rows']:
            if row['tile'] in covered_tiles:
                raise RuntimeError(f'duplicate tile: {row["tile"]}')
            covered_tiles.add(row['tile'])
            for hit in row['hits']:
                pk = hit['pk']
                if pk in hits and hit['latitude'] is not None and hits[pk]['latitude'] is not None:
                    if distance_m(hit, hits[pk]) > 30:
                        conflict.add(pk)
                else:
                    hits[pk] = hit
    queue = []
    counts = Counter()
    for pk, hit in sorted(hits.items()):
        if pk in conflict or hit['latitude'] is None or hit['longitude'] is None:
            counts['missingOrConflictingCoarsePosition'] += 1
            continue
        candidates = nearby(hit, grid)
        if not candidates:
            counts['withoutNearbyCpoSeed'] += 1
            continue
        counts['pkWithin250mOfEligibleCpoSeed'] += 1
        if len(candidates) > 1:
            counts['pkWithMultipleNearbyCpoSeeds'] += 1
        queue.append({'electroversePk': pk, 'coarseCoordinates': {
            'latitude': hit['latitude'], 'longitude': hit['longitude']},
            'nearbyCpoSeeds': candidates,
            'status': 'coarse_discovery_only_graphql_verification_required'})
    payload = {'schemaVersion': 1, 'generatedAt': datetime.now(timezone.utc).isoformat(),
               'country': 'GB', 'status': 'coarse_candidates_not_evse_links',
               'coveredTiles': len(covered_tiles), 'sourceSeedLocations': seeds['locationCount'],
               'candidatePks': len(queue), 'candidates': queue}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(gzip.compress(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()))
    summary = {'schemaVersion': 1, 'generatedAt': payload['generatedAt'],
               'status': payload['status'], 'coveredTiles': len(covered_tiles),
               'distinctTilePks': len(hits), 'candidatePks': len(queue),
               'counts': dict(counts), 'publicationStatus': 'no_emsp_tariff_promotion'}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
