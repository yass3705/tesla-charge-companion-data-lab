#!/usr/bin/env python3
from __future__ import annotations
import json, urllib.error, urllib.request
from pathlib import Path

BASE="https://prod.apix.alzp.tgscloud.net/evdc-bff-europe/v0.0.1"
ROUTES=[
    "/v3/infrastructure/locations",
    "/v2/infrastructure/locations/status",
    "/v2/infrastructure/locations/timestamp",
    "/v3/references/filters",
    "/v1/references/filters/timestamp",
]
OUT=Path("reports/belgium/totalenergies")
OUT.mkdir(parents=True,exist_ok=True)

def get(path):
    url=BASE+path
    req=urllib.request.Request(url,headers={
        "Accept":"application/json",
        "User-Agent":"TotalEnergies-Europe-static-probe/1.0"
    })
    row={"path":path,"url":url}
    try:
        with urllib.request.urlopen(req,timeout=40) as resp:
            raw=resp.read()
            row["status"]=resp.status
            row["headers"]={k:v for k,v in resp.headers.items() if k.lower() in ("content-type","www-authenticate","x-request-id","server")}
            row["body"]=raw.decode("utf-8","replace")[:5000]
    except urllib.error.HTTPError as e:
        raw=e.read()
        row["status"]=e.code
        row["headers"]={k:v for k,v in e.headers.items() if k.lower() in ("content-type","www-authenticate","x-request-id","server")}
        row["body"]=raw.decode("utf-8","replace")[:5000]
    except Exception as e:
        row["status"]=None
        row["error"]=type(e).__name__+": "+str(e)
    return row

results=[get(x) for x in ROUTES]
out={"baseUrl":BASE,"results":results}
(OUT/"charge-europe-api-unauth-probe-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
