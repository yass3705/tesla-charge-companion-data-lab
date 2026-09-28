#!/usr/bin/env python3
import json, urllib.request, urllib.parse, urllib.error
from pathlib import Path
from datetime import datetime, timezone

BASE="https://api.eponet.io"
UA={"User-Agent":"Eponet/1.4.7 Android TCC-research","Accept":"application/json","Content-Type":"application/json"}
tests=[]
endpoints=[
 "ocpp/chargers/getmapchargers/",
 "ocpp/chargers/getmapchargerdetails/",
 "ocpp/rate/getrates/",
 "ocpp/chargers/getthirdpartymapchargers/",
 "ocpp/chargers/getchargerdetails",
 "portal/getmobileappsettings",
]
payloads=[
 None,
 {},
 {"latitude":46.818,"longitude":8.2275},
 {"lat":46.818,"lng":8.2275},
 {"Latitude":46.818,"Longitude":8.2275},
 {"north":47.9,"south":45.7,"east":10.6,"west":5.8},
 {"charger_ids":[]},
 {"charger_id":""},
 {"ChargerId":""},
]
def req(method,path,payload=None):
    url=BASE+"/"+path.lstrip("/")
    data=None if payload is None else json.dumps(payload).encode()
    headers=dict(UA)
    if method=="GET": headers.pop("Content-Type",None)
    r=urllib.request.Request(url,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(r,timeout=30) as x:
            raw=x.read(500000)
            return {"method":method,"path":path,"payload":payload,"status":x.status,"contentType":x.headers.get("content-type"),"headers":dict(x.headers),"body":raw.decode("utf-8","replace")[:200000]}
    except urllib.error.HTTPError as e:
        raw=e.read(500000)
        return {"method":method,"path":path,"payload":payload,"status":e.code,"contentType":e.headers.get("content-type"),"headers":dict(e.headers),"body":raw.decode("utf-8","replace")[:200000]}
    except Exception as e:
        return {"method":method,"path":path,"payload":payload,"error":type(e).__name__+": "+str(e)}

for ep in endpoints:
    tests.append(req("GET",ep))
    for p in payloads:
        tests.append(req("POST",ep,p))

out={"generatedAt":datetime.now(timezone.utc).isoformat(),"base":BASE,"tests":tests}
Path("docs/switzerland-eponet-go-api-probe-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
interesting=[t for t in tests if t.get("status") not in (404,) or t.get("error")]
print(json.dumps(interesting,ensure_ascii=False,indent=2)[:120000])
