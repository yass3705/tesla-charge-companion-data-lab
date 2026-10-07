#!/usr/bin/env python3
"""Reconcile connector exclusions with guest detail evidence from the same baseline.

Build a V9 offer candidate; activation requires the runtime to enforce tariff UTC
independently of the session display timezone and load the station inventory.
"""
import copy
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    with (gzip.open(ROOT / path, 'rt') if path.endswith('.gz') else open(ROOT / path)) as f:
        return json.load(f)


def write(path, value):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, separators=(',', ':')) + '\n').encode()
    target.write_bytes(gzip.compress(data, mtime=0) if path.endswith('.gz') else data)


def main():
    source = read('data/national/uk_connected_kerb_locations.json.gz')
    app = read('data/national/uk_connected_kerb_app_direct_offers.json.gz')
    report = read('reports/uk/connected-kerb-app-collection-latest.json')
    assert report['operatorBaselineCollectedAt'] == source['collectedAt'], 'Stale app evidence'
    key = lambda o: (o['locationId'], o['evseUid'], o['connectorId'])
    offers = {key(o): o for o in app['offers']}
    unresolved = {key(o): o['reason'] for o in report['unresolved']}
    assert len(offers) == len(app['offers']), 'Duplicate offer scope'
    assert all(o['operatorBaselineCollectedAt'] == source['collectedAt'] for o in offers.values())
    unique = {}
    for loc in source['locations']:
        if loc['id'] not in unique or loc.get('last_updated', '') > unique[loc['id']].get('last_updated', ''):
            unique[loc['id']] = loc
    eligible, excluded, empty, partial, seen = [], [], [], [], set()
    for loc in unique.values():
        if loc.get('publish') is not True:
            continue
        kept = copy.deepcopy(loc)
        kept['evses'] = []
        lost = 0
        for evse in loc['evses']:
            connectors = []
            for conn in evse['connectors']:
                scope = (loc['id'], evse['uid'], conn['id'])
                if scope in offers:
                    seen.add(scope)
                    connectors.append({**conn, 'validatedDirectPricing': offers[scope]['pricing'],
                                       'pricingSource': 'operator_app_guest_detail'})
                else:
                    lost += 1
                    excluded.append({'stationId': loc['id'], 'stationName': loc.get('name'),
                                     'evseUid': evse['uid'], 'evseId': evse.get('evse_id'),
                                     'connectorId': conn['id'], 'reasons': [unresolved.get(scope, 'guest_detail_not_validated')],
                                     'reasonReport': 'reports/uk/connected-kerb-app-collection-latest.json'})
            if connectors:
                kept['evses'].append({**evse, 'connectors': connectors})
        if kept['evses']:
            eligible.append(kept)
            if lost:
                partial.append(loc['id'])
        else:
            empty.append(loc['id'])
    assert seen == offers.keys(), 'Orphan offers'
    assert len(seen) == report['resolvedConnectors']
    assert len(excluded) == report['unresolvedConnectors'] if isinstance(report['unresolvedConnectors'], int) else len(excluded) == len(report['unresolvedConnectors'])
    policy = {'provider': 'Connected Kerb', 'snapshotCollectedAt': source['collectedAt'],
              'appCollectedAt': app['collectedAt'], 'level': 'connector',
              'rule': 'Keep only connectors validated by app detail; omit a station only if none remain. Preserve raw source.',
              'retainedConnectorCount': len(seen), 'excludedConnectorCount': len(excluded),
              'excludedStationCount': len(empty), 'priceUnambiguousStationCount': len(eligible),
              'partiallyRetainedStationCount': len(partial), 'excludedStationIds': empty,
              'partiallyRetainedStationIds': partial, 'excludedConnectors': excluded,
              'eligibleDataset': 'data/national/uk_connected_kerb_price_unambiguous_locations.json.gz'}
    write('reports/uk/connected-kerb-price-exclusions-latest.json', policy)
    write(policy['eligibleDataset'], {'source': 'Connected Kerb API + guest app detail',
                                    'collectedAt': source['collectedAt'], 'appCollectedAt': app['collectedAt'],
                                    'priceAmbiguousConnectorsExcluded': True, 'locations': eligible})
    candidates = []
    days = {'SUNDAY': 0, 'MONDAY': 1, 'TUESDAY': 2, 'WEDNESDAY': 3, 'THURSDAY': 4, 'FRIDAY': 5, 'SATURDAY': 6}
    for offer in offers.values():
        rules = []
        for item in offer['pricing']['energySlices']:
            rule = {'scope': 'timeWindow' if item.get('startTime') or item.get('endTime') else 'allDay',
                    'start': (item.get('startTime') or '00:00')[:5],
                    'end': (item.get('endTime') or '24:00')[:5], 'pricePerKwh': item['price']}
            selected_days = [days[d] for d in item.get('dayOfWeek', [])]
            if selected_days and len(set(selected_days)) != 7:
                rule['daysOfWeek'] = selected_days
            if item.get('stepSize', 1) > 1:
                rule['energyStepWh'] = item['stepSize']
            assert item.get('minDuration', 0) == 0
            rules.append(rule)
        candidates.append({'id': 'connected-kerb:' + offer['connectorId'], 'provider': 'Connected Kerb',
                           'operatorIds': ['Connected Kerb'], 'stationIds': [offer['locationId']],
                           'evseIds': [offer['evseId'] or offer['evseUid']], 'countries': ['GB'],
                           'currency': 'GBP', 'directOperatorOnly': True, 'verifiedScope': 'exact_evse',
                           'pricing': {'type': 'rules', 'rules': rules},
                           'metadata': {'timeZone': 'UTC', 'displayTimeZone': 'Europe/London',
                                        'connectorId': offer['connectorId'], 'pricingScope': app['pricingScope']}})
    write('v9-production-runtime/data/v9/uk-connected-kerb-offers.candidate.json',
          {'country': 'GB', 'generatedAt': app['collectedAt'], 'activationStatus': 'pending_runtime_timezone_and_station_loader',
           'directOffers': candidates})
    doc = read('docs/connected-kerb-uk-integration-2026-10-07.json')
    doc.update(status='guest_app_reconciled_v9_candidate_ready', snapshotCollectedAt=source['collectedAt'],
               appCollectedAt=app['collectedAt'], publishedToV9=False,
               counts={'publicBaselineStations': len(eligible) + len(empty), 'validatedConnectors': len(seen),
                       'unresolvedConnectors': len(excluded), 'retainedStations': len(eligible),
                       'fullyExcludedStations': len(empty), 'partiallyRetainedStations': len(partial)},
               priceExclusionPolicy=policy | {'excludedConnectors': len(excluded)},
               next='Activate a GB station loader and enforce offer UTC timezone before runtime publication.',
               v9Candidate='v9-production-runtime/data/v9/uk-connected-kerb-offers.candidate.json')
    doc.pop('tariffLimitations', None)
    doc.pop('duplicateResolution', None)
    write('docs/connected-kerb-uk-integration-2026-10-07.json', doc)
    print(json.dumps(doc['counts']))


if __name__ == '__main__':
    main()
