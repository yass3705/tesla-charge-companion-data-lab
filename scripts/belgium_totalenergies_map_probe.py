#!/usr/bin/env python3
from __future__ import annotations
import json, re, subprocess, urllib.parse
from pathlib import Path

OUT=Path("reports/belgium/totalenergies")
OUT.mkdir(parents=True, exist_ok=True)

TARGETS=[
  "https://map.be-mo.io/",
  "https://totalms.webgeoservices.com/",
  "https://services.totalenergies.be/fr/faq/mobilite-electrique/comment-trouver-les-bornes-de-recharge-sur-mon-trajet",
]

def curl(url):
    cmd=["curl","-LsS","--retry","2","--connect-timeout","15","--max-time","45",
         "-A","Mozilla/5.0","-w","\\n__HTTP__%{http_code}\\n__URL__%{url_effective}",url]
    p=subprocess.run(cmd,capture_output=True,text=True)
    body=p.stdout
    status=0
    final=url
    m=re.search(r"\\n__HTTP__(\\d+)\\n__URL__(.*)$",body,re.S)
    if m:
        status=int(m.group(1))
        final=m.group(2).strip()
        body=body[:m.start()]
    return {"url":url,"finalUrl":final,"status":status,"body":body,"stderr":p.stderr[-1000:]}

def extract_assets(base,html):
    out=[]
    for pat in [r"<script[^>]+src=[\"']([^\"']+)", r"<link[^>]+href=[\"']([^\"']+)"]:
        for x in re.findall(pat,html,re.I):
            u=urllib.parse.urljoin(base,x)
            if u not in out:
                out.append(u)
    return out

def inspect_text(url,text):
    urls=sorted(set(re.findall(r"https?://[^\"'\\\\\\s<>]+",text)))
    routes=[]
    for q in re.findall(r"[\"']([^\"']{2,350})[\"']",text):
        ql=q.lower()
        if any(k in ql for k in ("api","station","charger","evse","tariff","price","connector","poi","location","store","map")) and ("/" in q or "?" in q):
            if q not in routes:
                routes.append(q)
    strings=[]
    for q in re.findall(r"[\"']([^\"'\\\\]{3,220})[\"']",text):
        ql=q.lower()
        if any(k in ql for k in ("tariff","price","pricing","evse","station","charger","connector","woosmap","webgeoservices")):
            if q not in strings:
                strings.append(q)
    return {"url":url,"bytes":len(text),"urls":urls[:500],"routes":routes[:1500],"interestingStrings":strings[:1000]}

pages=[]
scripts=[]
for target in TARGETS:
    res=curl(target)
    pages.append({k:v for k,v in res.items() if k!="body"})
    if res["status"]==200:
        assets=extract_assets(res["finalUrl"],res["body"])
        pages[-1]["assets"]=assets
        pages[-1]["inspection"]=inspect_text(res["finalUrl"],res["body"])
        for u in assets:
            if ".js" not in u.lower():
                continue
            rr=curl(u)
            item={k:v for k,v in rr.items() if k!="body"}
            if rr["status"]==200:
                item["inspection"]=inspect_text(rr["finalUrl"],rr["body"])
            scripts.append(item)

france_fingerprints={
  "mapHost":"totalms.webgeoservices.com",
  "woosmapSearch":"https://api.woosmap.com/stores/search/",
  "vistaPoi":"https://api.vista.alzp.tgscloud.net/REVERSE/api/Info/Poi",
}
serialized=json.dumps({"pages":pages,"scripts":scripts},ensure_ascii=False).lower()
lineage={
  "mentionsWebGeoServices":"webgeoservices" in serialized,
  "mentionsWoosmap":"woosmap" in serialized,
  "mentionsVistaPoi":"vista.alzp.tgscloud.net" in serialized or "/reverse/api/info/poi" in serialized,
  "mentionsPrice":"price" in serialized or "tarif" in serialized,
}

out={
  "operator":"TotalEnergies","country":"BE",
  "purpose":"Compare Belgium public charging-map lineage with validated France TotalEnergies map stack",
  "franceFingerprints":france_fingerprints,
  "lineage":lineage,
  "pages":pages,
  "scripts":scripts,
}
(OUT/"map-backend-lineage-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\\n",encoding="utf-8")
print(json.dumps({"lineage":lineage,"pages":[{"url":p["url"],"finalUrl":p["finalUrl"],"status":p["status"],"assets":len(p.get("assets",[]))} for p in pages]},ensure_ascii=False,indent=2))
