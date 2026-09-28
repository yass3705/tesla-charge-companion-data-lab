#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from collections import Counter,defaultdict

LOC=Path("data/belgium/additional/road-2026-09-28.json")
TAR=Path("data/belgium/additional/road-tariffs-2026-09-29.json")
OUT=Path("reports/belgium"); OUT.mkdir(parents=True,exist_ok=True)

locs=json.loads(LOC.read_text())
tariffs=json.loads(TAR.read_text())

tariff_by_id={}
for t in tariffs:
    if isinstance(t,dict) and t.get("id"):
        tariff_by_id[str(t["id"])]=t

evse_rows=[]
op_stats=defaultdict(lambda:Counter())
component_types=Counter()
currency_counts=Counter()
unmatched_tariff_ids=Counter()

for loc in locs if isinstance(locs,list) else []:
    op=loc.get("operator")
    if isinstance(op,dict): op=op.get("name") or op.get("id")
    op=str(op or "UNKNOWN")
    for ev in loc.get("evses") or []:
        if not isinstance(ev,dict): continue
        evse_id=ev.get("evse_id") or ev.get("uid") or ev.get("id")
        tids=[]
        connectors=ev.get("connectors") or []
        for c in connectors:
            if not isinstance(c,dict): continue
            for tid in c.get("tariff_ids") or []:
                if tid not in tids: tids.append(str(tid))
        matched=[tariff_by_id[x] for x in tids if x in tariff_by_id]
        for x in tids:
            if x not in tariff_by_id: unmatched_tariff_ids[x]+=1
        priced=bool(matched)
        op_stats[op]["evses"]+=1
        if priced: op_stats[op]["priced"]+=1
        else: op_stats[op]["unpriced"]+=1
        norm=[]
        for t in matched:
            cur=t.get("currency")
            if cur: currency_counts[str(cur)]+=1
            elems=[]
            for e in t.get("elements") or []:
                comps=[]
                for pc in e.get("price_components") or []:
                    typ=pc.get("type")
                    if typ: component_types[str(typ)]+=1
                    comps.append({
                      "type":typ,
                      "price":pc.get("price"),
                      "vat":pc.get("vat"),
                      "stepSize":pc.get("step_size")
                    })
                elems.append({"priceComponents":comps,"restrictions":e.get("restrictions")})
            norm.append({
              "id":t.get("id"),
              "currency":cur,
              "type":t.get("type"),
              "elements":elems,
              "lastUpdated":t.get("last_updated")
            })
        evse_rows.append({
          "operator":op,
          "locationId":loc.get("id"),
          "locationName":loc.get("name"),
          "city":loc.get("city"),
          "evseId":evse_id,
          "tariffIds":tids,
          "matchedTariffs":norm
        })

summary={
 "locations":len(locs) if isinstance(locs,list) else None,
 "evses":len(evse_rows),
 "tariffObjects":len(tariffs) if isinstance(tariffs,list) else None,
 "distinctTariffIds":len(tariff_by_id),
 "pricedEvses":sum(1 for x in evse_rows if x["matchedTariffs"]),
 "unpricedEvses":sum(1 for x in evse_rows if not x["matchedTariffs"]),
 "coveragePct":round(sum(1 for x in evse_rows if x["matchedTariffs"])/len(evse_rows)*100,2) if evse_rows else 0,
 "componentTypes":dict(component_types),
 "currencies":dict(currency_counts),
 "unmatchedTariffIds":len(unmatched_tariff_ids),
 "operators":[
   {"operator":op,"evses":s["evses"],"priced":s["priced"],"unpriced":s["unpriced"],
    "coveragePct":round(s["priced"]/s["evses"]*100,2) if s["evses"] else 0}
   for op,s in sorted(op_stats.items(),key=lambda kv:(-kv[1]["evses"],kv[0]))
 ]
}
(OUT/"belgium-road-tariff-coverage-2026-09-29.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
Path("data/operator_direct").mkdir(parents=True,exist_ok=True)
Path("data/operator_direct/road_belgium_tariffs_2026-09-29.json").write_text(json.dumps({
 "country":"BE","source":"Road public OCPI file","asOf":"2026-09-29",
 "sourceUrl":"https://roaming.road.io/files/9ef09c78-2666-418a-aa45-4f2261e2e305/tariffs.json",
 "items":evse_rows
},ensure_ascii=False,indent=2)+"\n")
print(json.dumps(summary,ensure_ascii=False,indent=2))
