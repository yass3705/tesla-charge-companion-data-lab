#!/usr/bin/env python3
"""Evyve UK CPO-only Eco-Movement PCPR collection and fail-closed V9 staging.

The operator-provided PCPR token does not authorize treating other CPOs as Evyve.
Connector tariff_ids are the only permitted source of connector prices.
"""
from __future__ import annotations
import collections
import copy
import gzip
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://open-chargepoints.com/api/ocpi/cpo/2.2.1/'
ALLOWED_COMPONENTS = {'ENERGY', 'TIME', 'PARKING_TIME', 'FLAT'}
ALLOWED_RESTRICTIONS = {'start_time', 'end_time', 'day_of_week', 'min_duration', 'max_duration',
                        'min_power', 'max_power', 'start_date', 'end_date'}
NONPUBLIC = re.compile(r'\b(staff only|employees only|fleet depot|private charging|internal test|not for public use)\b', re.I)


def write_json(path, document):
    dest = ROOT / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(document, ensure_ascii=False, separators=(',', ':'), sort_keys=True) + '\n').encode('utf-8')
    if path.endswith('.gz'):
        out = io.BytesIO()
        with gzip.GzipFile(fileobj=out, mode='wb', filename='', mtime=0, compresslevel=9) as f:
            f.write(raw)
        raw = out.getvalue()
    dest.write_bytes(raw)


def collect(endpoint, authorization):
    rows = []
    offset = 0
    calls = 0
    while True:
        if calls >= 28:
            raise RuntimeError(f'{endpoint}: request budget reached; refusing incomplete publication')
        url = BASE + endpoint + '?' + urllib.parse.urlencode({'limit': 1000, 'offset': offset})
        retries = 0
        while True:
            calls += 1
            try:
                req = urllib.request.Request(url, headers={'Authorization': authorization,
                            'Accept': 'application/json', 'User-Agent': 'TeslaChargeCompanion/9 Evyve-PCPR'})
                with urllib.request.urlopen(req, timeout=90) as response:
                    payload = json.load(response)
                break
            except urllib.error.HTTPError as err:
                if err.code in (429, 500, 502, 503, 504) and retries < 2 and calls < 28:
                    wait = min(120, 15 * 2 ** retries)
                    retry_after = (err.headers or {}).get('Retry-After')
                    if retry_after and str(retry_after).isdigit():
                        wait = max(wait, min(300, int(retry_after)))
                    retries += 1
                    time.sleep(wait)
                    continue
                raise RuntimeError(f'{endpoint}: HTTP {err.code}; retaining existing snapshot') from None
        if not isinstance(payload, dict) or payload.get('status_code', 1000) != 1000 or not isinstance(payload.get('data'), list):
            raise RuntimeError(f'{endpoint}: unexpected response; retaining existing snapshot')
        page = payload['data']
        rows.extend(page)
        if len(page) < 1000:
            break
        offset += len(page)
        time.sleep(1)
    return rows, calls


def label(v):
    return str(v.get('name') or '').strip() if isinstance(v, dict) else str(v or '').strip()


def eligible_location(loc):
    if loc.get('country_code') != 'GB' or str(loc.get('country') or '').upper() not in ('GB', 'GBR'):
        return 'outside_UK'
    if 'evyve' not in label(loc.get('operator')).casefold():
        return 'not_declared_Evyve_CPO'
    if loc.get('publish') is not True:
        return 'not_explicitly_public'
    for name in ('access_type', 'access', 'parking_type'):
        value = str(loc.get(name) or '').upper()
        if any(term in value for term in ('PRIVATE', 'STAFF', 'EMPLOYEE', 'FLEET', 'RESIDENT_ONLY')):
            return 'restricted_access'
    if NONPUBLIC.search(str(loc.get('name') or '')):
        return 'nonpublic_name'
    coords = loc.get('coordinates') or {}
    try:
        lat, lon = float(coords['latitude']), float(coords['longitude'])
    except (KeyError, TypeError, ValueError):
        return 'missing_coordinates'
    if not (49 <= lat <= 61 and -9 <= lon <= 3):
        return 'outside_UK_bounds'
    return None


