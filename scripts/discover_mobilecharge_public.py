#!/usr/bin/env python3
import json,re,urllib.request,urllib.parse,html
from pathlib import Path
from datetime import datetime,timezone

URLS=["https://cloud.mobilecharge.ch/csp/ferratec/data/stations/","https://cloud.mobilecharge.ch/"]
UA={"User-Agent":"Mozilla/5.0","Accept":"text/html,application/xhtml+xml,application/json"}
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"pages":[],"scripts":[]}
seen=set()
for url in URLS:
    try:
        req=urllib.request.Request(url,headers=UA)
        with urllib.request.urlopen(req,timeout=40) as r:
            body=r.read(5000000).decode("utf-8","replace"); final=r.geturl()
        srcs=[]
        for s in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']',body,re.I):
            su=urllib.parse.urljoin(final,html.unescape(s))
            if su not in seen: seen.add(su); srcs.append(su)
        hits=sorted(set(re.findall(r'https?://[^\s"\'<>]{5,700}|[^"\'\s<>]{0,100}(?:api|ajax|station|price|tariff|directpayment|qr|caspio)[^"\'\s<>]{0,150}',body,re.I)))
        out["pages"].append({"url":url,"finalUrl":final,"bytes":len(body),"scripts":srcs,"hits":hits[:1200]})
    except Exception as e:
        out["pages"].append({"url":url,"error":type(e).__name__+": "+str(e)})
for su in sorted(seen)[:100]:
    try:
        req=urllib.request.Request(su,headers=UA)
        with urllib.request.urlopen(req,timeout=40) as r:
            raw=r.read(12000000); ct=r.headers.get("content-type","")
        txt=raw.decode("utf-8","replace"); hits=[]
        for pat in [r'https?://[^\s"\'<>]{5,900}',r'["\']([^"\']*(?:api|ajax|station|price|tariff|directpayment|qr|caspio)[^"\']*)["\']']:
            for m in re.finditer(pat,txt,re.I):
                v=m.group(1) if m.lastindex else m.group(0)
                if 3<len(v)<1200 and v not in hits:hits.append(v)
                if len(hits)>=1200:break
            if len(hits)>=1200:break
        out["scripts"].append({"url":su,"contentType":ct,"bytes":len(raw),"hits":hits})
    except Exception as e:
        out["scripts"].append({"url":su,"error":type(e).__name__+": "+str(e)})
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-mobilecharge-public-discovery-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"pageCount":len(out["pages"]),"scriptCount":len(out["scripts"]),"hitScripts":sum(bool(x.get("hits")) for x in out["scripts"])},indent=2))
