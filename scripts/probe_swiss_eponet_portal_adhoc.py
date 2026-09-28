#!/usr/bin/env python3
import json, urllib.request, urllib.parse, urllib.error
from pathlib import Path
from datetime import datetime, timezone

BASES=["https://portal.eponet.ch/api.php","https://beta.eponet.ch/api.php"]
IDS=["CH*EPO*E0001697","CH*EPO*E0001727","CH*EPO*E0001813"]
UA={"User-Agent":"Eponet/1.4.7 Android TCC-research","Accept":"application/json,text/plain,*/*"}

queries=[
 {},
 {"charger_id":IDS[0]},
 {"chargerId":IDS[0]},
 {"id":IDS[0]},
 {"serial":IDS[0]},
 {"action":"getcharger","charger_id":IDS[0]},
 {"action":"getchargerdetails","charger_id":IDS[0]},
 {"action":"getrates","charger_id":IDS[0]},
 {"method":"getrates","charger_id":IDS[0]},
 {"api":"getrates","charger_id":IDS[0]},
 {"type":"charger","charger_id":IDS[0]},
]
posts=[
 {"charger_id":IDS[0]},
 {"chargerId":IDS[0]},
 {"action":"getcharger","charger_id":IDS[0]},
 {"action":"getchargerdetails","charger_id":IDS[0]},
 {"action":"getrates","charger_id":IDS[0]},
 {"method":"getrates","charger_id":IDS[0]},
 {"api":"getrates","charger_id":IDS[0]},
]
def call(url, method="GET", form=None):
    data=None
    headers=dict(UA)
    if form is not None:
        data=urllib.parse.urlencode(form).encode()
        headers["Content-Type"]="application/x-www-form-urlencoded"
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=25) as r:
            raw=r.read(500000)
            return {"url":url,"method":method,"form":form,"status":r.status,"finalUrl":r.geturl(),"contentType":r.headers.get("content-type"),"body":raw.decode("utf-8","replace")[:100000]}
    except urllib.error.HTTPError as e:
        raw=e.read(500000)
        return {"url":url,"method":method,"form":form,"status":e.code,"finalUrl":url,"contentType":e.headers.get("content-type"),"body":raw.decode("utf-8","replace")[:100000]}
    except Exception as e:
        return {"url":url,"method":method,"form":form,"error":type(e).__name__+": "+str(e)}

results=[]
for base in BASES:
    for q in queries:
        url=base
        if q: url += "?"+urllib.parse.urlencode(q)
        results.append(call(url))
    for p in posts:
        results.append(call(base,"POST",p))

# Also test browser-facing guessed paths, harmless GET only.
paths=[
 "https://portal.eponet.ch/adhoc",
 "https://portal.eponet.ch/adhoc/",
 "https://portal.eponet.ch/public-charging",
 "https://portal.eponet.ch/public_charging",
 "https://portal.eponet.ch/charger",
 "https://portal.eponet.ch/charger?charger_id="+urllib.parse.quote(IDS[0],safe=""),
 "https://portal.eponet.ch/?charger_id="+urllib.parse.quote(IDS[0],safe=""),
 "https://portal.eponet.ch/#charger_id="+urllib.parse.quote(IDS[0],safe=""),
 "https://www.eponet.info/adhoc_laden",
]
for u in paths: results.append(call(u))

out={"generatedAt":datetime.now(timezone.utc).isoformat(),"ids":IDS,"results":results}
Path("docs/switzerland-eponet-portal-adhoc-probe-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps([{k:v for k,v in r.items() if k!="body"}|{"bodyPreview":r.get("body","")[:3000]} for r in results],ensure_ascii=False,indent=2)[:120000])
