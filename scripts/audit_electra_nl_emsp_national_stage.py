#!/usr/bin/env python3
"""Audit checkpoint coverage and repeated EVSE identities across NL staging shards."""
import gzip
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('data/platforms/electra/netherlands/emsp-source-staging')
OUT = Path('reports/emsp-national/electra-nl-stage-audit.json')


def main():
    shards = []
    seen_pages = set()
    identities = Counter()
    first_occurrence = {}
    duplicate_examples = []
    duplicate_tariff_conflicts = 0
    duplicate_cpo_labels = 0
    totals = set()
    national_shas = set()
    aggregate = Counter()
    for path in sorted(ROOT.glob('pages-*.json.gz')):
        with gzip.open(path, 'rt') as handle:
            value = json.load(handle)
        if value.get('status') != 'source_staging_only_no_tariff_promotion':
            raise RuntimeError(f'invalid staging status: {path}')
        begin, size = value['startPage'], value['pages']
        pages = set(range(begin, begin + size))
        if seen_pages & pages:
            raise RuntimeError(f'overlapping page shards: {path}')
        seen_pages.update(pages)
        totals.add(value['sourceTotalCount'])
        national_shas.add(value['nationalSha256'])
        aggregate.update(value['counts'])
        for location in value['locations']:
            for evse in location['matchedAllowedEvses']:
                evse_id = evse['nationalEvseId']
                identities[evse_id] += 1
                occurrence = {'locationId': location['locationId'], 'cpo': location['cpo'],
                              'tariffIds': sorted(t.get('chargeTariffId') for t in location['chargeTariffs'])}
                previous = first_occurrence.setdefault(evse_id, occurrence)
                if previous is not occurrence:
                    duplicate_tariff_conflicts += occurrence['tariffIds'] != previous['tariffIds']
                    duplicate_cpo_labels += occurrence['cpo'] != previous['cpo']
                    if len(duplicate_examples) < 30:
                        duplicate_examples.append({'evseId': evse_id, 'first': previous, 'other': occurrence})
        shards.append({'path': str(path), 'startPage': begin, 'pages': size,
                       'sourceTotalCount': value['sourceTotalCount'], 'counts': value['counts']})
    if not shards or len(national_shas) != 1:
        raise RuntimeError('missing shards or mixed DOT-NL source SHA')
    expected = math.ceil(max(totals) / 100)
    missing = sorted(set(range(expected)) - seen_pages)
    repeated = sum(n - 1 for n in identities.values() if n > 1)
    status = ('complete_stable_source' if not missing and len(totals) == 1 else
              'complete_with_source_total_drift' if not missing else 'partial')
    report = {'schemaVersion': 1, 'generatedAt': datetime.now(timezone.utc).isoformat(),
              'status': status, 'sourceTotalCounts': sorted(totals), 'expectedPages': expected,
              'seenPages': len(seen_pages), 'missingPageCount': len(missing),
              'missingPagesFirst20': missing[:20], 'nationalSha256': national_shas.pop(),
              'aggregateCounts': dict(aggregate), 'distinctMatchedAllowedEvseIds': len(identities),
              'repeatedMatchedAllowedEvseOccurrences': repeated,
              'repeatedWithDifferentTariffIds': duplicate_tariff_conflicts,
              'repeatedWithDifferentCpoLabel': duplicate_cpo_labels,
              'duplicateExamplesFirst30': duplicate_examples,
              'shards': shards, 'publicationStatus': 'no_emsp_tariff_promotion'}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'shards'}))


if __name__ == '__main__':
    main()