def make_tariff(raw):
    if raw.get('country_code') != 'GB' or raw.get('currency') != 'GBP':
        return None, 'not_GBP_UK_tariff'
    if not isinstance(raw.get('elements'), list) or not raw['elements']:
        return None, 'missing_elements'
    result = copy.deepcopy(raw)
    for element in result['elements']:
        if not isinstance(element, dict) or not isinstance(element.get('restrictions') or {}, dict) or set(element.get('restrictions') or {}) - ALLOWED_RESTRICTIONS:
            return None, 'unsupported_restrictions'
        pcs = element.get('price_components')
        if not isinstance(pcs, list) or not pcs:
            return None, 'missing_components'
        for comp in pcs:
            if not isinstance(comp, dict) or comp.get('type') not in ALLOWED_COMPONENTS:
                return None, 'unsupported_component'
            try:
                price = Decimal(str(comp['price']))
                vat = Decimal(str(comp['vat'])) if comp.get('vat') is not None else Decimal('20')
                step = Decimal(str(comp.get('step_size', 1)))
                if not price.is_finite() or not vat.is_finite() or not step.is_finite() or price < 0 or vat < 0 or vat > 100 or step < 0 or (step == 0 and comp['type'] != 'FLAT'):
                    raise ValueError('invalid values')
            except (InvalidOperation, KeyError, ValueError, TypeError):
                return None, 'invalid_component_value'
            comp['sourcePriceExVat'] = float(price)
            comp['tccVatRateAppliedPct'] = float(vat)
            comp['tccVatOrigin'] = 'explicit_OCPI' if comp.get('vat') is not None else 'HMRC_UK_public_20_default'
            comp['price'] = float((price * (Decimal('1') + vat / 100)).quantize(Decimal('0.000001')))
            comp['vat'] = None  # VAT already included for V9: prevent a second application.
    result['tccPriceBasis'] = 'GBP_including_public_UK_VAT'
    result['tccSourcePriceBasis'] = 'OCPI_2.2.1_excluding_VAT'
    return result, None


