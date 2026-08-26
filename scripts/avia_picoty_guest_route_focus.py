#!/usr/bin/env python3
import json,re
from pathlib import Path
from datetime import datetime, timezone

INPUTS=[Path('data/reports/avia_picoty_runtime_config.json'),Path('data/reports/avia_picoty_hermes_api_strings.json'),Path('data/reports/avia_picoty_app_api_discovery.json')]
METHODS=['getTenantIdByRegisterCode','getAzureMapsRegistrationCode','getAppDistributionByTenantId','getChargingStationsAsGuest','getChargeTariffAsGuest','getMapLocationsAsGuest']
JWT=re.compile(r'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}')
BEARER=re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+\-/=]{16,}')
KV=re.compile(r'(?i)(api[-_ ]?key|subscription[-_ ]?key|client[-_ ]?secret|access[-_ ]?token|refresh[-_ ]?token|authorization)(\s*[=:]\s*["\']?)([^\s"\',}]{8,})')
ROUTE=re.compile(r'''(?x)(?:https?://[^\s"'<>]{3,180}|["']([^"']*(?:v1/|tenant|register|registration|distribution|location|tariff|map)[^"']{0,180})["'])''',re.I)

def redact(s):
    s=JWT.sub('[REDACTED_JWT]',s); s=BEARER.sub(r'\1[REDACTED]',s); s=KV.sub(lambda m:m.group(1)+m.group(2)+'[REDACTED]',s)
    return s

def walk(x,path='$'):
    if isinstance(x,dict):
        for k,v in x.items(): yield from walk(v,f'{path}.{k}')
    elif isinstance(x,list):
        for i,v in enumerate(x): yield from walk(v,f'{path}[{i}]')
    elif isinstance(x,str): yield path,x

def main():
    out={'schemaVersion':'1.0.0','generatedAt':datetime.now(timezone.utc).isoformat(),'methods':{m:[] for m in METHODS}}
    for p in INPUTS:
        if not p.exists(): continue
        data=json.loads(p.read_text(encoding='utf-8'))
        for path,s in walk(data):
            low=s.lower()
            for method in METHODS:
                needle=method.lower(); start=0
                while True:
                    i=low.find(needle,start)
                    if i<0: break
                    a=max(0,i-2500); b=min(len(s),i+len(method)+5000)
                    context=redact(s[a:b].replace('\x00',' '))
                    routes=[]
                    for rm in ROUTE.finditer(context):
                        val=rm.group(0)
                        if rm.lastindex and rm.group(1) is not None: val=rm.group(1)
                        val=val.strip('"\'')
                        if val not in routes: routes.append(val)
                    out['methods'][method].append({'source':str(p),'jsonPath':path,'context':context,'routeLike':routes[:60]})
                    start=i+len(method)
                    if len(out['methods'][method])>=12: break
    # dedupe by context
    for m,items in out['methods'].items():
        seen=set(); clean=[]
        for x in items:
            key=x['context']
            if key not in seen: seen.add(key); clean.append(x)
        out['methods'][m]=clean[:12]
    Path('data/reports/avia_picoty_guest_route_focus.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({m:len(v) for m,v in out['methods'].items()},indent=2))

if __name__=='__main__': main()
