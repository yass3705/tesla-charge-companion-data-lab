#!/usr/bin/env python3
"""Probe the public/read-only Deftpower app-backend routes used by AVIA Recharge & Vous.

No OAuth token, API subscription key, cookie, account identifier or customer data is sent.
Only GET and OPTIONS are used. Nonexistent IDs are intentional so this only establishes
route reachability and public bootstrap behavior.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path('data/reports/avia_picoty_app_backend_guest_probe.json')
HOSTS = [
    'https://adefweuappbckfa01.azurewebsites.net',
    'https://pdefweushaapiam01.azure-api.net',
    'https://api.deftpower.com',
]
PREFIXES = ['/app-backend/v1', '/api/app-backend/v1', '/v1/app-backend']
ROUTES = [
    ('GET', '/registration-groups', None),
    ('GET', '/tenants/nonexistent/app-distribution', None),
    ('GET', '/tenants/nonexistent/cpos', None),
    ('GET', '/tenants/nonexistent/files', None),
    ('GET', '/tenants/nonexistent/map-locations', {'latLongBottomLeft':'41,-6','latLongTopRight':'52,10'}),
    ('GET', '/tenants/nonexistent/nearby-locations', {'latitude':'48.8','longitude':'2.3'}),
    ('GET', '/tenants/nonexistent/locations/nonexistent', None),
    ('GET', '/tenants/nonexistent/locations/nonexistent/tariffs', None),
    ('OPTIONS', '/registration-groups', None),
    ('OPTIONS', '/tenants/nonexistent/map-locations', None),
]


def call(method, url, params=None):
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=method, headers={
        'User-Agent':'TeslaChargeCompanion-data-lab/1.0',
        'Accept':'application/json,text/plain,*/*',
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(10000).decode('utf-8','replace')
            return {'method':method,'url':url,'status':int(r.status),'contentType':r.headers.get('content-type'),'allow':r.headers.get('allow'),'wwwAuthenticate':r.headers.get('www-authenticate'),'body':body[:5000]}
    except urllib.error.HTTPError as e:
        body = e.read(10000).decode('utf-8','replace')
        return {'method':method,'url':url,'status':int(e.code),'contentType':e.headers.get('content-type') if e.headers else None,'allow':e.headers.get('allow') if e.headers else None,'wwwAuthenticate':e.headers.get('www-authenticate') if e.headers else None,'body':body[:5000]}
    except Exception as e:
        return {'method':method,'url':url,'status':None,'error':type(e).__name__,'message':str(e)[:1000]}


def main():
    results=[]
    for host in HOSTS:
        for prefix in PREFIXES:
            for method,route,params in ROUTES:
                results.append(call(method, host+prefix+route, params))
    counts={}
    for r in results:
        counts[str(r.get('status'))]=counts.get(str(r.get('status')),0)+1
    interesting=[r for r in results if r.get('status') not in (404,None)]
    payload={
        'schemaVersion':'1.0.0',
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'credentialsSent':False,
        'writeMethodsUsed':False,
        'hosts':HOSTS,
        'prefixes':PREFIXES,
        'statusCounts':counts,
        'interesting':interesting,
        'results':results,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'statusCounts':counts,'interesting':[{'url':r['url'],'status':r.get('status'),'body':r.get('body','')[:300]} for r in interesting]},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
