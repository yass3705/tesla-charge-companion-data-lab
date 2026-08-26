#!/usr/bin/env python3
"""Read-only live probe of Picoty/Deftpower guest location/tariff routes.

Uses only the public tenant id exposed by Picoty's production Expo manifest and public guest
operations explicitly exempt from access-token requirements in the app. No credentials, cookies,
OAuth tokens or API subscription keys are sent.
"""
from __future__ import annotations
import json,urllib.parse,urllib.request,urllib.error,re
from pathlib import Path
from datetime import datetime,timezone

TENANT='9439c762-3ce1-45fc-a9ea-a92ed5e06489'
HOSTS=['https://pdefweushaapiam01.azure-api.net','https://api.deftpower.com']
SAMPLES=[('la-souterraine',46.24066,1.48931),('tourgeville',49.35303,0.06257),('nantes',47.25837,-1.57995)]
JWT=re.compile(r'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}(?:\.[A-Za-z0-9_-]{8,})?')
SECRET=re.compile(r'(?i)(authorization|subscription[-_]?key|api[-_]?key|access[-_]?token|refresh[-_]?token|client[-_]?secret)(\s*[=:]\s*["\']?)([^\s"\',}]{8,})')

def sanitize(s):
    s=JWT.sub('<redacted-jwt>',s);s=SECRET.sub(lambda m:m.group(1)+m.group(2)+'<redacted>',s);return s

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'TeslaChargeCompanion-data-lab/1.0','Accept':'application/json,text/plain,*/*'},method='GET')
    try:
        with urllib.request.urlopen(req,timeout=25) as r:return {'url':url,'status':r.status,'contentType':r.headers.get('content-type'),'body':sanitize(r.read(500000).decode('utf-8','replace'))}
    except urllib.error.HTTPError as e:return {'url':url,'status':e.code,'contentType':e.headers.get('content-type') if e.headers else None,'body':sanitize(e.read(100000).decode('utf-8','replace'))}
    except Exception as e:return {'url':url,'status':None,'error':type(e).__name__,'body':sanitize(str(e))}

def main():
    results=[]
    for host in HOSTS:
        for prefix in ('','/v1'):
            base=f'{host}{prefix}/tenants/{TENANT}'
            results.append({'kind':'cpos','host':host,'prefix':prefix,'response':get(base+'/cpos')})
            for name,lat,lon in SAMPLES:
                queries=[
                    {'latitude':lat,'longitude':lon},
                    {'latitude':lat,'longitude':lon,'radius':5},
                    {'latitude':lat,'longitude':lon,'radiusInKm':5},
                    {'latitude':lat,'longitude':lon,'distance':5},
                ]
                for q in queries:
                    url=base+'/nearby-locations?'+urllib.parse.urlencode(q)
                    results.append({'kind':'nearby','sample':name,'query':q,'host':host,'prefix':prefix,'response':get(url)})
    out={'schemaVersion':'1.0.0','generatedAt':datetime.now(timezone.utc).isoformat(),'tenantId':TENANT,'credentialsSent':False,'writeMethodsUsed':False,'results':results}
    raw=json.dumps(out,ensure_ascii=False,indent=2)+'\n'
    if JWT.search(raw):raise RuntimeError('JWT survived sanitization')
    Path('data/reports/avia_picoty_guest_live_probe.json').write_text(raw,encoding='utf-8')
    print(json.dumps([{'kind':x['kind'],'sample':x.get('sample'),'host':x['host'],'prefix':x['prefix'],'query':x.get('query'),'status':x['response']['status'],'body':x['response'].get('body','')[:400]} for x in results],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
