#!/usr/bin/env python3
import json,urllib.request,time
from pathlib import Path
from collections import Counter,defaultdict

BASE="https://roaming.road.io/files/9ef09c78-2666-418a-aa45-4f2261e2e305"
OUT=Path("reports/belgium"); OUT.mkdir(parents=True,exist_ok=True)

def get(name):
    url=f"{BASE}/{name}.json?force=true"
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"TCC-Road-sync/1.0"})
    with urllib.request.urlopen(req,timeout=120) as r:
        return json.loads(r.read()),url

locs,lurl=get("locations")
time.sleep(2)
tars,turl=get("tariffs")
tmap={str(t.get("id")):t for t in tars if isinstance(t,dict) and t.get("id")}

op=defaultdict(lambda:Counter())
unmatched=Counter()
no_tid=[]
for loc in locs:
    oper=loc.get("operator")
    if isinstance(oper,dict): oper=oper.get("name") or oper.get("id")
    oper=str(oper or "UNKNOWN")
    for ev in loc.get("evses") or []:
        tids=[]
        for c in ev.get("connectors") or []:
            for tid in c.get("tariff_ids") or []:
                s=str(tid)
                if s not in tids: tids.append(s)
        op[oper]["evses"]+=1
        matched=[x for x in tids if x in tmap]
        if matched:
            op[oper]["priced"]+=1
        else:
            op[oper]["unpriced"]+=1
            if not tids:
                no_tid.append({
                  "operator":oper,"locationId":loc.get("id"),"locationName":loc.get("name"),
                  "evseId":ev.get("evse_id") or ev.get("uid") or ev.get("id")
                })
            for tid in tids:
                if tid not in tmap: unmatched[tid]+=1

report={
 "country":"BE","asOf":"2026-09-29","phase":"road-synchronized-tariff-refresh",
 "source":{"locations":lurl,"tariffs":turl},
 "locations":len(locs),"tariffs":len(tars),
 "evses":sum(s["evses"] for s in op.values()),
 "pricedEvses":sum(s["priced"] for s in op.values()),
 "unpricedEvses":sum(s["unpriced"] for s in op.values()),
 "distinctUnmatchedTariffIds":len(unmatched),
 "evsesWithoutAnyTariffId":len(no_tid),
 "noTariffIdItems":no_tid[:100],
 "operators":[
   {"operator":k,"evses":v["evses"],"priced":v["priced"],"unpriced":v["unpriced"],
    "coveragePct":round(v["priced"]/v["evses"]*100,2) if v["evses"] else 0}
   for k,v in sorted(op.items(),key=lambda kv:(-kv[1]["evses"],kv[0]))
 ]
}
(OUT/"belgium-road-synchronized-tariff-refresh-2026-09-29.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(report,ensure_ascii=False,indent=2))
