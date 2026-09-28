#!/usr/bin/env python3
from __future__ import annotations
import json, urllib.request, urllib.error
from pathlib import Path

BASE="https://public.mycardprd.alzp.tgscloud.net/chargeplus-bff/v2/pois/"
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)

targets=[
 {"sample":"Braine-l'Alleud","poiListId":"BEMO-59d3895777","expected":{"lat":50.66876,"lon":4.384442}},
 {"sample":"Boom","poiListId":"BEMO-55e8f80cda","expected":{"lat":51.099934,"lon":4.368176}},
 {"sample":"Alken-nearest-1","poiListId":"BEMO-46a9cd34f6","expected":{"lat":50.88475,"lon":5.299239}},
 {"sample":"Alken-nearest-2","poiListId":"BEMO-c1a18c9106","expected":{"lat":50.88475,"lon":5.299239}},
 {"sample":"Alken-nearest-3","poiListId":"BEMO-671f40291e","expected":{"lat":50.88475,"lon":5.299239}},
]

def get(url):
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"tesla-charge-companion-data-lab/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            body=r.read().decode("utf-8","replace")
            return {"url":url,"status":r.status,"contentType":r.headers.get("content-type"),"body":body[:300000]}
    except urllib.error.HTTPError as e:
        return {"url":url,"status":e.code,"contentType":e.headers.get("content-type"),"body":e.read().decode("utf-8","replace")[:300000]}
    except Exception as e:
        return {"url":url,"status":0,"error":type(e).__name__+": "+str(e)}

results=[]
for t in targets:
    pid=t["poiListId"]
    suffix=pid.split("BEMO-",1)[-1]
    variants=[
       ("suffix", BASE+"2-"+suffix+"/details"),
       ("full", BASE+"2-"+pid+"/details"),
    ]
    rr=[]
    for label,url in variants:
        r=get(url)
        parsed=None
        try: parsed=json.loads(r.get("body",""))
        except Exception: pass
        rr.append({"variant":label,**r,"json":parsed})
    results.append({"target":t,"tests":rr})

payload={"purpose":"Resolve Charge+ POI details and internal BeMo connector GUIDs for Belgian TotalEnergies samples","results":results}
(OUT/"chargeplus-poi-details-guid-2026-09-28.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"summary":[{"sample":x["target"]["sample"],"statuses":[(t["variant"],t["status"]) for t in x["tests"]]} for x in results]},ensure_ascii=False,indent=2))
