#!/usr/bin/env python3
from __future__ import annotations
import json, os, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

BASE="https://nap-be.eco-movement.com/datex2/v1/status/"
TOKEN=os.environ["BELGIUM_NAP_TOKEN"].strip()
SRC=Path("reports/belgium/totalenergies/profile-2026-09-28.json")
OUT=Path("reports/belgium/totalenergies/status-probe-2026-09-28.json")
profile=json.loads(SRC.read_text(encoding="utf-8"))
sample=profile.get("representativeMissingSample") or []
results=[]

for i,row in enumerate(sample):
    ids=row.get("externalIdentifiers") or []
    evse_id=ids[0] if ids else None
    result={
      "evseId":evse_id,"internalEvseId":row.get("evseId"),"locationId":row.get("locationId"),
      "brand":row.get("brand"),"city":row.get("city"),"powerW":row.get("powerW"),"currentType":row.get("currentType")
    }
    if not evse_id:
        result["error"]="missing external id"; results.append(result); continue
    if i: time.sleep(11)
    url=BASE+urllib.parse.quote(evse_id,safe="")
    req=urllib.request.Request(url,headers={
      "Authorization":f"Bearer {TOKEN}","Accept":"application/json",
      "User-Agent":"tesla-charge-companion-data-lab/1.0"
    })
    try:
        with urllib.request.urlopen(req,timeout=60) as resp:
            body=json.loads(resp.read())
            result["httpStatus"]=resp.status
            result["body"]=body
            s=json.dumps(body)
            result["hasEnergyRateUpdate"]="energyRateUpdate" in s
            result["hasEnergyPrice"]="energyPrice" in s
            result["statusValues"]=[]
            def walk(x):
                if isinstance(x,dict):
                    if "status" in x and isinstance(x["status"],dict) and "value" in x["status"]:
                        result["statusValues"].append(x["status"]["value"])
                    for v in x.values(): walk(v)
                elif isinstance(x,list):
                    for v in x: walk(v)
            walk(body)
    except urllib.error.HTTPError as e:
        result["httpStatus"]=e.code
        result["errorBody"]=e.read().decode("utf-8","replace")[:1000]
    except Exception as e:
        result["error"]=type(e).__name__+": "+str(e)
    results.append(result)

summary={
 "requested":len(sample),
 "http200":sum(1 for x in results if x.get("httpStatus")==200),
 "withEnergyRateUpdate":sum(1 for x in results if x.get("hasEnergyRateUpdate")),
 "withEnergyPrice":sum(1 for x in results if x.get("hasEnergyPrice")),
 "results":results
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in summary.items() if k!="results"},ensure_ascii=False,indent=2))
