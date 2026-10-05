#!/usr/bin/env python3
"""Discover Qwello public API calls embedded in the current Germany web bundle."""
from __future__ import annotations
import hashlib,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path

URL='https://qwello.de/js/app.af0ea5b4.js'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'
TOKENS=['services.qwello.eu','/v1','us/public/web','axios','baseURL','location','locations','station','stations','charger','price','pricing','tariff','tarif','public/web']

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def snippets(text,token,radius=900,limit=30):
    out=[];low=text.lower();t=token.lower();start=0
    while len(out)<limit:
        i=low.find(t,start)
        if i<0:break
        out.append(text[max(0,i-radius):min(len(text),i+len(token)+radius)])
        start=i+len(token)
    return out

def main():
    req=urllib.request.Request(URL,headers={'User-Agent':UA,'Accept':'application/javascript,*/*','Accept-Language':'de-DE,de;q=0.9'})
    with urllib.request.urlopen(req,timeout=90) as r:
        raw=r.read();meta={'url':r.geturl(),'status':getattr(r,'status',200),'contentType':r.headers.get('Content-Type'),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    text=raw.decode('utf-8','replace')
    hits={token:snippets(text,token) for token in TOKENS if token.lower() in text.lower()}
    string_literals=[]
    for m in re.finditer(r'["\']([^"\']{1,240})["\']',text):
        val=m.group(1)
        low=val.lower()
        if any(k in low for k in ('/v1','public/web','location','station','price','tarif','services.qwello','charger')):
            string_literals.append(val)
    string_literals=list(dict.fromkeys(string_literals))
    # Extract call-like contexts around common request verbs.
    request_contexts=[]
    for pat in (r'\.get\(',r'\.post\(',r'\.put\(',r'\.delete\(',r'axios',r'baseURL'):
        for m in re.finditer(pat,text,re.I):
            request_contexts.append(text[max(0,m.start()-600):min(len(text),m.start()+1200)])
    # Deduplicate contexts while retaining order.
    request_contexts=list(dict.fromkeys(request_contexts))[:120]
    out={'schemaVersion':'0.1.0','dataset':'germany-qwello-api-discovery','generatedAt':now(),'scope':{'stagedOnly':True,'publishesToTcc':False,'discoveryOnly':True},'source':meta,'tokenSnippets':hits,'candidateStringLiterals':string_literals[:1000],'requestContexts':request_contexts}
    p=Path('data/germany/qwello_api_discovery.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_QWELLO_API_DISCOVERY='+json.dumps({'source':meta,'tokens':sorted(hits),'candidateStrings':string_literals[:250],'requestContexts':request_contexts[:30]},ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
