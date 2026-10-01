#!/usr/bin/env python3
"""Publish a validated independent SuC snapshot. No Tesla queries or cross-repo token."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from core import convert_station, fetch_source, mac_key, now, parse_date, read, validate_source, write


def refresh(output, country_codes, source_path=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Download into a staging file. A failed check leaves every published file intact.
    staged = output / '.incoming.json'
    try:
        source = read(source_path) if source_path else fetch_source(staged)
        validate_source(source)
        observed = parse_date(source['generatedAt'])
        if observed > parse_date(now()):
            raise ValueError('SuC generation is in the future')
        old_raw = read(output / 'europe.json') if (output / 'europe.json').exists() else None
        if old_raw:
            if observed < parse_date(old_raw['generatedAt']):
                raise ValueError('SuC generation regressed; keep the previous snapshot')
            before, after = Counter(s['country'] for s in old_raw['stations']), Counter(s['country'] for s in source['stations'])
            for c, count in before.items():
                if after[c] < count * .9:
                    raise ValueError('SuC station count fell by more than 10% in ' + c)
        previous = read(output / 'tesla_stations.json') if (output / 'tesla_stations.json').exists() else []
        refs = {}
        for station in previous:
            key = mac_key(station)
            if key in refs:
                raise ValueError('Duplicate previous station key')
            refs[key] = station
        selected = [s for s in source['stations'] if s['country'] in country_codes]
        if not selected or set(country_codes) - {s['country'] for s in selected}:
            raise ValueError('Missing requested countries in SuC snapshot')
        exported = [convert_station(s, refs.get((s['country'], s['id'].casefold())), source['generatedAt']) for s in selected]
        ids = [s['id'] for s in exported]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate output ID')
        # Avoid persisting stale access-reference dates as new tariff observations.
        digest = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        metadata = {'schemaVersion': 1, 'checkedAt': now(), 'sourceGeneratedAt': source['generatedAt'],
                    'source': 'https://suc-tracker.eu/data/europe.json', 'sourceSha256': digest,
                    'catalogueSha256': hashlib.sha256(json.dumps(exported, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest(),
                    'sourceStationCount': len(source['stations']), 'exportStationCount': len(exported),
                    'countries': sorted(country_codes), 'byCountry': dict(sorted(Counter(s['countryCode'] for s in exported).items())),
                    'priceObservationDates': dict(sorted(Counter((s.get('sourceObservedAt') or '')[:10] for s in exported).items())),
                    'withoutComparableTariff': sum(not s['pricing']['rules'] for s in exported),
                    'accessHoursUnknown': sum(s['sucTracker']['accessSource'] == 'unknown' for s in exported),
                    'previousIdsAbsentFromSource': sorted(set(refs) - {(s['country'], s['id'].casefold()) for s in source['stations']}),
                    'publication': 'Independent SuC catalogue only; no TCC production replacement',
                    'accessPolicy': 'Previously verified Mac access metadata retained, no new access inferred',
                    'freshness': 'checkedAt is a download check; sourceGeneratedAt and sourceObservedAt are the source dates'}
        # Files become visible atomically together only when the Git commit is pushed.
        write(output / 'europe.json', source)
        write(output / 'tesla_stations.json', exported)
        write(output / 'metadata.json', metadata)
        return metadata
    finally:
        if staged.exists():
            staged.unlink()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', default='data/suc-tracker')
    p.add_argument('--config', default='config/countries.json')
    p.add_argument('--source-json', help='Offline fixture/check only; normally download SuC')
    args = p.parse_args()
    cfg = read(args.config)
    countries = {v['countryCode'] for v in cfg.values() if v.get('enabled')}
    result = refresh(args.out, countries, args.source_json)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
