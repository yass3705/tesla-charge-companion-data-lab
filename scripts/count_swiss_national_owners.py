#!/usr/bin/env python3
import gzip,json,urllib.request
from collections import defaultdict
from pathlib import Path
from datetime import datetime,timezone
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
req=urllib.request.Request(URL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
j=json.loads(raw.decode("utf-8"))
by=defaultdict(dict)
def walk(x,owner=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str) and x["OperatorID"].strip():owner=x["OperatorID"].strip()
        eid=x.get("EvseID")
        if owner and isinstance(eid,str) and eid.strip():by[owner][eid.strip()]=x
        for v in x.values():walk(v,owner)
    elif isinstance(x,list):
        for v in x:walk(v,owner)
walk(j)
rows=[]
for op,evs in sorted(by.items(),key=lambda kv:(-len(kv[1]),kv[0])):
    prefixes={}
    for eid in evs:
        pref=eid.split("*E",1)[0] if "*E" in eid else eid.split("*",2)[0]
        prefixes[pref]=prefixes.get(pref,0)+1
    stations={d.get("ChargingStationId") for d in evs.values() if d.get("ChargingStationId")}
    rows.append({"operatorId":op,"evseCount":len(evs),"chargingStationIdCount":len(stations),
                 "evsePrefixBreakdown":dict(sorted(prefixes.items(),key=lambda kv:(-kv[1],kv[0])))})
out={"schemaVersion":1,"country":"CH","generatedAt":datetime.now(timezone.utc).isoformat(),"source":URL,
     "operatorCount":len(rows),"evseCount":sum(x["evseCount"] for x in rows),"operators":rows,
     "policy":"OperatorID ownership from the national feed is authoritative; EVSE string prefixes are reported only as diagnostics and are not used to infer CPO ownership."}
Path("docs/switzerland-national-owner-counts-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
