#!/usr/bin/env python3
from __future__ import annotations
import json, urllib.parse, urllib.request
from pathlib import Path

OUT=Path("reports/belgium")
OUT.mkdir(parents=True,exist_ok=True)

BASE="https://transportdata.be/api/3/action/package_search"
queries=[
    "charging infrastructure",
    "electric vehicle charging",
    "AFIR charging",
    "Monta",
    "EnergyVision",
    "Indigo evcharging",
]

def get_json(url):
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"TCC-Belgium-AFIR-audit/1.0"})
    with urllib.request.urlopen(req,timeout=60) as r:
        return json.loads(r.read())

seen={}
for q in queries:
    url=BASE+"?"+urllib.parse.urlencode({"q":q,"rows":100})
    try:
        data=get_json(url)
    except Exception as e:
        continue
    for p in ((data.get("result") or {}).get("results") or []):
        pid=p.get("id") or p.get("name")
        if not pid: continue
        resources=[]
        for r in p.get("resources") or []:
            resources.append({
                "id":r.get("id"),
                "name":r.get("name"),
                "format":r.get("format"),
                "url":r.get("url"),
                "url_type":r.get("url_type"),
                "resource_type":r.get("resource_type"),
                "description":r.get("description"),
            })
        seen[pid]={
            "id":p.get("id"),
            "name":p.get("name"),
            "title":p.get("title"),
            "organization":(p.get("organization") or {}).get("title"),
            "notes":p.get("notes"),
            "metadata_modified":p.get("metadata_modified"),
            "resources":resources,
        }

# Keep likely EV-charging datasets only.
keywords=("charging","charger","evcharging","electric vehicle","afir","recharge")
items=[]
for p in seen.values():
    blob=(" ".join(str(p.get(k) or "") for k in ("name","title","notes","organization"))).lower()
    if any(k in blob for k in keywords):
        items.append(p)
items.sort(key=lambda x:((x.get("organization") or ""), (x.get("title") or "")))

payload={
    "country":"BE",
    "asOf":"2026-09-28",
    "source":"transportdata.be CKAN package_search",
    "datasetCount":len(items),
    "datasets":items,
}
(OUT/"belgium-afir-additional-datasets-discovery-2026-09-28.json").write_text(
    json.dumps(payload,ensure_ascii=False,indent=2)+"\n"
)
print(json.dumps({
    "datasetCount":len(items),
    "datasets":[
        {"title":x.get("title"),"organization":x.get("organization"),"resources":len(x.get("resources") or [])}
        for x in items
    ]
},ensure_ascii=False,indent=2))
