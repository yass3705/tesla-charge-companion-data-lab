#!/usr/bin/env python3
"""Independent SuC Tracker -> TCC catalogue and read-only Mac comparison.

Python 3.9+, standard library only. No publication, credentials or Tesla requests.
"""
import argparse
import copy
import hashlib
import html
import json
import math
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

SOURCE_URL = 'https://suc-tracker.eu/data/europe.json'


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def fetch_source(path):
    req = Request(SOURCE_URL, headers={'User-Agent': 'TCC-SuC-comparison/1.0', 'Accept': 'application/json'})
    with urlopen(req, timeout=60) as response:
        data = response.read(20_000_001)
    if len(data) > 20_000_000:
        raise ValueError('SuC payload exceeds 20 MB')
    payload = json.loads(data)
    validate_source(payload)
    write(path, payload)
    return payload


def validate_source(data):
    if not isinstance(data, dict) or data.get('schemaVersion') != 2:
        raise ValueError('Unsupported SuC schema; expected schemaVersion=2')
    rows = data.get('stations')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Empty/missing SuC stations')
    ids = [str(s.get('id', '')).casefold() for s in rows]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError('Missing/duplicate SuC station IDs')
    if data.get('stats', {}).get('stations') != len(rows):
        raise ValueError('SuC count does not match stats.stations')
    parse_date(data.get('generatedAt'))


