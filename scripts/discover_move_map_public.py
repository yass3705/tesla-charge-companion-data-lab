#!/usr/bin/env python3
import json,re,urllib.request,urllib.parse,html
from pathlib import Path
from datetime import datetime,timezone

URLS=["https://www.move.ch/karte/_genf.html","https://www.move.ch/karte/"]
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"}
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"pages":[],"scripts":[]}
seen=set()
for url in URLS:
    try:
        req=urllib.request.Request(url,headers=UA)
        with urllib.request.urlopen(req,timeout=40) as r:
            body=r.read(4000000).decode("utf-8","replace"); final=r.geturl()
        srcs=[]
        for s in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']',body,re.I):
            su=urllib.parse.urljoin(final,html.unescape(s))
            if su not in seen: seen.add(su); srcs.append(su)
        out["pages"].append({"url":url,"finalUrl":final,"bytes":len(body),"scripts":srcs,
            "interesting":sorted(set(re.findall(r'https?://[^\s"\'<>]{5,500}|[^"\'\s<>]{0,80}(?:api|graphql|station|charger|tariff|price|map)[^"\'\s<>]{0,120}',body,re.I)))[:1000]})
    except Exception as e:
        out["pages"].append({"url":url,"error":type(e).__name__+": "+str(e)})
for su in sorted(seen):
    try:
        req=urllib.request.Request(su,headers=UA)
        with urllib.request.urlopen(req,timeout=50) as r:
            raw=r.read(20000000); ct=r.headers.get("content-type","")
        txt=raw.decode("utf-8","replace")
        hits=[]
        pats=[
            r'https?://[^\s"\'<>]{5,800}',
            r'["\']([^"\']*(?:api|graphql|station|charger|chargepoint|tariff|price|connector|map|ocpi)[^"\']*)["\']'
        ]
        for pat in pats:
            for m in re.finditer(pat,txt,re.I):
                v=m.group(1) if m.lastindex else m.group(0)
                if 3<len(v)<1200 and v not in hits:hits.append(v)
                if len(hits)>=1500: break
            if len(hits)>=1500: break
        out["scripts"].append({"url":su,"bytes":len(raw),"contentType":ct,"hits":hits})
    except Exception as e:
        out["scripts"].append({"url":su,"error":type(e).__name__+": "+str(e)})
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-move-map-public-discovery-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"pages":out["pages"],"scriptCount":len(out["scripts"]),"hitScripts":sum(bool(x.get("hits")) for x in out["scripts"])},ensure_ascii=False,indent=2))
