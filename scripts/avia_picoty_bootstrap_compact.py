#!/usr/bin/env python3
"""Compact the large Picoty app bootstrap report into safe actionable identifiers.

This script performs no network calls. It only reads previously generated, redacted static
analysis and emits route definitions, safe UUID candidates and nearby literals useful for
reconstructing the documented guest bootstrap flow.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SRC = Path('data/reports/avia_picoty_full_guest_bootstrap.json')
OUT = Path('data/reports/avia_picoty_bootstrap_compact.json')

WANTED = (
    'getRegistrationGroups', 'registerWithoutToken', 'getTenantFiles', 'getCposAsGuest',
    'getNearbyLocationsAsGuest', 'getMapLocationsAsGuest', 'getLocationAsGuest',
    'simulateLocationPricingAsGuest', 'getLocationTariffsAsGuest',
)
CONFIG_TERMS = (
    'registrationCode', 'registrationGroup', 'registerCode', 'tenantId', 'tenant_id',
    'appDistribution', 'distributionId', 'runtimeVersion', 'expo-runtime-version',
    'EXPO_RUNTIME_VERSION', 'EXPO_UPDATE_URL', 'expo-channel-name', 'u.expo.dev',
)
UUID_RE = re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b')
PATH_RE = re.compile(r'''["'](/[^"']{1,240})["']''')
URL_RE = re.compile(r'https://[^\s"\'<>]{3,260}', re.I)
SENSITIVE = re.compile(r'(?i)(api[-_ ]?key|subscription[-_ ]?key|client[-_ ]?secret|access[-_ ]?token|refresh[-_ ]?token|authorization)')


def safe_literal(value: str) -> bool:
    if not value or len(value) > 300 or SENSITIVE.search(value):
        return False
    low = value.lower()
    return (
        value.startswith('/') or value.startswith('https://u.expo.dev/')
        or any(k.lower() in low for k in CONFIG_TERMS)
        or any(k.lower() in low for k in WANTED)
        or bool(UUID_RE.fullmatch(value))
    )


def collect_strings(obj, out: list[str]):
    if isinstance(obj, str):
        if safe_literal(obj) and obj not in out:
            out.append(obj)
        for u in UUID_RE.findall(obj):
            if u not in out:
                out.append(u)
        for m in PATH_RE.finditer(obj):
            p = m.group(1)
            if len(p) <= 240 and p not in out:
                out.append(p)
        for m in URL_RE.finditer(obj):
            u = m.group(0).rstrip('.,);}')
            if ('expo.dev' in u or 'deftpower' in u or 'azure' in u) and u not in out:
                out.append(u)
    elif isinstance(obj, dict):
        for v in obj.values():
            collect_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_strings(v, out)


def main():
    data = json.loads(SRC.read_text(encoding='utf-8'))
    operations = {}
    raw_ops = data.get('operations') or {}
    for name in WANTED:
        hits = raw_ops.get(name) or []
        literals: list[str] = []
        methods = []
        for hit in hits:
            m = hit.get('methodCandidate')
            if m and m not in methods:
                methods.append(m)
            collect_strings(hit.get('publicLiterals') or [], literals)
            # Context is large; extract only route/UUID/config tokens, never persist it whole.
            collect_strings(hit.get('context') or '', literals)
        operations[name] = {
            'hitCount': len(hits),
            'methods': methods,
            'safeLiterals': literals[:300],
        }

    config = {}
    for term in CONFIG_TERMS:
        hits = (data.get('configHits') or {}).get(term) or []
        literals: list[str] = []
        for hit in hits:
            collect_strings(hit.get('publicLiterals') or [], literals)
            collect_strings(hit.get('context') or '', literals)
        config[term] = {'hitCount': len(hits), 'safeLiterals': literals[:300]}

    resources: list[dict] = []
    for item in data.get('resourceMetadata') or []:
        literals: list[str] = []
        collect_strings(item.get('context') or '', literals)
        if literals or item.get('uuidCandidates'):
            resources.append({
                'file': item.get('file'),
                'line': item.get('line'),
                'uuidCandidates': item.get('uuidCandidates') or [],
                'safeLiterals': literals[:100],
            })

    all_strings: list[str] = []
    collect_strings(data, all_strings)
    uuids = sorted(set(data.get('uuidCandidates') or []) | set(UUID_RE.findall('\n'.join(all_strings))))

    out = {
        'schemaVersion': '1.0.0',
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'sourceGeneratedAt': data.get('generatedAt'),
        'operations': operations,
        'config': config,
        'resourceMetadata': resources[:250],
        'uuidCandidates': uuids,
        'allSafeRouteAndConfigLiterals': all_strings[:1000],
        'safety': {'networkCalls': False, 'credentialsPersisted': False, 'tokensPersisted': False},
    }
    rendered = json.dumps(out, ensure_ascii=False, indent=2) + '\n'
    # Fail closed if a JWT or common key label/value pattern slipped through.
    assert not re.search(r'\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}', rendered)
    assert not re.search(r'\bAIza[0-9A-Za-z_-]{20,}\b', rendered)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(rendered, encoding='utf-8')
    print(json.dumps({
        'uuidCandidates': uuids,
        'operationHits': {k: v['hitCount'] for k, v in operations.items()},
        'configHits': {k: v['hitCount'] for k, v in config.items() if v['hitCount']},
        'safeLiteralCount': len(all_strings),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
