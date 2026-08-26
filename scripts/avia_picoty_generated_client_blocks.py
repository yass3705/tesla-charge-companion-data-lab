#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime, timezone

SOURCE = Path('data/reports/avia_picoty_runtime_config.json')
OUT = Path('data/reports/avia_picoty_generated_client_blocks.json')
TARGETS = [
    'getRegistrationGroups',
    'registerWithoutToken',
    'getTenantFiles',
    'getCposAsGuest',
    'getNearbyLocationsAsGuest',
    'getMapLocationsAsGuest',
    'getLocationAsGuest',
    'simulateLocationPricingAsGuest',
    'getLocationTariffsAsGuest',
]
ROUTE_HINTS = ['/register', '/registration', '/groups', '/tenants/', '/locations/', '/cpos', '/map-locations', '/nearby', '/tariffs', '/simulate']

JWT = re.compile(r'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}')
BEARER = re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+\-/=]{16,}')
KV_SECRET = re.compile(r'(?i)(api[-_ ]?key|subscription[-_ ]?key|client[-_ ]?secret|access[-_ ]?token|refresh[-_ ]?token|authorization)(\s*[=:]\s*[\"\']?)([^\s\"\',}]{8,})')
QUOTED = re.compile(r"['\"]([^'\"]{1,220})['\"]")


def redact(s):
    s = JWT.sub('[REDACTED_JWT]', s)
    s = BEARER.sub(r'\1[REDACTED]', s)
    s = KV_SECRET.sub(lambda m: m.group(1)+m.group(2)+'[REDACTED]', s)
    return s


def walk_strings(obj, path='$'):
    if isinstance(obj, dict):
        for k,v in obj.items():
            yield from walk_strings(v, f'{path}.{k}')
    elif isinstance(obj, list):
        for i,v in enumerate(obj):
            yield from walk_strings(v, f'{path}[{i}]')
    elif isinstance(obj, str):
        yield path, obj


def literals(ctx):
    vals=[]
    for m in QUOTED.finditer(ctx):
        v=m.group(1)
        low=v.lower()
        if (v.startswith('/') or any(x in low for x in ('registration','register','tenant','location','tariff','cpo','distribution'))) and v not in vals:
            vals.append(v)
    return vals[:100]


def useful(ctx):
    low=ctx.lower()
    return ('http' in low and ('request' in low or "'method'" in low or '[\"method\"]' in low)) or "['path']" in ctx or "'path':" in ctx


def main():
    data=json.loads(SOURCE.read_text(encoding='utf-8'))
    strings=list(walk_strings(data))
    out={
        'schemaVersion':'1.0.0',
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'source':str(SOURCE),
        'targets':{},
        'genericRouteBlocks':[],
    }

    for target in TARGETS:
        hits=[]
        for path,s in strings:
            low=s.lower(); n=target.lower(); start=0
            while True:
                i=low.find(n,start)
                if i<0: break
                a=max(0,i-6000); b=min(len(s),i+len(target)+10000)
                ctx=redact(s[a:b].replace('\x00',' '))
                if useful(ctx):
                    item={'jsonPath':path,'context':ctx,'literals':literals(ctx)}
                    if item not in hits: hits.append(item)
                start=i+len(n)
        # Prefer blocks that contain likely route literals and keep enough alternatives.
        hits.sort(key=lambda x: (not any(v.startswith('/') for v in x['literals']), -len(x['literals'])))
        out['targets'][target]=hits[:30]

    generic=[]
    for path,s in strings:
        low=s.lower()
        if not any(h.lower() in low for h in ROUTE_HINTS):
            continue
        # Collect each route-hint occurrence independently.
        for hint in ROUTE_HINTS:
            pos=0
            while True:
                i=low.find(hint.lower(),pos)
                if i<0: break
                a=max(0,i-4500); b=min(len(s),i+7000)
                ctx=redact(s[a:b].replace('\x00',' '))
                if useful(ctx):
                    item={'hint':hint,'jsonPath':path,'context':ctx,'literals':literals(ctx)}
                    if item not in generic: generic.append(item)
                pos=i+len(hint)
    out['genericRouteBlocks']=generic[:120]

    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({
        'targets':{k:len(v) for k,v in out['targets'].items()},
        'genericRouteBlocks':len(out['genericRouteBlocks'])
    },indent=2))

if __name__=='__main__':
    main()