def validate_mac(data):
    if not isinstance(data, list) or not data:
        raise ValueError('Use the TCC export/tesla_stations.json ARRAY, not stations-updated.json or a checkpoint')
    ids = [s.get('id') for s in data]
    if not all(isinstance(x, str) and x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError('Missing/duplicate Mac IDs')
    for s in data:
        if not isinstance(s.get('pricing'), dict) or not s.get('countryCode'):
            raise ValueError('Invalid TCC station: ' + s['id'])


def parse_date(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Missing observation date')
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return d.replace(tzinfo=d.tzinfo or timezone.utc)


def numeric(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid non-negative number: ' + repr(value))
    return value


def hhmm(value):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 1440:
        raise ValueError('Invalid minute of day')
    return '%02d:%02d' % divmod(value, 60)


def minute(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{2}:\d{2}', value):
        raise ValueError('Invalid time')
    h, m = map(int, value.split(':'))
    if h > 24 or m > 59 or (h == 24 and m):
        raise ValueError('Invalid time')
    return 60 * h + m


def convert_pricing(pricing):
    """Reject weekly subsets: current TCC production ignores day selectors."""
    if not isinstance(pricing, dict) or pricing.get('pricingStatus') != 'available':
        raise ValueError('Tariff unavailable')
    unit, currency = pricing.get('pricingUnit'), pricing.get('currency')
    if not isinstance(currency, str) or not re.fullmatch('[A-Z]{3}', currency):
        raise ValueError('Missing/invalid currency')
    if unit not in ('kwh', 'minute'):
        raise ValueError('Unsupported billing unit')
    bands = pricing.get('prices' if unit == 'kwh' else 'minutePrices', [])
    if not bands:
        raise ValueError('No tariff bands')
    rules, covered = [], [False] * 1440
    for band in bands:
        if band.get('days') != 127:
            raise ValueError('Weekly tariff cannot be represented by current TCC')
        start, end = band.get('start'), band.get('end')
        start_s, end_s = hhmm(start), hhmm(end)
        if start >= end:
            raise ValueError('Invalid/overnight SuC band; explicit split required')
        if any(covered[start:end]):
            raise ValueError('Overlapping tariff bands')
        covered[start:end] = [True] * (end - start)
        rule = {'scope': 'allDay' if start == 0 and end == 1440 else 'timeWindow',
                'start': start_s, 'end': end_s, 'currency': currency,
                'billing': 'kwh' if unit == 'kwh' else 'powerMinute'}
        if unit == 'kwh':
            rule['pricePerKwh'] = numeric(band.get('price')) / 1_000_000
        else:
            tiers = band.get('tiers') or []
            if not tiers:
                raise ValueError('Missing power tiers')
            converted, expected = [], 0
            for i, tier in enumerate(tiers):
                lo = numeric(tier.get('minPowerKw'))
                raw_hi = tier.get('maxPowerKw')
                hi = 1000 if raw_hi is None else numeric(raw_hi)
                if lo != expected or hi <= lo or (raw_hi is None and i != len(tiers) - 1):
                    raise ValueError('Gapped/overlapping power tiers')
                converted.append({'minKw': lo, 'maxKw': hi,
                                  'ratePerMinute': numeric(tier.get('price')) / 1_000_000})
                expected = hi
            if tiers[-1].get('maxPowerKw') is not None:
                raise ValueError('Power tiers do not have an open final band')
            rule['powerBands'] = converted
        rules.append(rule)
    if not all(covered):
        raise ValueError('Tariff does not cover all 24 hours')
    return {'type': 'rules', 'rules': sorted(rules, key=lambda r: r['start'])}


def slug(url):
    path = urlparse(url or '').path
    marker = '/supercharger/'
    return unquote(path.split(marker, 1)[1]).strip('/').casefold() if marker in path else ''


def mac_key(station):
    return (station.get('countryCode'), str(station.get('sucTracker', {}).get('sourceStationId') or slug(station.get('teslaUrl'))).casefold())


def distance_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, [a['latitude'], a['longitude'], b['lat'], b['lon']])
    d = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(d)))


def rule_value(rule):
    currency, billing = rule.get('currency'), rule.get('billing')
    if not currency:
        raise ValueError('Missing currency')
    if billing == 'kwh':
        return (currency, billing, round(numeric(rule.get('pricePerKwh')), 6))
    if billing == 'powerMinute':
        tiers = rule.get('powerBands') or []
        if not tiers:
            raise ValueError('Missing power tiers')
        return (currency, billing, tuple((numeric(t['minKw']), numeric(t['maxKw']), round(numeric(t['ratePerMinute']), 6)) for t in tiers))
    if billing == 'minute':
        return (currency, billing, round(numeric(rule.get('chargePerMinute')), 6))
    raise ValueError('Unsupported billing')


def schedule(pricing):
    """Canonical effective charge price at each local minute; ignores fees."""
    if pricing.get('type') != 'rules' or not pricing.get('rules'):
        raise ValueError('Tariff unavailable/unsupported')
    slots, fallback = [None] * 1440, None
    for rule in pricing['rules']:
        if rule.get('days') not in (None, 127):
            raise ValueError('Weekly tariff unsupported')
        value = rule_value(rule)
        if rule.get('scope') == 'allDay':
            if fallback is not None and fallback != value:
                raise ValueError('Conflicting all-day prices')
            fallback = value
        elif rule.get('scope') == 'timeWindow':
            a, b = minute(rule['start']), minute(rule['end'])
            indexes = range(1440) if a == b else (range(a, b) if a < b else list(range(a, 1440)) + list(range(b)))
            for i in indexes:
                if slots[i] is not None and slots[i] != value:
                    raise ValueError('Conflicting time windows')
                slots[i] = value
        else:
            raise ValueError('Unsupported day/scope')
    slots = [x if x is not None else fallback for x in slots]
    if any(x is None for x in slots):
        raise ValueError('Incomplete tariff day')
    merged = []
    for m, value in enumerate(slots):
        if merged and merged[-1]['value'] == value:
            merged[-1]['end'] = m + 1
        else:
            merged.append({'start': m, 'end': m + 1, 'value': value})
    return merged


def station_schedule(station):
    main = schedule(station['pricing'])
    for cfg in station.get('chargingConfigurations') or []:
        if schedule(cfg.get('pricing') or station['pricing']) != main:
            raise ValueError('Different prices per configuration: SuC only describes site-level pricing')
    return main


def convert_station(source, baseline, generation):
    issues = []
    try:
        pricing = convert_pricing(source.get('pricing', {}).get('tesla'))
    except ValueError as exc:
        pricing = {'type': 'rules', 'rules': []}
        issues.append(str(exc))
    for name, limit in [('lat', 90), ('lon', 180)]:
        val = source.get(name)
        if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val) or abs(val) > limit:
            raise ValueError('Invalid coordinates for ' + source['id'])
    power, stalls = numeric(source.get('maxPowerKw') or 0), numeric(source.get('stallCount') or 0)
    if power <= 0 or stalls <= 0:
        pricing = {'type': 'rules', 'rules': []}
        issues.append('Missing power/stalls; station retained but excluded from simulation')
    checked = source.get('lastSuccessfulAt')
    try:
        parse_date(checked)
    except ValueError:
        pricing = {'type': 'rules', 'rules': []}
        issues.append('Missing lastSuccessfulAt')
    addr = source.get('address') or {}
    address = ', '.join(str(addr[k]) for k in ('street', 'postalCode', 'city', 'country') if addr.get(k))
    sid = baseline['id'] if baseline else 'tesla-suc-' + re.sub('[^a-zA-Z0-9_-]', '-', source['id'])
    access = copy.deepcopy(baseline.get('access')) if baseline else None
    prior_provenance = (baseline or {}).get('sucTracker') or {}
    access_source = prior_provenance.get('accessSource') or ('Mac/TCC baseline' if access else 'unknown')
    if not access or access_source == 'unknown':
        access = {'limited': True, 'days': {}, 'afterCloseMode': 'must_stop',
                  'afterCloseNote': 'Horaires non fournis par SuC Tracker : à vérifier.'}
        issues.append('Access hours unknown; excluded from simulation until verified')
    provenance = {'provider': 'SuC Tracker', 'url': SOURCE_URL, 'sourceStationId': source['id'],
                  'datasetGeneratedAt': generation, 'lastSuccessfulAt': checked,
                  'lastCheckedAt': source.get('lastCheckedAt'), 'priceChangedAt': source.get('pricing', {}).get('tesla', {}).get('priceChangedAt'),
                  'lifecycle': source.get('lifecycle'), 'staleSince': source.get('staleSince'),
                  'accessSource': access_source,
                  'accessReferenceAt': prior_provenance.get('accessReferenceAt') or ((baseline or {}).get('lastUpdated') if access_source != 'unknown' else None),
                  'feesCoverage': 'SuC does not supply connection, parking, idle or congestion fees',
                  'powerScope': 'site maximum; not a per-stall power inventory',
                  'unknownUpperPowerBoundMappedToKw': 1000, 'issues': issues}
    unavailable = bool(baseline and baseline.get('temporarilyUnavailable'))
    if source.get('lifecycle') != 'active' or source.get('staleSince'):
        pricing = {'type': 'rules', 'rules': []}
        issues.append('Inactive/stale source station; tariff excluded from simulation')
    row = {'id': sid, 'name': 'Tesla ' + source['name'], 'kind': 'DC', 'operator': 'Tesla',
           'source': 'teslaSupercharger', 'countryCode': source['country'],
           'department': baseline.get('department', '') if baseline else '',
           'latitude': source['lat'], 'longitude': source['lon'], 'timezone': source.get('timezone'),
           'powerKw': power, 'stalls': stalls, 'address': address,
           'mapsUrl': 'https://maps.google.com/maps?daddr=%s,%s' % (source['lat'], source['lon']),
           'pricing': pricing, 'access': access, 'temporarilyUnavailable': unavailable,
           'lastUpdated': checked[:10] if checked else '', 'sourceObservedAt': checked,
           'sucTracker': provenance,
           'notes': 'Source comparative SuC Tracker. Frais annexes non fournis. Disponibilité en direct inconnue.',
           'chargingConfigurations': [{'id': 'suc-site', 'label': 'DC %s kW (maximum du site)' % power,
                                       'kind': 'DC', 'powerKw': power, 'stalls': stalls, 'pricing': copy.deepcopy(pricing)}]}
    if baseline and baseline.get('teslaUrl'):
        row['teslaUrl'] = baseline['teslaUrl']
    non_tesla = source.get('pricing', {}).get('nonTesla')
    try:
        row['nonTeslaPricing'] = convert_pricing(non_tesla)
    except ValueError:
        row['nonTeslaPricing'] = {'type': 'rules', 'rules': []}
    return row


