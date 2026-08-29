#!/usr/bin/env python3
"""Inspect Qwello public Vue lazy chunks for location/pricing API calls.

Webpack stores chunk names and JavaScript content hashes in two separate maps
inside its ``u=function(e)`` filename resolver. Pairing arbitrary name/hash
literals can produce valid-looking but wrong files, so this probe parses that
resolver explicitly and joins both maps by numeric chunk id.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

APP = 'https://qwello.de/js/app.af0ea5b4.js'
BASE = 'https://qwello.de/js/{name}.{hash}.js'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'
TOKENS = [
    'services.qwello.eu','VUE_APP_SERVICES_URL','VUE_APP_USER_SERVICE_URL',
    '/public/','public/web','pricing','price','tariff','tarif','location','locations',
    'station','stations','charger','chargers','0.49','0,49','0.51','0,51',
    'infrastructure','kwh','minute','axios','baseURL','.get(','.post('
]


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/javascript,*/*'})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.read(), getattr(r, 'status', 200), r.geturl()
    except urllib.error.HTTPError as e:
        return e.read(), e.code, e.geturl()


def snips(text, token, r=1200, limit=16):
    out=[]; low=text.lower(); t=token.lower(); start=0
    while len(out)<limit:
        i=low.find(t,start)
        if i<0: break
        out.append(text[max(0,i-r):min(len(text),i+len(token)+r)])
        start=i+len(token)
    return out


def parse_js_chunk_resolver(app: str):
    # Current webpack 5 form:
    # a.u=function(e){return"js/"+({131:"texts-Imprint",...}[e]||e)+"."+
    #   {131:"10a8084b",...}[e]+".js"}
    resolver = re.search(
        r'\.u=function\(e\)\{return["\']js/["\']\+\((\{.*?\})\[e\]\|\|e\)\+["\']\.["\']\+(\{.*?\})\[e\]\+["\']\.js["\']\}',
        app,
        re.S,
    )
    if not resolver:
        raise RuntimeError('Qwello webpack JS chunk filename resolver not found')
    name_obj, hash_obj = resolver.group(1), resolver.group(2)
    names = {int(k): v for k,v in re.findall(r'(\d+):["\']([^"\']+)["\']', name_obj)}
    hashes = {int(k): v for k,v in re.findall(r'(\d+):["\']([0-9a-f]{8,64})["\']', hash_obj, re.I)}
    if len(hashes) < 10:
        raise RuntimeError(f'implausibly small Qwello JS hash map: {len(hashes)}')
    rows=[]
    for chunk_id,h in sorted(hashes.items()):
        rows.append({'chunkId':chunk_id,'name':names.get(chunk_id,str(chunk_id)),'hash':h})
    return rows, names, hashes


def candidate_literals(text: str):
    literals=[]
    for m in re.finditer(r'["\']([^"\']{1,350})["\']', text):
        v=m.group(1); lo=v.lower()
        if any(k in lo for k in (
            '/public','service','price','pric','tarif','location','station','charger',
            'kwh','minute','map','geo','country','city','operator','evse'
        )):
            literals.append(v)
    return list(dict.fromkeys(literals))[:1200]


def main():
    raw,status,_ = fetch(APP)
    if status != 200:
        raise RuntimeError(f'Qwello app bundle HTTP {status}')
    app = raw.decode('utf-8','replace')
    pairs,names,hashes = parse_js_chunk_resolver(app)

    rows=[]; hit_counts=Counter()
    for pair in pairs:
        url=BASE.format(name=pair['name'],hash=pair['hash'])
        raw,status,final=fetch(url)
        row={**pair,'url':final,'httpStatus':status,'bytes':len(raw)}
        if status!=200:
            row['error']=f'HTTP {status}'
            rows.append(row)
            continue
        text=raw.decode('utf-8','replace'); hits={}
        for token in TOKENS:
            if token.lower() in text.lower():
                hits[token]=snips(text,token); hit_counts[token]+=1
        row['tokenHits']=hits
        row['candidateLiterals']=candidate_literals(text) if hits else []
        rows.append(row)

    relevant=[r for r in rows if r.get('tokenHits')]
    out={
        'schemaVersion':'0.2.0',
        'dataset':'germany-qwello-chunk-discovery',
        'pairCount':len(pairs),
        'namedChunkCount':len(names),
        'hashChunkCount':len(hashes),
        'reachableChunkCount':sum(1 for r in rows if r.get('httpStatus')==200),
        'tokenChunkCounts':dict(hit_counts),
        'chunks':rows,
    }
    p=Path('data/germany/qwello_chunk_discovery.json'); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_QWELLO_CHUNK_DISCOVERY='+json.dumps({
        'pairCount':len(pairs),
        'namedChunkCount':len(names),
        'reachableChunkCount':out['reachableChunkCount'],
        'tokenChunkCounts':dict(hit_counts),
        'resolvedChunks':pairs,
        'relevantChunks':[
            {
                'chunkId':r['chunkId'],'name':r['name'],'hash':r['hash'],'url':r['url'],
                'bytes':r['bytes'],'tokens':sorted(r.get('tokenHits') or {}),
                'candidateLiterals':r.get('candidateLiterals',[])[:180],
                'snippets':{k:v[:5] for k,v in (r.get('tokenHits') or {}).items()}
            } for r in relevant
        ],
    },ensure_ascii=False,sort_keys=True))

if __name__=='__main__': main()
