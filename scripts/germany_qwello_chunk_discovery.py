#!/usr/bin/env python3
"""Inspect Qwello public Vue lazy chunks for location/pricing API calls.

The current public webpack runtime was inspected directly. Its chunk-name and
content-hash maps are retained below as a discovery fallback, but every name and
hash is verified against the live ``app.js`` before any chunk is fetched. If the
site is rebuilt and the map changes, the workflow fails rather than silently
using stale asset URLs.
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
    'infrastructure','kwh','minute','axios','baseURL','.get(','.post(',
    'charging','connector','evse','country','city','latitude','longitude'
]

# Observed in the live webpack filename resolver on 2026-08-29. These values are
# discovery metadata, not charging/tariff data. Runtime verification below makes
# any front-end rebuild fail closed.
KNOWN_RUNTIME_CHUNKS = {
    131: ('texts-Imprint','10a8084b'),
    154: ('download-app','4441beec'),
    171: ('texts-PrivacyPolicy','59ec22f1'),
    208: ('texts-Terms-and-Conditions','e221c341'),
    269: ('user-login','3bff7df6'),
    405: ('texts-GtcCopy','efe473f8'),
    445: ('reset-password','f10a4e15'),
    524: ('webapp-download','e72a9f94'),
    546: ('help','3c1dcb3a'),
    711: ('texts-InstallationPartners','bda6345f'),
    761: ('texts-Cookies','fc7e4b7c'),
    763: ('webmap','5c977612'),
    919: ('user-account','68949600'),
    932: ('texts-TermsOfUse','465473b7'),
    939: ('home','ac225ad7'),
    941: ('contacts','54d57b66'),
    1002: ('texts-OurPartner','541e76d9'),
    1020: ('1020','58150553'),
}


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/javascript,*/*'})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.read(), getattr(r, 'status', 200), r.geturl()
    except urllib.error.HTTPError as e:
        return e.read(), e.code, e.geturl()


def snips(text, token, r=1400, limit=18):
    out=[]; low=text.lower(); t=token.lower(); start=0
    while len(out)<limit:
        i=low.find(t,start)
        if i<0: break
        out.append(text[max(0,i-r):min(len(text),i+len(token)+r)])
        start=i+len(token)
    return out


def verified_runtime_chunks(app: str):
    missing=[]; rows=[]
    for chunk_id,(name,h) in sorted(KNOWN_RUNTIME_CHUNKS.items()):
        # Both literals must still occur in the current public runtime. For the
        # unnamed numeric chunk only the hash and chunk id can be asserted.
        name_ok = name in app if not name.isdigit() else str(chunk_id) in app
        hash_ok = h in app
        if not (name_ok and hash_ok):
            missing.append({'chunkId':chunk_id,'name':name,'hash':h,'namePresent':name_ok,'hashPresent':hash_ok})
        rows.append({'chunkId':chunk_id,'name':name,'hash':h})
    if missing:
        raise RuntimeError(f'Qwello runtime chunk map changed: {missing}')
    if 'webmap' not in app or 'home' not in app:
        raise RuntimeError('Qwello runtime missing expected webmap/home chunk markers')
    return rows


def candidate_literals(text: str):
    literals=[]
    for m in re.finditer(r'["\']([^"\']{1,420})["\']', text):
        v=m.group(1); lo=v.lower()
        if any(k in lo for k in (
            '/public','service','price','pric','tarif','location','station','charger',
            'kwh','minute','map','geo','country','city','operator','evse','connector',
            'latitude','longitude','charging'
        )):
            literals.append(v)
    return list(dict.fromkeys(literals))[:1600]


def main():
    raw,status,_=fetch(APP)
    if status!=200:
        raise RuntimeError(f'Qwello app bundle HTTP {status}')
    app=raw.decode('utf-8','replace')
    pairs=verified_runtime_chunks(app)

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
        'schemaVersion':'0.4.0','dataset':'germany-qwello-chunk-discovery',
        'runtimeMapMode':'verified-observed-map','pairCount':len(pairs),
        'reachableChunkCount':sum(1 for r in rows if r.get('httpStatus')==200),
        'relevantChunkCount':len(relevant),'tokenChunkCounts':dict(hit_counts),'chunks':rows,
    }
    p=Path('data/germany/qwello_chunk_discovery.json');p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_QWELLO_CHUNK_DISCOVERY='+json.dumps({
        'runtimeMapMode':out['runtimeMapMode'],'pairCount':len(pairs),
        'reachableChunkCount':out['reachableChunkCount'],'relevantChunkCount':len(relevant),
        'tokenChunkCounts':dict(hit_counts),'resolvedChunks':pairs,
        'relevantChunks':[
            {'chunkId':r['chunkId'],'name':r['name'],'hash':r['hash'],'url':r['url'],'bytes':r['bytes'],
             'tokens':sorted(r.get('tokenHits') or {}),'candidateLiterals':r.get('candidateLiterals',[])[:240],
             'snippets':{k:v[:6] for k,v in (r.get('tokenHits') or {}).items()}}
            for r in relevant
        ]
    },ensure_ascii=False,sort_keys=True))

if __name__=='__main__':main()
