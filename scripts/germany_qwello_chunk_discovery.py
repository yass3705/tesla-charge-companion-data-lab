#!/usr/bin/env python3
"""Inspect Qwello public Vue lazy chunks for location/pricing API calls.

Webpack stores chunk names and JavaScript content hashes in separate numeric
object literals. Rather than depending on the exact minified filename-resolver
syntax, this probe identifies the name map by semantic markers (``home`` and
``webmap``), identifies the hexadecimal hash map by overlapping numeric chunk
ids, and joins them deterministically.
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


def numeric_string_maps(app: str):
    """Return dense {numeric-id: quoted-string} object literals from minified JS."""
    maps=[]
    # The runtime maps are flat and comma-separated. Values do not contain quotes.
    pattern=re.compile(r'\{((?:\d+:["\'][^"\']+["\'](?:,|(?=\}))){5,})\}')
    for match in pattern.finditer(app):
        entries={int(k):v for k,v in re.findall(r'(\d+):["\']([^"\']+)["\']',match.group(1))}
        if len(entries)>=5:
            maps.append({'start':match.start(),'entries':entries})
    return maps


def parse_js_chunk_resolver(app: str):
    maps=numeric_string_maps(app)
    if not maps:
        raise RuntimeError('no dense numeric string maps found in Qwello runtime')

    # Name map is unambiguous in the current public app: it contains semantic route
    # chunk names including both home and webmap.
    name_candidates=[]
    for item in maps:
        values=set(item['entries'].values())
        score=sum(marker in values for marker in ('home','webmap','contacts','help','user-login'))
        if score:
            name_candidates.append((score,len(item['entries']),item))
    if not name_candidates:
        raise RuntimeError('Qwello chunk-name map with home/webmap markers not found')
    _,_,name_item=max(name_candidates,key=lambda x:(x[0],x[1]))
    names=name_item['entries']
    if 'home' not in names.values() or 'webmap' not in names.values():
        raise RuntimeError(f'Qwello name map incomplete: {names}')

    # Hash map: hexadecimal strings, strong overlap with name-map ids. Prefer the
    # candidate closest to the name map in the runtime if scores tie.
    hash_candidates=[]
    for item in maps:
        entries=item['entries']
        if item is name_item:
            continue
        hex_entries={k:v for k,v in entries.items() if re.fullmatch(r'[0-9a-f]{8,64}',v,re.I)}
        if len(hex_entries)<10:
            continue
        overlap=len(set(hex_entries)&set(names))
        if overlap<10:
            continue
        distance=abs(item['start']-name_item['start'])
        hash_candidates.append((overlap,len(hex_entries),-distance,item,hex_entries))
    if not hash_candidates:
        diagnostic=[{'start':m['start'],'size':len(m['entries']),'sample':list(m['entries'].items())[:5]} for m in maps[:20]]
        raise RuntimeError(f'Qwello JS hash map not found; maps={diagnostic}')
    _,_,_,hash_item,hashes=max(hash_candidates,key=lambda x:(x[0],x[1],x[2]))

    rows=[]
    for chunk_id,h in sorted(hashes.items()):
        rows.append({'chunkId':chunk_id,'name':names.get(chunk_id,str(chunk_id)),'hash':h})
    if len(rows)<10:
        raise RuntimeError(f'implausibly small Qwello JS chunk map: {len(rows)}')
    return rows,names,hashes,{
        'numericMapCount':len(maps),
        'nameMapStart':name_item['start'],
        'hashMapStart':hash_item['start'],
        'nameHashOverlap':len(set(names)&set(hashes)),
    }


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
    pairs,names,hashes,parse_meta = parse_js_chunk_resolver(app)

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
        'schemaVersion':'0.3.0',
        'dataset':'germany-qwello-chunk-discovery',
        'pairCount':len(pairs),
        'namedChunkCount':len(names),
        'hashChunkCount':len(hashes),
        'parseMeta':parse_meta,
        'reachableChunkCount':sum(1 for r in rows if r.get('httpStatus')==200),
        'relevantChunkCount':len(relevant),
        'tokenChunkCounts':dict(hit_counts),
        'chunks':rows,
    }
    p=Path('data/germany/qwello_chunk_discovery.json'); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_QWELLO_CHUNK_DISCOVERY='+json.dumps({
        'pairCount':len(pairs),
        'namedChunkCount':len(names),
        'reachableChunkCount':out['reachableChunkCount'],
        'relevantChunkCount':len(relevant),
        'parseMeta':parse_meta,
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
