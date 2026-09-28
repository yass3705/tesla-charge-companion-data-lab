#!/usr/bin/env python3
import json,re,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from datetime import datetime,timezone

UA={"User-Agent":"Mozilla/5.0 TCC-V9-Switzerland/1.0","Accept":"text/html,application/xhtml+xml,application/json,*/*"}
roots=[
 "https://adhoc.swisscharge.ch/tenant/Swisscharge_CH/search",
 "https://wiki.eponet.ch/books/e-mobilitat-fahrzeug-laden-an-einer-ladestation/page/laden-mit-qr-code-ad-hoc-laden",
 "https://www.partino.ch/",
 "https://www.iwb.ch/servicecenter/oeffentliches-ladenetz/mobilitaet-tarife",
]
def get(url):
    req=urllib.request.Request(url,headers=UA)
    try:
        with urllib.request.urlopen(req,timeout=35) as r:
            raw=r.read(4000000)
            return {"url":url,"status":r.status,"finalUrl":r.geturl(),"contentType":r.headers.get("content-type"),"body":raw.decode("utf-8","replace")}
    except urllib.error.HTTPError as e:
        raw=e.read(1000000)
        return {"url":url,"status":e.code,"finalUrl":url,"contentType":e.headers.get("content-type"),"body":raw.decode("utf-8","replace")}
    except Exception as e:
        return {"url":url,"error":type(e).__name__+": "+str(e),"body":""}

pages=[]
assets=[]
for root in roots:
    p=get(root); pages.append(p)
    base=p.get("finalUrl") or root
    body=p.get("body","")
    srcs=re.findall(r'<script[^>]+src=["\']([^"\']+)',body,re.I)
    hrefs=re.findall(r'<link[^>]+href=["\']([^"\']+)',body,re.I)
    for x in srcs+hrefs:
        u=urllib.parse.urljoin(base,x)
        if any(k in u for k in (".js",".mjs","bundle","main","chunk")):
            a=get(u); a["root"]=root; assets.append(a)

patterns=[
 r'https?://[^"\'\s<>]+',
 r'/(?:api|v1|v2|v3|graphql|tenant|station|stations|charge|charging|tariff|price|prices|search|location|locations)[A-Za-z0-9_?&=./{}:\-]*',
 r'[A-Za-z0-9_\-]*(?:tariff|price|station|evse|connector|adhoc|payment)[A-Za-z0-9_\-]*'
]
hits=[]
for obj in pages+assets:
    text=obj.get("body","")
    hh=[]
    for pat in patterns:
        for m in re.findall(pat,text,re.I):
            if isinstance(m,tuple): m="".join(m)
            if len(m)>2: hh.append(m[:500])
    uniq=[]
    seen=set()
    for h in hh:
        if h not in seen:
            seen.add(h); uniq.append(h)
    hits.append({"url":obj.get("url"),"status":obj.get("status"),"contentType":obj.get("contentType"),"hits":uniq[:800]})

# Probe likely Swisscharge API routes discovered/common SPA patterns.
base="https://adhoc.swisscharge.ch"
probe_paths=[
 "/api","/api/","/api/config","/api/tenant/Swisscharge_CH","/api/tenant/Swisscharge_CH/search",
 "/api/v1/tenant/Swisscharge_CH/search","/api/v1/stations","/api/v1/search",
 "/tenant/Swisscharge_CH/api/search","/backend/tenant/Swisscharge_CH/search",
 "/config.json","/assets/config.json","/environment.json","/assets/environment.json"
]
probes=[]
for path in probe_paths:
    p=get(base+path)
    probes.append({k:p.get(k) for k in ("url","status","finalUrl","contentType","error")} | {"bodyPreview":p.get("body","")[:2000]})

out={"generatedAt":datetime.now(timezone.utc).isoformat(),"pages":[{k:v for k,v in p.items() if k!="body"} for p in pages],"assets":[{k:v for k,v in a.items() if k!="body"} for a in assets],"hits":hits,"probes":probes}
Path("docs/switzerland-residual-public-backend-discovery-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"assets":out["assets"],"interesting":[h for h in hits if h["hits"]][:12],"probes":probes},ensure_ascii=False,indent=2)[:120000])