def stage(locations, tariffs, stamp):
    tariff_keys = collections.defaultdict(list)
    for item in tariffs:
        if isinstance(item, dict):
            tariff_keys[(item.get('country_code'), item.get('party_id'), str(item.get('id') or ''))].append(item)
    excluded = collections.Counter()
    tariff_rejections = collections.Counter()
    op_names = collections.Counter(label(loc.get('operator')) for loc in locations if isinstance(loc, dict))
    used = {}
    valid_locations = []
    seen_locations = set()
    seen_connectors = set()
    connectors_count = 0
    priced = 0
    missing = set()
    for raw in locations:
        if not isinstance(raw, dict):
            excluded['malformed_location'] += 1
            continue
        reason = eligible_location(raw)
        if reason:
            excluded[reason] += 1
            continue
        key = (raw.get('country_code'), raw.get('party_id'), str(raw.get('id') or ''))
        if not key[1] or not key[2] or key in seen_locations:
            excluded['invalid_or_duplicate_location_id'] += 1
            continue
        seen_locations.add(key)
        loc = copy.deepcopy(raw)
        kept_evses = []
        for evse in loc.get('evses') or []:
            if not isinstance(evse, dict) or str(evse.get('status') or '').upper() == 'REMOVED':
                excluded['removed_or_malformed_evse'] += 1
                continue
            eid = str(evse.get('evse_id') or evse.get('uid') or '').strip()
            if not eid:
                excluded['missing_evse_id'] += 1
                continue
            e = copy.deepcopy(evse)
            kept_connectors = []
            for c in e.get('connectors') or []:
                if not isinstance(c, dict) or not str(c.get('id') or ''):
                    excluded['missing_connector_id'] += 1
                    continue
                identity = (key, eid, str(c['id']))
                if identity in seen_connectors:
                    excluded['duplicate_connector'] += 1
                    continue
                seen_connectors.add(identity)
                conn = copy.deepcopy(c)
                rawrefs = conn.get('tariff_ids', [])
                if not isinstance(rawrefs, list):
                    rawrefs = []
                refs = [str(i) for i in rawrefs if i is not None]
                conn['sourceTariffIds'] = refs
                verified = []
                if len(refs) != len(set(refs)):
                    tariff_rejections['duplicate_tariff_reference'] += 1
                else:
                    for ref in refs:
                        tkey = (key[0], key[1], ref)
                        matches = tariff_keys.get(tkey, [])
                        if len(matches) != 1:
                            tariff_rejections['missing_or_ambiguous_tariff'] += 1
                            missing.add(ref)
                            continue
                        tariff, why = make_tariff(matches[0])
                        if why:
                            tariff_rejections[why] += 1
                        else:
                            used[tkey] = tariff
                            verified.append(ref)
                # No partial/invented prices for a connector with any ambiguous ref.
                conn['tariff_ids'] = verified if len(verified) == len(refs) else []
                priced += bool(conn['tariff_ids'])
                connectors_count += 1
                kept_connectors.append(conn)
            if kept_connectors:
                e['connectors'] = kept_connectors
                kept_evses.append(e)
        if kept_evses:
            loc['evses'] = kept_evses
            valid_locations.append(loc)
        else:
            excluded['no_valid_evse'] += 1
    # A different CPO's token must never silently overwrite Evyve's previous dataset.
    if not valid_locations:
        raise RuntimeError(f'No public Evyve UK locations confirmed; observed operator names: {dict(op_names)}')
    used_keys = {(loc['country_code'], loc['party_id'], tid)
                 for loc in valid_locations for e in loc['evses'] for c in e['connectors'] for tid in c.get('tariff_ids', [])}
    doc = {'country': 'GB', 'collectedAt': stamp, 'source': 'Evyve UK operator-supplied Eco-Movement PCPR',
           'integrationStatus': 'cpo_direct_exact_connector_vat_inclusive_staged',
           'sources': [{'id': 'evyve-uk-pcpr-direct', 'name': 'Evyve Charging', 'country': 'GB',
                        'pricingScope': 'cpo_direct_pcpr', 'locations': valid_locations,
                        'tariffs': [used[k] for k in sorted(used_keys)]}]}
    report = {'provider': 'Evyve Charging', 'country': 'GB', 'collectedAt': stamp,
              'sourceLocations': len(locations), 'sourceTariffs': len(tariffs),
              'publicEvyveLocations': len(valid_locations), 'publicConnectors': connectors_count,
              'pricedExactConnectors': priced, 'unpricedPublicConnectors': connectors_count - priced,
              'operatorNamesInTokenFeed': dict(op_names), 'excluded': dict(excluded),
              'blockedTariffReasons': dict(tariff_rejections), 'missingOrAmbiguousTariffRefs': sorted(missing)[:100],
              'tariffPolicy': 'Evyve CPO PCPR only; direct tariff_ids at exact connector; GBP VAT-inclusive; missing or ambiguous unpriced',
              'accessPolicy': 'explicit public UK Evyve locations only; restricted/staff/private removed',
              'credentialPersisted': False, 'publishedToV9': False,
              'readyForV9Review': bool(priced), 'status': 'staged_for_audit_not_live'}
    return doc, report


# Eco-Movement shared-secret attempt: validation below *rejects* a Blink-only feed.
def main():
    token = os.environ.get('EVYVE_PCPR_TOKEN', '').strip()
    if not token:
        raise SystemExit('Missing Actions secret EVYVE_PCPR_TOKEN; never enter token in code or logs')
    authorization = token if token.lower().startswith(('token ', 'bearer ')) else 'Token ' + token
    locations, location_calls = collect('locations', authorization)
    tariffs, tariff_calls = collect('tariffs', authorization)
    if not locations:
        raise RuntimeError('Evyve returned an empty location feed; previous snapshot retained')
    stamp = datetime.now(timezone.utc).isoformat()
    staged, audit = stage(locations, tariffs, stamp)
    audit['apiRequests'] = {'locations': location_calls, 'tariffs': tariff_calls}
    write_json('data/national/uk_evyve_pcpr.json.gz', {'source': 'Evyve PCPR', 'collectedAt': stamp,
                                                         'locations': locations, 'tariffs': tariffs})
    write_json('data/national/uk_evyve_pcpr_v9.json.gz', staged)
    write_json('reports/uk/evyve-pcpr-latest.json', audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
