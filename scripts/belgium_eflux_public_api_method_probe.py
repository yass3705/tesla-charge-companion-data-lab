#!/usr/bin/env python3
from __future__ import annotations
import json,urllib.request,urllib.error
from pathlib import Path

OUT=Path("reports/belgium/road"); OUT.mkdir(parents=True,exist_ok=True)
BASE="https://api.e-flux.nl"

cases=[
 ("map-locations-options","OPTIONS","/1/map/locations",None),
 ("map-locations-post-empty","POST","/1/map/locations",{}),
 ("map-locations-post-belgium","POST","/1/map/locations",{"north":51.6,"south":49.4,"east":6.5,"west":2.5,"zoom":8}),
 ("search-fast-options","OPTIONS","/2/locations/msp/search/fast",None),
 ("search-fast-post-empty","POST","/2/locations/msp/search/fast",{}),
 ("search-fast-post-evse","POST","/2/locations/msp/search/fast",{"query":"BE*EFL*EV*0080612*C1"}),
]

def call(method,path,payload):
    data=None if payload is None else json.dumps(payload).encode()
    headers={"Accept":"application/json","User-Agent":"TCC-EFlux-public-method-probe/1.0"}
    if data is not None: headers["Content-Type"]="application/json"
    req=urllib.request.Request(BASE+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            body=r.read().decode("utf-8","replace")
            return getattr(r,"status",None),dict(r.headers),body
    except urllib.error.HTTPError as e:
        return e.code,dict(e.headers),e.read().decode("utf-8","replace")
    except Exception as e:
        return 0,{},type(e).__name__+": "+str(e)

def summarize(body):
    try:
        obj=json.loads(body)
    except:
        return {"bodyPrefix":body[:500]}
    if isinstance(obj,dict):
        out={"keys":sorted(obj.keys())}
        for k in ("error","message","code","detail","status"):
            if k in obj:
                v=obj[k]
                if isinstance(v,(str,int,float,bool)) or v is None: out[k]=v
                elif isinstance(v,dict):
                    out[k]={kk:vv for kk,vv in v.items() if isinstance(vv,(str,int,float,bool,type(None)))}
        for k,v in obj.items():
            if isinstance(v,list):
                out[k+"Count"]=len(v)
                if v and isinstance(v[0],dict):out[k+"ItemKeys"]=sorted(v[0].keys())
        return out
    if isinstance(obj,list):
        return {"listCount":len(obj),"itemKeys":sorted(obj[0].keys()) if obj and isinstance(obj[0],dict) else None}
    return {"type":type(obj).__name__}

tests=[]
for name,method,path,payload in cases:
    st,h,b=call(method,path,payload)
    tests.append({
      "name":name,"method":method,"path":path,"status":st,
      "allow":h.get("Allow") or h.get("allow"),
      "contentType":h.get("Content-Type") or h.get("content-type"),
      "response":summarize(b)
    })
payload={"country":"BE","asOf":"2026-09-29","scope":"public unauthenticated route-method probe","tests":tests,
         "policy":{"credentialsUsed":False,"authenticationBypassAttempted":False,"readOnlyIntent":True}}
(OUT/"eflux-public-api-method-probe-2026-09-29.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(payload,ensure_ascii=False,indent=2))
