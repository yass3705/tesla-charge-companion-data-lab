#!/usr/bin/env python3
from __future__ import annotations
import json,urllib.request,urllib.error
from pathlib import Path
from collections import defaultdict,Counter

BASE="https://roaming.road.io/files/9ef09c78-2666-418a-aa45-4f2261e2e305/"
OUTD=Path("data/belgium/additional"); OUTD.mkdir(parents=True,exist_ok=True)
REPD=Path("reports/belgium"); REPD.mkdir(parents=True,exist_ok=True)

def fetch(name):
    url=BASE+name+"?force=true"
    req=urllib.request.Request(url,headers={"User-Agent":"TCC-Road-atomic-refresh/1.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=180) as r:
        return json.loads(r.read())

locations=fetch("locations.json")
tariffs=fetch("tariffs.json")
(OUTD/"road-2026-09-29.json").write_text(json.dumps(locations,ensure_ascii=False,separators=(",",":"))+"\n")
(OUTD/"road-tariffs-2026-09-29.json").write_text(json.dumps(tariffs,ensure_ascii=False,separators=(",",":"))+"\n")

# Parse Road OCPI-like locations deterministically.
rows=[]
def walk(x):
    if isinstance(x,dict):
        low={str(k).lower():v for k,v in x.items()}
        evses=low.get("evses")
        if isinstance(evses,list) and any(k in low for k in ("coordinates","city","country","address")):
            op=low.get("operator") or low.get("cpo") or low.get("network") or low.get("party_id") or low.get("partyid")
            if isinstance(op,dict): op=op.get("name") or op.get("id")
            for ev in evses:
                if not isinstance(ev,dict): continue
                rows.append({
                  "operator":str(op or "UNKNOWN"),
                  "locationId":low.get("id"),
                  "locationName":low.get("name"),
                  "city":low.get("city"),
                  "country":low.get("country"),
                  "evseId":ev.get("evse_id") or ev.get("evseid") or ev.get("uid") or ev.get("id"),
                  "connectors":ev.get("connectors") or []
                })
        for v in x.values(): walk(v)
    elif isinstance(x,list):
        for v in x: walk(v)
walk(locations)

byid=defaultdict(list)
for t in tariffs:
    if t.get("id") is not None: byid[str(t["id"])].append(t)

ops=defaultdict(lambda:{"evses":0,"matched":0,"missing":0})
missing=[]; matched=0
for ev in rows:
    op=ev["operator"]; ops[op]["evses"]+=1
    tids=[]
    for c in ev.get("connectors") or []:
        for tid in c.get("tariff_ids") or []:
            if str(tid) not in tids: tids.append(str(tid))
    hits=sum((byid.get(tid,[]) for tid in tids),[])
    if hits:
        matched+=1; ops[op]["matched"]+=1
    else:
        ops[op]["missing"]+=1
        missing.append({"operator":op,"locationId":ev.get("locationId"),"locationName":ev.get("locationName"),"city":ev.get("city"),"evseId":ev.get("evseId"),"tariffIds":tids})

report={
 "country":"BE","asOf":"2026-09-29","phase":"road-atomic-refresh-validation",
 "freshLocationsObjects":len(locations) if isinstance(locations,list) else None,
 "freshTariffObjects":len(tariffs),
 "evseRows":len(rows),"matchedEvses":matched,"missingEvses":len(missing),
 "coveragePct":round(matched/len(rows)*100,2) if rows else 0,
 "operators":[
   {"operator":op,**s,"coveragePct":round(s["matched"]/s["evses"]*100,2) if s["evses"] else 0}
   for op,s in sorted(ops.items(),key=lambda kv:-kv[1]["evses"])
 ],
 "missingSample":missing[:200],
 "note":"Locations and tariffs were fetched sequentially in the same workflow with force=true to minimize snapshot skew."
}
(REPD/"belgium-road-atomic-refresh-validation-2026-09-29.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({k:report[k] for k in ("evseRows","freshTariffObjects","matchedEvses","missingEvses","coveragePct")},indent=2))
print(json.dumps(report["operators"],ensure_ascii=False,indent=2))
