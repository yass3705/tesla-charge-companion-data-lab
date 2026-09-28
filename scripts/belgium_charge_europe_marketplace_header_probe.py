#!/usr/bin/env python3
import json, urllib.parse, urllib.request, urllib.error
from pathlib import Path

BASE="https://prod.apix.alzp.tgscloud.net/evdc-bff-europe/v0.0.1"
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)
HEADERS={
 "Accept":"application/json",
 "User-Agent":"TotalEnergies-Charge-Europe-research/1.0",
 "x-apif-apikey":"marketplace-evp",
}
tests=[
 ("locations-country","/v3/infrastructure/locations",{"countryCode":"BE","pageNumber":"0","pageSize":"5"}),
 ("locations-near-boom","/v3/infrastructure/locations",{"latitude":"51.099934","longitude":"4.368176","pageNumber":"0","pageSize":"10"}),
 ("timestamp","/v2/infrastructure/locations/timestamp",{}),
]
def get(label,path,params):
    url=BASE+path+("?" + urllib.parse.urlencode(params) if params else "")
    req=urllib.request.Request(url,headers=HEADERS)
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            body=r.read().decode("utf-8","replace")
            try: data=json.loads(body)
            except Exception: data={"raw":body[:50000]}
            return {"label":label,"url":url,"status":r.status,"contentType":r.headers.get("content-type"),"json":data}
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace")
        try: data=json.loads(body)
        except Exception: data={"raw":body[:50000]}
        return {"label":label,"url":url,"status":e.code,"contentType":e.headers.get("content-type"),"json":data}
    except Exception as e:
        return {"label":label,"url":url,"status":0,"error":type(e).__name__+": "+str(e)}
res=[get(*t) for t in tests]
payload={
 "purpose":"Validate whether the embedded Charge Europe marketplace identifier is the public API key and inspect Belgium location price schema.",
 "headerValuePersisted":False,
 "results":res
}
(OUT/"charge-europe-marketplace-header-probe-2026-09-28.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps([{"label":x["label"],"status":x["status"],"keys":sorted(x.get("json",{}).keys()) if isinstance(x.get("json"),dict) else None} for x in res],ensure_ascii=False,indent=2))
