#!/usr/bin/env python3
import json,urllib.request,urllib.error
from pathlib import Path

BASE="https://roaming.road.io/files/9ef09c78-2666-418a-aa45-4f2261e2e305/"
CANDIDATES=[
 "tariffs.json?force=true",
 "tariff.json?force=true",
 "prices.json?force=true",
 "evses.json?force=true",
 "status.json?force=true"
]
OUT=Path("reports/belgium"); OUT.mkdir(parents=True,exist_ok=True)
results={}
for name in CANDIDATES:
    url=BASE+name
    req=urllib.request.Request(url,headers={"User-Agent":"TCC-Road-tariff-probe/1.0","Accept":"application/json,*/*"})
    try:
        with urllib.request.urlopen(req,timeout=90) as r:
            body=r.read()
            rec={"status":r.status,"contentType":r.headers.get("content-type"),"bytes":len(body)}
            try:
                obj=json.loads(body)
                rec["jsonType"]=type(obj).__name__
                if isinstance(obj,list):
                    rec["topCount"]=len(obj)
                    rec["sampleKeys"]=sorted(obj[0].keys()) if obj and isinstance(obj[0],dict) else []
                elif isinstance(obj,dict):
                    rec["topKeys"]=sorted(obj.keys())[:80]
                    # common wrappers
                    for k in ("data","tariffs","results","items"):
                        if isinstance(obj.get(k),list):
                            rec["wrappedCount"]=len(obj[k])
                            rec["wrappedKey"]=k
                            rec["sampleKeys"]=sorted(obj[k][0].keys()) if obj[k] and isinstance(obj[k][0],dict) else []
                            break
                if name.startswith("tariffs") and r.status==200:
                    p=Path("data/belgium/additional/road-tariffs-2026-09-29.json")
                    p.parent.mkdir(parents=True,exist_ok=True)
                    p.write_bytes(body)
                    rec["snapshotPath"]=str(p)
            except Exception as e:
                rec["jsonError"]=type(e).__name__+": "+str(e)
            results[name]=rec
    except urllib.error.HTTPError as e:
        results[name]={"status":e.code,"contentType":e.headers.get("content-type"),"bytes":len(e.read())}
    except Exception as e:
        results[name]={"status":0,"error":type(e).__name__+": "+str(e)}

payload={"country":"BE","asOf":"2026-09-29","sourceBase":BASE,"candidates":results}
(OUT/"belgium-road-sibling-endpoint-probe-2026-09-29.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(payload,ensure_ascii=False,indent=2))
