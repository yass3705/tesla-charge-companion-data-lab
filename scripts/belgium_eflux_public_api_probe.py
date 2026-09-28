#!/usr/bin/env python3
from __future__ import annotations
import json,urllib.parse,urllib.request,urllib.error
from pathlib import Path

OUT=Path("reports/belgium/road"); OUT.mkdir(parents=True,exist_ok=True)
BASE="https://api.e-flux.nl"
KNOWN_EVSE="BE*EFL*EV*0080612*C1"

tests=[
 {"name":"map-config","method":"GET","path":"/1/map/config"},
 {"name":"map-locations-empty","method":"GET","path":"/1/map/locations"},
 {"name":"map-locations-belgium","method":"GET","path":"/1/map/locations","query":{"latitude":"50.8503","longitude":"4.3517","radius":"50000"}},
 {"name":"search-fast-empty","method":"GET","path":"/2/locations/msp/search/fast"},
 {"name":"search-fast-evse","method":"GET","path":"/2/locations/msp/search/fast","query":{"query":KNOWN_EVSE}},
]

def call(t):
    url=BASE+t["path"]
    if t.get("query"):
        url+="?"+urllib.parse.urlencode(t["query"])
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"TCC-EFlux-public-probe/1.0"},method=t["method"])
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            body=r.read().decode("utf-8","replace")
            return r.status,dict(r.headers),body
    except urllib.error.HTTPError as e:
        return e.code,dict(e.headers),e.read().decode("utf-8","replace")
    except Exception as e:
        return 0,{},type(e).__name__+": "+str(e)

out=[]
for t in tests:
    st,h,b=call(t)
    rec={"name":t["name"],"method":t["method"],"path":t["path"],"status":st,"contentType":h.get("Content-Type") or h.get("content-type"),"bodyLength":len(b)}
    # Persist only structural/sample metadata, not any credential-like response values.
    try:
        obj=json.loads(b)
        if isinstance(obj,dict):
            rec["jsonKeys"]=sorted(obj.keys())
            for k in ("message","error","status","code","detail"):
                v=obj.get(k)
                if isinstance(v,(str,int,float,bool)) or v is None:
                    rec[k]=v
            # if clearly public location data, summarize only
            for k in ("data","results","locations"):
                v=obj.get(k)
                if isinstance(v,list):
                    rec[k+"Count"]=len(v)
                    if v and isinstance(v[0],dict): rec[k+"ItemKeys"]=sorted(v[0].keys())
        elif isinstance(obj,list):
            rec["listCount"]=len(obj)
            if obj and isinstance(obj[0],dict): rec["itemKeys"]=sorted(obj[0].keys())
    except Exception:
        rec["bodyPrefix"]=b[:300]
    out.append(rec)

payload={"country":"BE","asOf":"2026-09-29","scope":"unauthenticated read-only public API probe","base":BASE,"tests":out,
        "policy":{"credentialsUsed":False,"authenticationBypassAttempted":False,"readOnly":True}}
(OUT/"eflux-public-api-probe-2026-09-29.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(payload,ensure_ascii=False,indent=2))
