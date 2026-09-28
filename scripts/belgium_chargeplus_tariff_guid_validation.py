#!/usr/bin/env python3
from __future__ import annotations
import json, urllib.parse, urllib.request, urllib.error
from pathlib import Path

BASE="https://public.mycardprd.alzp.tgscloud.net/chargeplus-bff/v1/pois/tariff"
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)

targets=[
 {"sample":"Braine-l'Alleud BE*TCB*E800106","connectorGuid":"82f3204d-2a3e-51f7-802b-0226f7bd5390","evseId":"BE*TCB*E800106","powerKw":50},
 {"sample":"Boom BE*TCB*E800372","connectorGuid":"986e2857-dd55-5739-872b-db252800bbf2","evseId":"BE*TCB*E800372","powerKw":300},
 {"sample":"Boom BE*TCB*E800373","connectorGuid":"bf4a89e0-f525-56b1-b760-ba6f00a588f5","evseId":"BE*TCB*E800373","powerKw":300},
]

def get(guid):
    url=BASE+"?"+urllib.parse.urlencode({"connectorId":guid})
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"tesla-charge-companion-data-lab/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            body=r.read().decode("utf-8","replace")
            return {"url":url,"status":r.status,"contentType":r.headers.get("content-type"),"body":body[:200000]}
    except urllib.error.HTTPError as e:
        return {"url":url,"status":e.code,"contentType":e.headers.get("content-type"),"body":e.read().decode("utf-8","replace")[:200000]}
    except Exception as e:
        return {"url":url,"status":0,"error":type(e).__name__+": "+str(e)}

results=[]
for t in targets:
    r=get(t["connectorGuid"])
    parsed=None
    try: parsed=json.loads(r.get("body",""))
    except Exception: pass
    results.append({"target":t,**r,"json":parsed})

payload={"purpose":"Validate exact Charge+ public tariffs for Belgian TotalEnergies connectors using internal BeMo GUIDs","results":results}
(OUT/"chargeplus-tariff-guid-validation-2026-09-28.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"summary":[{"sample":x["target"]["sample"],"status":x["status"],"hasErrors":(x["json"] or {}).get("hasErrors") if isinstance(x["json"],dict) else None} for x in results]},ensure_ascii=False,indent=2))
