#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone

INPUTS = [
    Path('data/reports/avia_picoty_runtime_config.json'),
    Path('data/reports/avia_picoty_hermes_api_strings.json'),
    Path('data/reports/avia_picoty_app_api_discovery.json'),
    Path('data/reports/avia_picoty_guest_probe.json'),
]
TARGETS = [
    'getChargeTariffAsGuest',
    'getMapLocationsAsGuest',
    'getAppDistributionAsGuest',
    'tenantId', 'tenant_id', 'tenant-id',
    'appDistribution', 'app-distribution', 'distributionId', 'distribution_id',
    'registrationGroup', 'registration-group',
    'v1/tenants/', '/v1/tenants/',
    'api.deftpower.com', 'account.deftpower.com',
    'fr.picoty.app', 'picoty',
]

JWT = re.compile(r'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}')
BEARER = re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+\-/=]{16,}')
KV_SECRET = re.compile(r'(?i)(api[-_ ]?key|subscription[-_ ]?key|client[-_ ]?secret|access[-_ ]?token|refresh[-_ ]?token|authorization)(\s*[=:]\s*["\']?)([^\s"\',}]{8,})')
LONG_TOKEN = re.compile(r'(?<![A-Za-z0-9])[A-Za-z0-9_-]{48,}(?![A-Za-z0-9])')


def redact(s: str) -> str:
    s = JWT.sub('[REDACTED_JWT]', s)
    s = BEARER.sub(r'\1[REDACTED]', s)
    s = KV_SECRET.sub(lambda m: m.group(1)+m.group(2)+'[REDACTED]', s)
    s = LONG_TOKEN.sub('[REDACTED_LONG_TOKEN]', s)
    return s


def walk(obj, path='$'):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f'{path}.{k}')
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f'{path}[{i}]')
    elif isinstance(obj, str):
        yield path, obj


def snippets_for(value: str):
    low = value.lower()
    found = []
    for target in TARGETS:
        start = 0
        needle = target.lower()
        while True:
            i = low.find(needle, start)
            if i < 0:
                break
            a = max(0, i - 260)
            b = min(len(value), i + len(target) + 420)
            snippet = redact(value[a:b].replace('\x00', ' '))
            found.append({'target': target, 'snippet': snippet})
            start = i + max(1, len(target))
            if len(found) >= 80:
                return found
    # de-duplicate snippets while preserving order
    seen=set(); out=[]
    for x in found:
        key=(x['target'],x['snippet'])
        if key not in seen:
            seen.add(key); out.append(x)
    return out


def main():
    out = {
        'schemaVersion': '1.0.0',
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'purpose': 'Public guest-route reconstruction for AVIA VOLT Picoty / Deftpower; secrets and long tokens redacted.',
        'files': [],
    }
    for p in INPUTS:
        item={'path':str(p),'exists':p.exists(),'matches':[]}
        if p.exists():
            try:
                data=json.loads(p.read_text(encoding='utf-8'))
                for path,value in walk(data):
                    hits=snippets_for(value)
                    if hits:
                        item['matches'].append({'jsonPath':path,'hits':hits})
            except Exception as e:
                item['error']=f'{type(e).__name__}: {e}'
        out['files'].append(item)
    Path('data/reports/avia_picoty_guest_route_context.json').write_text(
        json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    total=sum(len(f.get('matches',[])) for f in out['files'])
    print(json.dumps({'files':len(out['files']),'matchContainers':total},indent=2))

if __name__=='__main__':
    main()
