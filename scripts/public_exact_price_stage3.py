#!/usr/bin/env python3
"""Final focused public-web probe for Freshmile and Qovoltis exact-price routes.

Freshmile: traverse public Nuxt JS chunks and extract sanitized API/location/tariff route strings.
Qovoltis: inspect public landing HTML inline navigation/form strings.
No authentication, cookies, POSTs, credentials, mobile packages, or raw-body persistence.
"""
from __future__ import annotations
import argparse, hashlib, html, json, re, ssl, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
ABS_RE=re.compile(r"https?://[^\s\"'`<>]+",re.I)
NUXT_JS_RE=re.compile(r"(?:https?://charge\.freshmile\.com)?(/_nuxt/[A-Za-z0-9_.-]+\.js)",re.I)
QUOTED_RE=re.compile(r"[\"'`]([^\"'`<>]{2,260})[\"'`]")
INLINE_SCRIPT_RE=re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",re.I|re.S)
ATTR_RE=re.compile(r"\b(?:href|action|formaction|onclick)=[\"']([^\"']+)[\"']",re.I)
KEYWORDS=("api","graphql","location","locations","station","stations","evse","evses","connector","tariff","tariffs","price","prices","pricing","chargepoint","charger","payment","card","guest")

def now_iso():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def clean_url(u):
    p=urllib.parse.urlsplit(u);return urllib.parse.urlunsplit((p.scheme,p.netloc.lower(),re.sub(r'/{2,}','/',p.path or '/'),'',''))
def fetch(url,limit=6_000_000):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/javascript,text/javascript,application/json;q=0.9,*/*;q=0.8','Cache-Control':'no-cache'},method='GET')
    ctx=ssl.create_default_context()
    try:
        with urllib.request.urlopen(req,timeout=35,context=ctx) as r:
            raw=r.read(limit);status=int(getattr(r,'status',200));final=r.geturl();ctype=r.headers.get('Content-Type','').split(';',1)[0].strip().lower()
    except urllib.error.HTTPError as e:
        raw=e.read(min(limit,200_000));status=e.code;final=e.geturl();ctype=e.headers.get('Content-Type','').split(';',1)[0].strip().lower() if e.headers else ''
    return {'status':status,'final':final,'ctype':ctype,'text':raw.decode('utf-8',errors='replace'),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def interesting(s):
    l=s.lower();return any(k in l for k in KEYWORDS)
def sanitize_literal(base,s):
    s=html.unescape(s).strip().rstrip('),.;')
    if any(x in s for x in ('${','{','}','<','>','\\')):return None
    if s.startswith('http://') or s.startswith('https://'):
        try:return clean_url(s)
        except Exception:return None
    if s.startswith('/'):
        try:return clean_url(urllib.parse.urljoin(base,s))
        except Exception:return None
    return s[:240]

def freshmile():
    root='https://charge.freshmile.com/'
    page=fetch(root)
    queue=[];seen=set();chunks=[];candidates=set()
    for m in NUXT_JS_RE.findall(page['text']):queue.append(clean_url(urllib.parse.urljoin(root,m)))
    while queue and len(seen)<40:
        u=queue.pop(0)
        if u in seen:continue
        seen.add(u)
        try:r=fetch(u)
        except Exception:continue
        chunks.append({'url':u,'httpStatus':r['status'],'bytesRead':r['bytes'],'contentSha256':r['sha256']})
        for m in NUXT_JS_RE.findall(r['text']):
            v=clean_url(urllib.parse.urljoin(root,m))
            if v not in seen and v not in queue:queue.append(v)
        for raw in ABS_RE.findall(r['text']):
            if interesting(raw):
                v=sanitize_literal(u,raw)
                if v:candidates.add(v)
        for raw in QUOTED_RE.findall(r['text']):
            if interesting(raw):
                v=sanitize_literal(u,raw)
                if v:candidates.add(v)
    filtered=[]
    for x in sorted(candidates):
        lx=x.lower()
        if any(lx.endswith(ext) for ext in ('.css','.png','.jpg','.jpeg','.svg','.woff','.woff2')):continue
        if 'freshmile.com' in lx or x.startswith('/') or not x.startswith('http'):
            filtered.append(x)
    route_like=[x for x in filtered if any(k in x.lower() for k in ('api','location','evse','station','tariff','price','graphql'))]
    return {'target':'freshmile','seed':{'httpStatus':page['status'],'bytesRead':page['bytes'],'contentSha256':page['sha256']},'chunksInspected':len(chunks),'chunks':chunks,'candidateStrings':filtered[:200],'routeLikeCandidates':route_like[:160],'conclusion':{'usablePublicRouteStringFound':bool(route_like),'nextStep':'probe only concrete discovered route templates with public GET and required public identifiers' if route_like else 'stop Freshmile public-web exact-price discovery'}}
def qovoltis():
    root='https://chargenow.qovoltis.com/'
    page=fetch(root)
    strings=set()
    texts=[page['text']]+INLINE_SCRIPT_RE.findall(page['text'])
    for raw in ATTR_RE.findall(page['text']):
        v=sanitize_literal(root,raw)
        if v:strings.add(v)
    for t in texts:
        for raw in ABS_RE.findall(t):
            if interesting(raw):
                v=sanitize_literal(root,raw)
                if v:strings.add(v)
        for raw in QUOTED_RE.findall(t):
            if interesting(raw) or raw.startswith('/'):
                v=sanitize_literal(root,raw)
                if v:strings.add(v)
    useful=[]
    for x in sorted(strings):
        lx=x.lower()
        if any(lx.endswith(ext) for ext in ('.css','.png','.jpg','.jpeg','.svg','.woff','.woff2','.js')):continue
        if 'cdn-cgi' in lx or 'cloudflare' in lx:continue
        useful.append(x)
    flow=[x for x in useful if any(k in x.lower() for k in ('pay','payment','card','guest','charge','station','borne','start'))]
    return {'target':'qovoltis','seed':{'httpStatus':page['status'],'bytesRead':page['bytes'],'contentSha256':page['sha256']},'publicNavigationStrings':useful[:160],'cardFlowCandidates':flow[:100],'conclusion':{'publicCardFlowCandidateFound':bool(flow),'nextStep':'probe concrete same-vendor public flow route if present' if flow else 'stop Qovoltis public-web exact-price discovery; app/interactive station flow required'}}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--target',choices=('freshmile','qovoltis'),required=True);ap.add_argument('--out',required=True);a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    d={'schemaVersion':'1.0.0','dataset':f'{a.target}-public-exact-price-stage3','generatedAt':now_iso(),'method':{'authenticated':False,'mobilePackageUsed':False,'persistRawBodies':False,'httpMethods':['GET']}}
    d.update(freshmile() if a.target=='freshmile' else qovoltis())
    (out/f'{a.target}_stage3.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'SUMMARY.md').write_text(f"# {a.target} stage 3\n\n`{json.dumps(d['conclusion'],ensure_ascii=False)}`\n",encoding='utf-8')
    print(json.dumps(d['conclusion'],ensure_ascii=False))
if __name__=='__main__':main()
