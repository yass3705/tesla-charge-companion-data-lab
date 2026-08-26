#!/usr/bin/env python3
import json,re
from pathlib import Path
from datetime import datetime,timezone

INPUTS=[Path('data/reports/avia_picoty_runtime_config.json'),Path('data/reports/avia_picoty_full_guest_bootstrap.json'),Path('data/reports/avia_picoty_hermes_api_strings.json')]
TERMS=['API_SUBSCRIPTION_KEY','API_URL','subscription-key','subscriptionKey','Ocp-Apim','ocp-apim','baseUrl','baseURL','api-version','/v1/','v1/tenants/','accessTokenExclusionList','secure: true','secure:true']
JWT=re.compile(r'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}(?:\.[A-Za-z0-9_-]{8,})?')
GOOGLE=re.compile(r'AIza[0-9A-Za-z_-]{20,}')
SECRET_ASSIGN=re.compile(r'(?i)((?:api[-_ ]?key|subscription[-_ ]?key|authorization|access[-_ ]?token|refresh[-_ ]?token|client[-_ ]?secret)\s*[=:]\s*["\']?)([^\s,"\'};]{6,})')
UUIDS={'fd0addd9-7ef0-48cb-b4bc-19373e6203a7','fda4bdf2-46e4-4bc8-9ec8-296862f5d2c3','9439c762-3ce1-45fc-a9ea-a92ed5e06489'}

def sanitize(s):
    s=JWT.sub('<redacted-jwt>',s);s=GOOGLE.sub('<redacted-google-api-key>',s)
    s=SECRET_ASSIGN.sub(lambda m:m.group(1)+'<redacted>',s)
    return s

def walk(x,path='$'):
    if isinstance(x,dict):
        for k,v in x.items():yield from walk(v,f'{path}.{k}')
    elif isinstance(x,list):
        for i,v in enumerate(x):yield from walk(v,f'{path}[{i}]')
    elif isinstance(x,str):yield path,x

def main():
    out={'schemaVersion':'1.0.0','generatedAt':datetime.now(timezone.utc).isoformat(),'terms':{t:[] for t in TERMS}}
    for p in INPUTS:
        if not p.exists():continue
        try:d=json.loads(p.read_text(encoding='utf-8'))
        except Exception:continue
        for path,s in walk(d):
            low=s.lower()
            for term in TERMS:
                needle=term.lower();start=0
                while True:
                    i=low.find(needle,start)
                    if i<0:break
                    ctx=sanitize(s[max(0,i-3000):min(len(s),i+len(term)+6000)].replace('\x00',' '))
                    item={'source':str(p),'jsonPath':path,'context':ctx}
                    if item not in out['terms'][term]:out['terms'][term].append(item)
                    start=i+len(term)
                    if len(out['terms'][term])>=12:break
    for k in out['terms']:out['terms'][k]=out['terms'][k][:12]
    raw=json.dumps(out,ensure_ascii=False,indent=2)+'\n'
    if JWT.search(raw) or GOOGLE.search(raw):raise RuntimeError('unsafe output')
    Path('data/reports/avia_picoty_http_client_summary.json').write_text(raw,encoding='utf-8')
    print(json.dumps({k:len(v) for k,v in out['terms'].items()},indent=2))
if __name__=='__main__':main()
