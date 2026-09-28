#!/usr/bin/env python3
import json, urllib.parse, urllib.request, urllib.error
from pathlib import Path

BASE="https://prod.apix.alzp.tgscloud.net/evdc-bff-europe/v0.0.1"
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)

tests=[
 ("locations-none","/v3/infrastructure/locations",{}),
 ("locations-country","/v3/infrastructure/locations",{"countryCode":"BE"}),
 ("locations-latlon","/v3/infrastructure/locations",{"latitude":"51.099934","longitude":"4.368176"}),
 ("locations-bbox","/v3/infrastructure/locations",{"minLatitude":"51.09","maxLatitude":"51.11","minLongitude":"4.35","maxLongitude":"4.39"}),
 ("locations-page","/v3/infrastructure/locations",{"pageNumber":"0","pageSize":"10","countryCode":"BE"}),
 ("timestamp","/v2/infrastructure/locations/timestamp",{}),
 ("status","/v2/infrastructure/locations/status",{}),
]
def get(path,params):
    url=BASE+path+("?" + urllib.parse.urlencode(params) if params else "")
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"tesla-charge-companion-data-lab/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            body=r.read().decode("utf-8","replace")
            return {"label":label,"url":url,"status":r.status,"contentType":r.headers.get("content-type"),"body":body[:50000]}
    except urllib.error.HTTPError as e:
        return {"label":label,"url":url,"status":e.code,"contentType":e.headers.get("content-type"),"body":e.read().decode("utf-8","replace")[:50000]}
    except Exception as e:
        return {"label":label,"url":url,"status":0,"error":type(e).__name__+": "+str(e)}
res=[]
for label,path,params in tests:
    res.append(get(path,params))
payload={"base":BASE,"results":res,"notes":["Read-only anonymous probe of routes found in current TotalEnergies Charge Europe app."]}
(OUT/"charge-europe-api-probe-2026-09-28.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps([{"label":x["label"],"status":x["status"],"body":x.get("body","")[:2000]} for x in res],ensure_ascii=False,indent=2))
