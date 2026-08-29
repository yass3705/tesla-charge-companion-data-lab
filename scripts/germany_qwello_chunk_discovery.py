#!/usr/bin/env python3
"""Inspect Qwello public Vue lazy chunks for location/pricing API calls."""
from __future__ import annotations
import json,re,urllib.error,urllib.request
from collections import Counter
from pathlib import Path

APP='https://qwello.de/js/app.af0ea5b4.js'
BASE='https://qwello.de/js/{name}.{hash}.js'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'
TOKENS=['services.qwello.eu','VUE_APP_SERVICES_URL','VUE_APP_USER_SERVICE_URL','/public/','pricing','price','tariff','tarif','location','locations','station','stations','charger','chargers','0.49','0,49','0.51','0,51','infrastructure','kwh','minute']

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/javascript,*/*'})
    try:
        with urllib.request.urlopen(req,timeout=45) as r:return r.read(),getattr(r,'status',200),r.geturl()
    except urllib.error.HTTPError as e:return e.read(),e.code,e.geturl()

def snips(text,token,r=1000,limit=12):
    out=[];low=text.lower();t=token.lower();start=0
    while len(out)<limit:
        i=low.find(t,start)
        if i<0:break
        out.append(text[max(0,i-r):min(len(text),i+len(token)+r)])
        start=i+len(token)
    return out

def main():
    raw,status,_=fetch(APP);assert status==200
    app=raw.decode('utf-8','replace')
    # Runtime contains multiple name->contenthash maps. Collect plausible names/hashes.
    pairs=[]
    for name,h in re.findall(r'([A-Za-z][A-Za-z0-9_~.-]{1,80}):["\']([0-9a-f]{8})["\']',app):
        if (name,h) not in pairs:pairs.append((name,h))
    rows=[];hit_counts=Counter()
    for name,h in pairs:
        url=BASE.format(name=name,hash=h)
        raw,status,final=fetch(url)
        if status!=200:continue
        text=raw.decode('utf-8','replace');hits={}
        for token in TOKENS:
            if token.lower() in text.lower():
                hits[token]=snips(text,token);hit_counts[token]+=1
        # Extract URL/path-like literals from relevant chunks.
        literals=[]
        if hits:
            for m in re.finditer(r'["\']([^"\']{1,300})["\']',text):
                v=m.group(1);lo=v.lower()
                if any(k in lo for k in ('/public','service','price','pric','tarif','location','station','charger','kwh','minute')):
                    literals.append(v)
            literals=list(dict.fromkeys(literals))[:800]
        rows.append({'name':name,'hash':h,'url':final,'bytes':len(raw),'tokenHits':hits,'candidateLiterals':literals})
    out={'dataset':'germany-qwello-chunk-discovery','pairCount':len(pairs),'reachableChunkCount':len(rows),'tokenChunkCounts':dict(hit_counts),'chunks':rows}
    p=Path('data/germany/qwello_chunk_discovery.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_QWELLO_CHUNK_DISCOVERY='+json.dumps({'pairCount':len(pairs),'reachableChunkCount':len(rows),'tokenChunkCounts':dict(hit_counts),'relevantChunks':[{'name':r['name'],'hash':r['hash'],'url':r['url'],'bytes':r['bytes'],'tokens':sorted(r['tokenHits']),'candidateLiterals':r['candidateLiterals'][:120],'snippets':{k:v[:4] for k,v in r['tokenHits'].items()}} for r in rows if r['tokenHits']]},ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
