#!/usr/bin/env python3
"""Check UK tile inventory batches before any Electroverse location lookup."""
import gzip
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('reports/emsp-national/electroverse-uk-tiles')
OUT = Path('reports/emsp-national/electroverse-uk-tile-audit.json')


def main():
    tiles = set()
    pks = Counter()
    batches = []
    possible_truncation = []
    totals = set()
    sizes = set()
    for path in sorted(ROOT.glob('batch-*.json.gz')):
        with gzip.open(path, 'rt') as handle:
            report = json.load(handle)
        if report['status'] != 'tile_ids_only_no_emsp_tariffs' or report['errors']:
            raise RuntimeError(f'incomplete UK tile batch: {path}')
        if report['selectedTiles'] != report['completedTiles']:
            raise RuntimeError(f'partial UK tile batch: {path}')
        totals.add(report['totalTiles'])
        sizes.add(report['batchSize'])
        for row in report['rows']:
            if row['tile'] in tiles:
                raise RuntimeError(f'duplicate tile {row["tile"]}')
            tiles.add(row['tile'])
            pks.update(hit['pk'] for hit in row['hits'])
        possible_truncation.extend(report['possibleTruncatedTiles'])
        batches.append({'path': str(path), 'batchIndex': report['batchIndex'],
                        'completedTiles': report['completedTiles'],
                        'distinctLocationPks': report['distinctLocationPks']})
    if not batches or len(totals) != 1 or len(sizes) != 1:
        raise RuntimeError('missing batches or inconsistent tile universe')
    total, size = totals.pop(), sizes.pop()
    expected = math.ceil(total / size)
    indices = {x['batchIndex'] for x in batches}
    missing = sorted(set(range(expected)) - indices)
    missing_positions = sum(1 for path in sorted(ROOT.glob('batch-*.json.gz'))
                            for row in json.load(gzip.open(path))['rows']
                            for hit in row['hits'] if hit['latitude'] is None or hit['longitude'] is None)
    status = ('complete_listing' if not missing and len(tiles) == total
              and not possible_truncation and not missing_positions else 'partial_or_truncated')
    report = {'schemaVersion': 1, 'generatedAt': datetime.now(timezone.utc).isoformat(),
              'status': status, 'expectedBatches': expected,
              'presentBatches': len(indices), 'presentParts': len(batches),
              'missingBatchIndices': missing, 'totalTiles': total, 'coveredTiles': len(tiles),
              'distinctLocationPks': len(pks),
              'hitsWithoutCoarsePosition': missing_positions,
              'repeatedPkOccurrencesAcrossTiles': sum(n - 1 for n in pks.values() if n > 1),
              'possibleTruncatedTiles': sorted(set(possible_truncation)),
              'batches': batches, 'publicationStatus': 'no_emsp_tariff_promotion'}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'batches'}))


if __name__ == '__main__':
    main()
