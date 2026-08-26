#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone

INPUTS = [
    Path('data/reports/avia_picoty_runtime_config.json'),
    Path('data/reports/avia_picoty_hermes_api_strings.json'),
    Path('data/reports/avia_picoty_app_api_discovery.json'),
    Path('data/reports/avia_picoty_guest_route_focus.json'),
    Path('data/reports/avia_picoty_guest_route_context.json'),
]

NEEDLES = [
    'runtimeVersion', 'runtime-version', 'expo-runtime-version', 'runtime_version',
    'expo.modules.updates', 'EXPO_UPDATE_URL', 'expo-channel-name', 'u.expo.dev',
    'getRegistrationGroups', 'registerWithoutToken', 'registrationCode',
    'registrationGroup', 'registerCode', 'getTenantFiles', 'getCposAsGuest',
    'getNearbyLocationsAsGuest', 'getMapLocationsAsGuest', 'getLocationAsGuest',
    'simulateLocationPricingAsGuest', 'getLocationTariffsAsGuest',
    'tenantId', 'tenant_id', 'appDistribution', 'distributionId',
]

ROUTE_PART = re.compile(
    r"(?:https?://[^\s\"'<>]{3,220}|/[A-Za-z0-9_{}:.-]+(?:/[A-Za-z0-9_{}:.-]+){0,8})"
)
JWT = re.compile(r'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}')
BEARER = re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+\-/=]{16,}')
KV_SECRET = re.compile(
    r'(?i)(api[-_ ]?key|subscription[-_ ]?key|client[-_ ]?secret|access[-_ ]?token|refresh[-_ ]?token|authorization)'
    r'(\s*[=:]\s*[\"\']?)([^\s\"\',}]{8,})'
)


def redact(s: str) -> str:
    s = JWT.sub('[REDACTED_JWT]', s)
    s = BEARER.sub(r'\1[REDACTED]', s)
    s = KV_SECRET.sub(lambda m: m.group(1) + m.group(2) + '[REDACTED]', s)
    return s


def walk(obj, path='$'):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f'{path}.{k}', k
            yield from walk(v, f'{path}.{k}')
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f'{path}[{i}]')
    elif isinstance(obj, (str, int, float, bool)) or obj is None:
        yield path, obj


def route_like(s: str):
    out = []
    for m in ROUTE_PART.finditer(s):
        v = m.group(0)
        if any(x in v.lower() for x in ('tenant', 'register', 'location', 'tariff', 'expo', 'distribution', 'cpo')):
            if v not in out:
                out.append(v)
    return out[:80]


def contexts_for(s: str, needle: str):
    low = s.lower()
    n = needle.lower()
    start = 0
    out = []
    while True:
        i = low.find(n, start)
        if i < 0:
            break
        a = max(0, i - 4200)
        b = min(len(s), i + len(needle) + 9000)
        ctx = redact(s[a:b].replace('\x00', ' '))
        out.append(ctx)
        start = i + max(1, len(n))
        if len(out) >= 8:
            break
    return out


def main():
    report = {
        'schemaVersion': '1.0.0',
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'purpose': 'Focused extraction of public AVIA Picoty guest bootstrap and Expo update metadata. Credentials/tokens are redacted.',
        'inputs': [],
        'hits': {n: [] for n in NEEDLES},
        'scalarCandidates': [],
    }

    scalar_seen = set()
    for p in INPUTS:
        report['inputs'].append({'path': str(p), 'exists': p.exists()})
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:
            report['inputs'][-1]['error'] = f'{type(e).__name__}: {e}'
            continue

        for path, value in walk(data):
            if isinstance(value, str):
                for needle in NEEDLES:
                    if needle.lower() not in value.lower():
                        continue
                    for ctx in contexts_for(value, needle):
                        item = {
                            'source': str(p),
                            'jsonPath': path,
                            'context': ctx,
                            'routeLike': route_like(ctx),
                        }
                        if item not in report['hits'][needle]:
                            report['hits'][needle].append(item)
                            if len(report['hits'][needle]) >= 12:
                                break

                # Retain short public-looking scalar literals around bootstrap/update concepts.
                if 1 <= len(value) <= 240 and any(k in path.lower() for k in (
                    'runtime', 'expo', 'registration', 'tenant', 'distribution', 'version', 'channel', 'update'
                )):
                    rv = redact(value)
                    key = (path, rv)
                    if key not in scalar_seen:
                        scalar_seen.add(key)
                        report['scalarCandidates'].append({'source': str(p), 'jsonPath': path, 'value': rv})

    # Cap report size while keeping the most relevant material.
    for needle in list(report['hits']):
        report['hits'][needle] = report['hits'][needle][:12]
    report['scalarCandidates'] = report['scalarCandidates'][:300]

    out = Path('data/reports/avia_picoty_bootstrap_focus.json')
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({
        'hitCounts': {k: len(v) for k, v in report['hits'].items() if v},
        'scalarCandidates': len(report['scalarCandidates']),
    }, indent=2))


if __name__ == '__main__':
    main()