def compare(mac, source, label, countries=None, normalized=None):
    validate_mac(mac)
    validate_source(source)
    countries = set(countries or (s['countryCode'] for s in mac))
    baseline = [s for s in mac if s['countryCode'] in countries]
    src = [s for s in source['stations'] if s['country'] in countries]
    normalized_by_key = None
    if normalized is not None:
        validate_mac(normalized)
        normalized_by_key = {mac_key(s): s for s in normalized}
        if len(normalized_by_key) != len(normalized):
            raise ValueError('Duplicate normalized SuC keys')
    by_key = defaultdict(list)
    for m in baseline:
        key = mac_key(m)
        if key[1]:
            by_key[key].append(m)
    matched_ids, exported, rows = set(), [], []
    for s in src:
        candidates = by_key.get((s['country'], str(s['id']).casefold()), [])
        old = candidates[0] if len(candidates) == 1 else None
        if old and old['id'] in matched_ids:
            raise ValueError('Ambiguous matching: ' + old['id'])
        if old:
            matched_ids.add(old['id'])
        if normalized_by_key is None:
            new = convert_station(s, old, source['generatedAt'])
        else:
            key = (s['country'], str(s['id']).casefold())
            if key not in normalized_by_key:
                raise ValueError('GitHub catalogue missing source station: ' + s['id'])
            new = copy.deepcopy(normalized_by_key[key])
        exported.append(new)
        row = {'country': s['country'], 'name': s['name'], 'teslaId': s['id'],
               'macId': old['id'] if old else None, 'sucId': new['id'],
               'matchMethod': 'exact Tesla URL identifier + country' if old else None,
               'macObservedAt': old.get('sourceObservedAt') or old.get('lastUpdated') if old else None,
               'sucObservedAt': s.get('lastSuccessfulAt'), 'status': 'only_suc',
               'macPricing': old.get('pricing') if old else None, 'sucPricing': new['pricing'],
               'technicalDifferences': [], 'issues': list(new['sucTracker']['issues']),
               'feesComparison': 'not_comparable_source_missing',
               'nonTeslaComparison': 'not_compared_TCC_baseline_has_Tesla_pricing'}
        if old:
            try:
                row['macEffectiveSchedule'] = station_schedule(old)
                row['sucEffectiveSchedule'] = station_schedule(new)
                row['status'] = 'same_tariff' if row['macEffectiveSchedule'] == row['sucEffectiveSchedule'] else 'different_tariff'
            except (ValueError, KeyError, TypeError) as exc:
                row['status'] = 'not_comparable'
                row['issues'].append(str(exc))
            for field in ['powerKw', 'stalls']:
                if old.get(field) != new.get(field):
                    row['technicalDifferences'].append({'field': field, 'mac': old.get(field), 'suc': new.get(field)})
            try:
                delta_m = distance_m(old, s)
                if delta_m > 100:
                    row['technicalDifferences'].append({'field': 'coordinates', 'distanceMeters': round(delta_m)})
            except (KeyError, TypeError, ValueError):
                row['issues'].append('Mac coordinates missing/invalid')
            try:
                row['observationGapHours'] = round((parse_date(row['sucObservedAt']) - parse_date(row['macObservedAt'])).total_seconds() / 3600, 2)
                row['macDatePrecision'] = 'day' if len(row['macObservedAt']) == 10 else 'timestamp'
            except ValueError:
                row['observationGapHours'] = None
        else:
            suggestions = []
            for m in baseline:
                if m['countryCode'] != s['country']:
                    continue
                try:
                    dist = distance_m(m, s)
                    if dist <= 500:
                        suggestions.append({'macId': m['id'], 'name': m['name'], 'distanceMeters': round(dist)})
                except (KeyError, ValueError, TypeError):
                    pass
            row['candidateMatchesForReview'] = sorted(suggestions, key=lambda x: x['distanceMeters'])
        rows.append(row)
    for old in baseline:
        if old['id'] not in matched_ids:
            rows.append({'country': old['countryCode'], 'name': old['name'], 'macId': old['id'],
                         'teslaId': slug(old.get('teslaUrl')), 'status': 'only_mac',
                         'macObservedAt': old.get('sourceObservedAt') or old.get('lastUpdated'), 'sucObservedAt': None,
                         'macPricing': old.get('pricing'), 'sucPricing': None, 'technicalDifferences': [],
                         'issues': ['Absence/mismatched identifier is not evidence of station closure']})
    ids = [x['id'] for x in exported]
    if len(ids) != len(set(ids)):
        raise ValueError('Export ID collision')
    summary = dict(Counter(r['status'] for r in rows))
    summary.update({'macStations': len(baseline), 'sucStations': len(src), 'matched': len(matched_ids),
                    'withTechnicalDifferences': sum(bool(r['technicalDifferences']) for r in rows),
                    'accessHoursUnknown': sum(x['sucTracker']['accessSource'] == 'unknown' for x in exported),
                    'exportWithoutTariff': sum(not x['pricing']['rules'] for x in exported)})
    report = {'schemaVersion': 1, 'generatedAt': now(), 'macSource': label,
              'sucSource': SOURCE_URL, 'sucGeneratedAt': source['generatedAt'],
              'countries': sorted(countries), 'summary': summary,
              'comparisonScope': 'Tesla charge tariffs across all local minutes; power tiers in native currency. Fees and live status not compared.',
              'dateCaveat': 'Different observation dates can explain differences; a difference is not proof of an error. Day-only Mac dates are not precise timestamps.',
              'publication': 'Separate comparison file; no merge, removal or production replacement.',
              'perCountry': {c: dict(Counter(r['status'] for r in rows if r['country'] == c)) for c in sorted(countries)},
              'stations': sorted(rows, key=lambda x: (x['country'], x['name']))}
    return exported, report


