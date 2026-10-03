#!/usr/bin/env python3
"""Probe Qwello's public web API endpoints discovered in its public JS bundle.

Only anonymous GET requests to URLs embedded in the public site are attempted.
Responses are stored verbatim (text/JSON) for QA discovery; no TCC publication.
"""
from __future__ import annotations
import hashlib,json,urllib.error,urllib.request
from datetime import datetime,timezone
from pathlib import Path

URLS=[
 'https://services.qwello.eu/v1/us/public/web',
 'https://services.qwello.eu/v1',
]
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'

def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def probe(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/plain,*/*','Accept-Language':'de-DE,de;q=0.9','Origin':'https://qwello.de','Referer':'https://qwello.de/de/how-to'})
    try:
        with urllib.request.urlopen(req,timeout=60) as r:
            raw=r.read();status=getattr(r,'status',200);headers=dict(r.headers.items());final=r.geturl()
    except urllib.error.HTTPError as exc:
        raw=exc.read();status=exc.code;headers=dict(exc.headers.items());final=exc.geturl()
    text=raw.decode('utf-8','replace')
    parsed=None
    try:parsed=json.loads(text)
    except Exception:pass
    return {'requestedUrl':url,'url':final,'status':status,'contentType':headers.get('Content-Type'),'allowOrigin':headers.get('Access-Control-Allow-Origin'),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'json':parsed,'text':None if parsed is not None else text[:20000]}

def main():
    rows=[probe(u) for u in URLS]
    out={'schemaVersion':'0.1.0','dataset':'germany-qwello-public-api-probe','generatedAt':now(),'scope':{'stagedOnly':True,'publishesToTcc':False,'anonymousGetOnly':True,'discoveryOnly':True},'responses':rows}
    p=Path('data/germany/qwello_public_api_probe.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_QWELLO_PUBLIC_API_PROBE='+json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
