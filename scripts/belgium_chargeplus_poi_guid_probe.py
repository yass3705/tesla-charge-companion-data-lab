#!/usr/bin/env python3
from __future__ import annotations
import json,urllib.parse,urllib.request,urllib.error
from pathlib import Path

OUT=Path("reports/belgium/totalenergies")
OUT.mkdir(parents=True,exist_ok=True)
BASE="https://public.mycardprd.alzp.tgscloud.net/chargeplus-bff/v2/pois"
samples=[
 {"name":"Braine-l'Alleud","lat":50.66876,"lon":4.384442,"radius":5000},
 {"name":"Boom","lat":51.099934,"lon":4.368176,"radius":5000},
 {"name":"Alken","lat":50.88475,"lon":5.299239,"radius":5000},
]

def get(params):
    url=BASE+"?"+urllib.parse.urlencode(params)
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
for s in samples:
    params={"latitude":s["lat"],"longitude":s["lon"],"poiType":2,"radius":s["radius"]}
    r=get(params)
    parsed=None
    try: parsed=json.loads(r.get("body",""))
    except Exception: pass
    results.append({"sample":s,**r,"json":parsed})

out={"purpose":"Resolve public Charge+ POI schema and BeMo connector GUIDs around known Belgian TotalEnergies stations","results":results}
(OUT/"chargeplus-poi-guid-probe-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"summary":[{"sample":x["sample"]["name"],"status":x["status"],"jsonType":type(x["json"]).__name__ if x["json"] is not None else None} for x in results]},ensure_ascii=False,indent=2))