LABELS = {'same_tariff': 'Tarif identique', 'different_tariff': 'Tarif différent', 'only_suc': 'SuC uniquement / ID à vérifier',
          'only_mac': 'Mac uniquement / ID à vérifier', 'not_comparable': 'Non comparable'}


def render_html(report):
    esc = lambda s: html.escape(str(s if s is not None else '—'))
    def price(p):
        if not p or not p.get('rules'):
            return 'Tarif indisponible'
        parts = []
        for r in p['rules']:
            slot = 'Toute la journée' if r.get('scope') == 'allDay' else '%s–%s' % (r.get('start'), r.get('end'))
            if r.get('billing') == 'kwh':
                val = '%s %s/kWh' % (r.get('pricePerKwh'), r.get('currency'))
            elif r.get('billing') == 'powerMinute':
                val = '; '.join('%s–%s kW : %s %s/min' % (b.get('minKw'), b.get('maxKw'), b.get('ratePerMinute'), r.get('currency')) for b in r.get('powerBands', []))
            else:
                val = '%s %s/min' % (r.get('chargePerMinute'), r.get('currency'))
            parts.append(esc(slot + ' : ' + val))
        return '<br>'.join(parts)
    rows = []
    for r in report['stations']:
        details = list(r.get('issues', []))
        for d in r['technicalDifferences']:
            details.append(json.dumps(d, ensure_ascii=False))
        if r.get('candidateMatchesForReview'):
            details.append('Correspondances possibles : ' + json.dumps(r['candidateMatchesForReview'], ensure_ascii=False))
        rows.append('<tr data-status="%s"><td>%s</td><td><b>%s</b><br><small>%s</small></td><td>%s</td><td>%s<br><small>Relevé : %s</small></td><td>%s<br><small>Relevé : %s</small></td><td>%s</td></tr>' %
                    (esc(r['status']), esc(r['country']), esc(r['name']), esc(r.get('teslaId')), esc(LABELS[r['status']]), price(r.get('macPricing')), esc(r.get('macObservedAt')), price(r.get('sucPricing')), esc(r.get('sucObservedAt')), '<br>'.join(map(esc, details))))
    cards = ''.join('<div class="card"><b>%s</b><span>%s</span></div>' % (report['summary'].get(k, 0), esc(v)) for k, v in LABELS.items())
    options = ''.join('<option value="%s">%s</option>' % (k, esc(v)) for k, v in LABELS.items())
    return '''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Tesla — Mac / SuC Tracker</title>
<style>body{font:15px system-ui,sans-serif;margin:24px;background:#f4f7fb;color:#142439}h1{font-size:28px}.cards{display:flex;flex-wrap:wrap;gap:12px}.card{background:white;padding:18px;border-radius:12px;min-width:150px}.card b{display:block;font-size:28px}.card span,small{color:#58687a}input,select{font:inherit;padding:12px;border:1px solid #bcc9d8;border-radius:8px;margin:16px 8px 16px 0}table{border-collapse:collapse;background:white;width:100%}th,td{text-align:left;border-bottom:1px solid #dde5ef;padding:12px;vertical-align:top}th{background:#152c48;color:white;position:sticky;top:0}td:nth-child(4),td:nth-child(5){min-width:220px}small{font-size:12px}.scroll{overflow:auto}.note{max-width:1100px;line-height:1.55}a{color:#215ba9}</style>
<h1>Tesla : collecte Mac / SuC Tracker</h1><p class="note">Référence Mac : MACLABEL<br>SuC Tracker : fichier généré le SUCDATE. Rapport créé le REPORTDATE.<br>Comparaison du prix de charge dans la devise locale, sur toute la journée. Les dates de relevé peuvent expliquer les écarts. Les frais de parking, congestion et connexion ne sont pas fournis par SuC Tracker ; ils ne sont pas comparés. Les stations sans horaires connus sont conservées dans le JSON mais exclues de la simulation jusqu’à vérification. Aucun catalogue en production n’a été remplacé.</p>
<div class="cards">CARDS</div><input id="q" type="search" placeholder="Station, pays, identifiant…"><select id="status"><option value="">Tous les résultats</option>OPTIONS</select><span id="count"></span>
<div class="scroll"><table><thead><tr><th>Pays</th><th>Station</th><th>Résultat</th><th>Mac / base publiée</th><th>SuC Tracker</th><th>À vérifier</th></tr></thead><tbody>ROWS</tbody></table></div>
<script>const q=document.getElementById('q'),s=document.getElementById('status'),rows=[...document.querySelectorAll('tbody tr')];function filter(){let n=0;for(const r of rows){r.hidden=!!((s.value&&r.dataset.status!==s.value)||!r.textContent.toLocaleLowerCase().includes(q.value.toLocaleLowerCase()));if(!r.hidden)n++}document.getElementById('count').textContent=n+' stations affichées'}q.addEventListener('input',filter);s.addEventListener('change',filter);filter();</script></html>'''.replace('MACLABEL', esc(report['macSource'])).replace('SUCDATE', esc(report['sucGeneratedAt'])).replace('REPORTDATE', esc(report['generatedAt'])).replace('CARDS', cards).replace('OPTIONS', options).replace('ROWS', ''.join(rows))


