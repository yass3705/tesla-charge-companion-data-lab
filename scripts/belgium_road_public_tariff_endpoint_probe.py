#!/usr/bin/env python3
import json,urllib.request,urllib.error
from pathlib import Path

BASE="https://roaming.road.io/files/9ef09c78-2666-418a-aa45-4f2261e2e305"
CANDS=[
 "tariffs.json?force=true",
 "tariffs.json",
 "2.2.1/tariffs.json?force=true",
 "ocpi/tariffs.json?force=true",
 "locations.json?force=true"
]
OUT=Path("reports/belgium"); OUT.mkdir(parents=True,exist_ok=True)
results=[]
for rel in CANDS:
    url=BASE+"/"+rel
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"TCC-Road-public-tariff-probe/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=60) as r:
            body=r.read()
            rec={"url":url,"status":r.status,"contentType":r.headers.get("content-type"),"bytes":len(body)}
            if "json" in (rec["contentType"] or "").lower() or body[:1] in (b"[",b"{"):
                try:
                    obj=json.loads(body)
                    rec["jsonType"]=type(obj).__name__
                    rec["topLevelCount"]=len(obj) if hasattr(obj,"__len__") else None
                    if "tariffs" in rel and r.status==200:
                        Path("data/belgium/additional/road-tariffs-2026-09-29.json").write_text(
                            json.dumps(obj,ensure_ascii=False,separators=(",",":"))+"\n"
                        )
                        rec["snapshotPath"]="data/belgium/additional/road-tariffs-2026-09-29.json"
                except Exception as e:
                    rec["parseError"]=type(e).__name__+": "+str(e)
            results.append(rec)
    except urllib.error.HTTPError as e:
        results.append({"url":url,"status":e.code,"contentType":e.headers.get("content-type"),"bytes":len(e.read())})
    except Exception as e:
        results.append({"url":url,"status":0,"error":type(e).__name__+": "+str(e)})

payload={"country":"BE","asOf":"2026-09-29","source":"Road public files","results":results}
(OUT/"belgium-road-public-tariff-endpoint-probe-2026-09-29.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(payload,ensure_ascii=False,indent=2))
