#!/usr/bin/env python3
"""Extract and probe only documented/public guest bootstrap surfaces for Picoty Recharge & Vous.

No user credentials or persistent auth tokens are used. The goal is to resolve tenant/location
identifiers necessary to read public guest tariff endpoints. Responses are stored with sensitive
headers omitted.
"""
import json,re,urllib.parse,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone

REPORTS=[
 Path('data/reports/avia_picoty_runtime_config.json'),
 Path('data/reports/avia_picoty_hermes_api_strings.json'),
 Path('data/reports/avia_picoty_app_api_discovery.json'),
 Path('data/reports/avia_picoty_guest_route_focus.json'),
]
HOSTS=['https://pdefweushaapiam01.azure-api.net','https://api.deftpower.com']
TOKENS=['getRegistrationGroups','registerWithoutToken','getTenantIdAsGuest','getTenantIdByRegisterCode','getAzureMapsRegistrationCode','getAppDistributionByTenantId','registration-groups','register','tenant','app-distribution']
URL_RE=re.compile(r'https?://[^\s"\'<>]+')
ROUTE_RE=re.compile(r'[/A-Za-z0-9_.:-]*(?:registration|register|tenant|distribution)[/A-Za-z0-9_.:{}?=&-]*',re.I)
UUID_RE=re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b',re.I)


def walk(x,path='$'):
    if isinstance(x,dict):
        for k,v in x.items(): yield from walk(v,f'{path}.{k}')
    elif isinstance(x,list):
        for i,v in enumerate(x): yield from walk(v,f'{path}[{i}]')
    elif isinstance(x,str): yield path,x


def extract_candidates():
    out={'urls':[], 'routes':[], 'uuids':[], 'snippets':[]}
    for p in REPORTS:
        if not p.exists(): continue
        try:data=json.loads(p.read_text(encoding='utf-8'))
        except Exception:continue
        for path,s in walk(data):
            low=s.lower()
            if not any(t.lower() in low for t in TOKENS): continue
            sn=s[:12000]
            out['snippets'].append({'source':str(p),'path':path,'text':sn})
            for u in URL_RE.findall(s):
                if any(h in u for h in ['deftpower','azure-api.net','picoty']):
                    if u not in out['urls']: out['urls'].append(u)
            for m in ROUTE_RE.findall(s):
                if len(m)>=5 and m not in out['routes']: out['routes'].append(m)
            for u in UUID_RE.findall(s):
                if u not in out['uuids']: out['uuids'].append(u)
    out['snippets']=out['snippets'][:120]
    return out


def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json,text/plain,*/*'})
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            body=r.read(100000).decode('utf-8','replace')
            return {'url':url,'status':r.status,'contentType':r.headers.get('content-type'),'body':body}
    except urllib.error.HTTPError as e:
        return {'url':url,'status':e.code,'contentType':e.headers.get('content-type') if e.headers else None,'body':e.read(20000).decode('utf-8','replace')}
    except Exception as e:
        return {'url':url,'status':None,'error':type(e).__name__,'body':str(e)}


def main():
    cand=extract_candidates()
    probes=[]
    static_paths=['/v1/tenants','/tenants','/registration-groups','/v1/registration-groups','/app-distribution','/v1/app-distribution']
    for base in HOSTS:
        for path in static_paths: probes.append(get(base+path))
    out={'schemaVersion':'1.0.0','generatedAt':datetime.now(timezone.utc).isoformat(),'candidates':cand,'anonymousReadOnlyProbes':probes}
    Path('data/reports/avia_picoty_bootstrap_probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'urls':len(cand['urls']),'routes':len(cand['routes']),'uuids':len(cand['uuids']),'probes':[(x['url'],x['status']) for x in probes]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
