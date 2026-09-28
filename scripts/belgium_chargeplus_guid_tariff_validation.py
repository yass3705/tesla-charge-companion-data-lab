#!/usr/bin/env python3
import json, urllib.parse, urllib.request, urllib.error
from pathlib import Path

BASE="https://public.mycardprd.alzp.tgscloud.net/chargeplus-bff/v1/pois/tariff"
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)

cases=[
 {"chargePointId":"BE*TCB*E800372","connectorId":"986e2857-dd55-5739-872b-db252800bbf2","powerKw":300,"standard":"IEC_62196_T2_COMBO"},
 {"chargePointId":"BE*TCB*E800373","connectorId":"bf4a89e0-f525-56b1-b760-ba6f00a588f5","powerKw":300,"standard":"IEC_62196_T2_COMBO"},
 {"chargePointId":"BE*TCB*E800374","connectorId":"4b58689b-3f6e-5419-bee4-b414193bcaee","powerKw":100,"standard":"CHADEMO"},
]

def get(cid):
    url=BASE+"?"+urllib.parse.urlencode({"connectorId":cid})
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"tesla-charge-companion-data-lab/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            body=r.read().decode("utf-8","replace")
            return {"url":url,"status":r.status,"contentType":r.headers.get("content-type"),"body":body}
    except urllib.error.HTTPError as e:
        return {"url":url,"status":e.code,"contentType":e.headers.get("content-type"),"body":e.read().decode("utf-8","replace")}
    except Exception as e:
        return {"url":url,"status":0,"error":type(e).__name__+": "+str(e),"body":""}

results=[]
for case in cases:
    r=get(case["connectorId"])
    parsed=None
    try: parsed=json.loads(r.get("body") or "")
    except Exception: pass
    results.append({**case,**r,"json":parsed})

payload={
 "targetSite":{"name":"TotalEnergies Boom","napLocationId":"TotalEnergies-MOW-BOOM","coordinates":[51.099934,4.368176],"bemoPoiId":"BEMO-55e8f80cda"},
 "results":results,
 "notes":["Read-only validation of exact Charge+ connector GUIDs discovered from public POI details.","No tariff is written to canonical Belgium data by this probe."]
}
(OUT/"chargeplus-guid-tariff-validation-2026-09-28.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps([{
 "chargePointId":x["chargePointId"],"connectorId":x["connectorId"],"status":x["status"],
 "hasData":bool((x.get("json") or {}).get("data")),"hasErrors":(x.get("json") or {}).get("hasErrors"),
 "data":(x.get("json") or {}).get("data"),"errors":(x.get("json") or {}).get("errors")
} for x in results],ensure_ascii=False,indent=2))
