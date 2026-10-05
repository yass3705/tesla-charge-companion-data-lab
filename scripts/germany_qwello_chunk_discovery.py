#!/usr/bin/env python3
"""Discover Qwello public lazy chunks and candidate station/pricing API routes.

This is staging research for the Germany catalogue targeted at TCC V9.  The
Qwello public site currently uses a Webpack 4 runtime whose lazy-chunk resolver
is keyed by *named strings* (for example ``home``), not numeric Webpack 5 ids.
The resolver is parsed live on every run so a front-end rebuild fails closed
instead of silently reusing stale asset hashes.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse

SHELL = 'https://qwello.de/de/how-to'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'
TOKENS = [
    'services.qwello.eu','VUE_APP_SERVICES_URL','VUE_APP_USER_SERVICE_URL',
    '/public/','public/web','pricing','price','tariff','tarif','location','locations',
    'station','stations','charger','chargers','0.49','0,49','0.51','0,51',
    'infrastructure','kwh','minute','axios','baseURL','.get(','.post(',
    'charging','connector','evse','country','city','latitude','longitude',
    'map','cluster','bounds','viewport','coordinates','socket'
]


def fetch(url, accept='application/javascript,*/*'):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.read(), getattr(r, 'status', 200), r.geturl(), dict(r.headers.items())
    except urllib.error.HTTPError as e:
        return e.read(), e.code, e.geturl(), dict(e.headers.items())


def shell_app_url():
    raw,status,final,_ = fetch(SHELL, 'text/html,*/*')
    if status != 200:
        raise RuntimeError(f'Qwello shell HTTP {status}')
    html=raw.decode('utf-8','replace')
    srcs=re.findall(r'<script\b[^>]*\bsrc\s*=\s*["\']?([^"\'\s>]+)',html,re.I)
    urls=[urljoin(final,s) for s in srcs]
    apps=[u for u in urls if re.search(r'/js/app(?:\.[A-Za-z0-9_-]+)?\.js(?:\?|$)',u)]
    if not apps:
        raise RuntimeError(f'Qwello shell has no app bundle: {urls}')
    return apps[-1], urls


def parse_object_pairs(obj: str):
    """Parse a minified JS object whose values are quoted strings."""
    out={}
    pat=re.compile(r'(?:(?:"([^"\\]*(?:\\.[^"\\]*)*)")|([A-Za-z_$][A-Za-z0-9_$]*))\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"')
    for m in pat.finditer(obj):
        key=m.group(1) if m.group(1) is not None else m.group(2)
        value=m.group(3)
        key=bytes(key,'utf-8').decode('unicode_escape') if '\\' in key else key
        value=bytes(value,'utf-8').decode('unicode_escape') if '\\' in value else value
        out[key]=value
    return out


def parse_webpack4_chunk_resolver(app: str):
    # Current shape (variable names may change):
    # function c(e){return s.p+"js/"+({home:"home",...}[e]||e)+"."+
    #   {home:"78332419",...}[e]+".js"}
    patterns=[
        re.compile(
            r'function\s+[A-Za-z_$][A-Za-z0-9_$]*\(e\)\{return\s+[A-Za-z_$][A-Za-z0-9_$]*\.p\+"js/"\+\((\{.*?\})\[e\]\|\|e\)\+"\."\+(\{.*?\})\[e\]\+"\.js"\}',
            re.S,
        ),
        re.compile(
            r'\.p\+"js/"\+\((\{.*?\})\[e\]\|\|e\)\+"\."\+(\{.*?\})\[e\]\+"\.js"',
            re.S,
        ),
    ]
    match=None
    for pat in patterns:
        match=pat.search(app)
        if match: break
    if not match:
        raise RuntimeError('Qwello Webpack 4 JS chunk resolver not found')
    names=parse_object_pairs(match.group(1))
    hashes=parse_object_pairs(match.group(2))
    if len(hashes) < 10:
        raise RuntimeError(f'implausibly small Qwello JS hash map: {len(hashes)}')
    missing_names=sorted(set(hashes)-set(names))
    rows=[]
    for key,h in hashes.items():
        name=names.get(key,key)
        rows.append({'chunkKey':key,'name':name,'hash':h})
    return rows, {
        'nameEntryCount':len(names),
        'hashEntryCount':len(hashes),
        'hashKeysMissingNameEntry':missing_names,
    }


def snips(text, token, radius=1300, limit=12):
    out=[]; low=text.lower(); needle=token.lower(); start=0
    while len(out)<limit:
        i=low.find(needle,start)
        if i<0: break
        out.append(text[max(0,i-radius):min(len(text),i+len(token)+radius)])
        start=i+len(token)
    return out


def candidate_literals(text: str):
    literals=[]
    for m in re.finditer(r'["\']([^"\']{1,500})["\']', text):
        v=m.group(1); lo=v.lower()
        if any(k in lo for k in (
            '/public','service','price','pric','tarif','location','station','charger',
            'kwh','minute','map','geo','country','city','operator','evse','connector',
            'latitude','longitude','charging','cluster','bound','viewport','socket'
        )):
            literals.append(v)
    return list(dict.fromkeys(literals))[:1800]


def absolute_urls(text: str):
    vals=re.findall(r'https?://[^"\'\s<>\\]+',text,re.I)
    return list(dict.fromkeys(vals))[:1000]


def main():
    app_url,shell_scripts=shell_app_url()
    raw,status,final,_=fetch(app_url)
    if status != 200:
        raise RuntimeError(f'Qwello app bundle HTTP {status}')
    app=raw.decode('utf-8','replace')
    pairs,parse_meta=parse_webpack4_chunk_resolver(app)

    parsed=urlparse(final)
    js_base=f'{parsed.scheme}://{parsed.netloc}/js/'
    rows=[]; hit_counts=Counter()
    for pair in pairs:
        url=urljoin(js_base,f"{pair['name']}.{pair['hash']}.js")
        raw,status,chunk_final,_=fetch(url)
        row={**pair,'url':chunk_final,'httpStatus':status,'bytes':len(raw)}
        if status != 200:
            row['error']=f'HTTP {status}'
            rows.append(row)
            continue
        text=raw.decode('utf-8','replace'); hits={}
        for token in TOKENS:
            if token.lower() in text.lower():
                hits[token]=snips(text,token); hit_counts[token]+=1
        row['tokenHits']=hits
        if hits:
            row['candidateLiterals']=candidate_literals(text)
            row['absoluteUrls']=absolute_urls(text)
        rows.append(row)

    # The app bundle itself contains environment/base URLs and can also contain
    # request routes, so report its candidates separately from lazy chunks.
    app_hits={}
    for token in TOKENS:
        if token.lower() in app.lower():
            app_hits[token]=snips(app,token)

    relevant=[r for r in rows if r.get('tokenHits')]
    out={
        'schemaVersion':'0.5.0',
        'dataset':'germany-qwello-chunk-discovery',
        'targetVersion':'V9',
        'stagedOnly':True,
        'publishesToTcc':False,
        'tariffsRankable':False,
        'runtimeMapMode':'live-webpack4-named-resolver',
        'shellUrl':SHELL,
        'shellScripts':shell_scripts,
        'appUrl':final,
        'resolver':parse_meta,
        'pairCount':len(pairs),
        'reachableChunkCount':sum(1 for r in rows if r.get('httpStatus')==200),
        'relevantChunkCount':len(relevant),
        'tokenChunkCounts':dict(hit_counts),
        'appTokenHits':app_hits,
        'appCandidateLiterals':candidate_literals(app),
        'appAbsoluteUrls':absolute_urls(app),
        'chunks':rows,
    }
    p=Path('data/germany/qwello_chunk_discovery.json');p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_QWELLO_CHUNK_DISCOVERY='+json.dumps({
        'targetVersion':'V9','runtimeMapMode':out['runtimeMapMode'],'appUrl':final,
        'resolver':parse_meta,'pairCount':len(pairs),'reachableChunkCount':out['reachableChunkCount'],
        'relevantChunkCount':len(relevant),'tokenChunkCounts':dict(hit_counts),
        'appCandidateLiterals':out['appCandidateLiterals'][:180],
        'appAbsoluteUrls':out['appAbsoluteUrls'][:80],
        'resolvedChunks':pairs,
        'relevantChunks':[
            {'chunkKey':r['chunkKey'],'name':r['name'],'hash':r['hash'],'url':r['url'],'bytes':r['bytes'],
             'tokens':sorted(r.get('tokenHits') or {}),'candidateLiterals':r.get('candidateLiterals',[])[:240],
             'absoluteUrls':r.get('absoluteUrls',[])[:80],
             'snippets':{k:v[:5] for k,v in (r.get('tokenHits') or {}).items()}}
            for r in relevant
        ],
    },ensure_ascii=False,sort_keys=True))

if __name__=='__main__':
    main()