def run(mac_path, suc_path, out_dir, label, countries=None):
    mac_path, suc_path, out_dir = Path(mac_path).resolve(), Path(suc_path).resolve(), Path(out_dir).resolve()
    targets = [out_dir / 'tesla_stations_suc_tracker.json', out_dir / 'comparaison_mac_suc.json', out_dir / 'comparaison_mac_suc.html']
    if mac_path in targets or suc_path in targets:
        raise ValueError('Input and output paths must differ')
    mac, source = read(mac_path), read(suc_path)
    exported, report = compare(mac, source, label, countries)
    report['inputSha256'] = {'mac': hashlib.sha256(mac_path.read_bytes()).hexdigest(), 'suc': hashlib.sha256(suc_path.read_bytes()).hexdigest()}
    write(targets[0], exported)
    write(targets[1], report)
    targets[2].write_text(render_html(report), encoding='utf-8')
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mac-json', required=True, help='Mac/TCC export array; read-only')
    p.add_argument('--suc-json', help='Existing SuC raw JSON; otherwise download once')
    p.add_argument('--out', default='comparison-output')
    p.add_argument('--mac-label', default='Export Mac fourni (dates de relevé par station)')
    p.add_argument('--countries', help='Comma-separated country codes; default: countries present in Mac file')
    args = p.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    suc = Path(args.suc_json).resolve() if args.suc_json else out / 'suc-tracker-source.json'
    if suc == Path(args.mac_json).resolve():
        p.error('Mac and SuC inputs must differ')
    if not args.suc_json:
        fetch_source(suc)
    report = run(args.mac_json, suc, out, args.mac_label, args.countries.upper().split(',') if args.countries else None)
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))
    print('Rapport : ' + str(out / 'comparaison_mac_suc.html'))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('Échec : ' + str(exc), file=sys.stderr)
        sys.exit(1)
