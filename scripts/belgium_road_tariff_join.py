#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from collections import Counter,defaultdict

INV=Path("data/belgium/additional/canonical/road-belgium-canonical-2026-09-29.json")
TAR=Path("data/belgium/additional/road-tariffs-2026-09-29.json")
OUT=Path("data/operator_direct/road_belgium_tariffs_2026-09-29.json")
REP=Path("reports/belgium/belgium-road-tariff-join-2026-09-29.json")

inv=json.loads(INV.read_text())
tariffs=json.loads(TAR.read_text())
byid=defaultdict(list)
for t in tariffs:
    tid=t.get("id")
    if tid is not None:
        byid[str(tid)].append(t)

matched=[]; missing=[]; ambiguous=[]
op_stats=defaultdict(lambda:{"evses":0,"matched":0,"missing":0,"ambiguous":0})
component_types=Counter(); currencies=Counter(); tariff_id_use=Counter()

for ev in inv.get("items") or []:
    op=str(ev.get("operator") or "UNKNOWN")
    op_stats[op]["evses"]+=1
    tids=[]
    for c in ev.get("connectors") or []:
        for tid in c.get("tariff_ids") or []:
            s=str(tid)
            if s not in tids: tids.append(s)
    hits=[]
    miss=[]
    for tid in tids:
        arr=byid.get(tid,[])
        tariff_id_use[tid]+=1
        if not arr:
            miss.append(tid)
        else:
            hits.extend(arr)
    # dedupe exact tariff records by id+party+country
    uniq={}
    for t in hits:
        key=(str(t.get("id")),str(t.get("country_code")),str(t.get("party_id")))
        uniq[key]=t
    hits=list(uniq.values())
    if hits:
        op_stats[op]["matched"]+=1
        if len(hits)>1:
            op_stats[op]["ambiguous"]+=1
            ambiguous.append({"operator":op,"evseId":ev.get("evseId"),"tariffIds":tids,"matchCount":len(hits)})
        for t in hits:
            if t.get("currency"): currencies[str(t["currency"])]+=1
            for el in t.get("elements") or []:
                for pc in el.get("price_components") or []:
                    typ=pc.get("type")
                    if typ: component_types[str(typ)]+=1
        matched.append({
          "operator":op,
          "locationId":ev.get("locationId"),
          "locationName":ev.get("locationName"),
          "city":ev.get("city"),
          "evseId":ev.get("evseId"),
          "tariffIds":tids,
          "tariffs":hits
        })
    else:
        op_stats[op]["missing"]+=1
        missing.append({
          "operator":op,"locationId":ev.get("locationId"),"locationName":ev.get("locationName"),
          "city":ev.get("city"),"evseId":ev.get("evseId"),"tariffIds":tids
        })

payload={
  "country":"BE","source":"Road public OCPI-style files","asOf":"2026-09-29",
  "inventoryEvseRows":len(inv.get("items") or []),
  "tariffObjects":len(tariffs),
  "matchedEvses":len(matched),
  "missingEvses":len(missing),
  "ambiguousEvses":len(ambiguous),
  "entries":matched,
  "missing":missing,
  "rules":[
    "Tariffs are joined only through connector tariff_ids from the same public Road dataset.",
    "Raw OCPI-style tariff objects are preserved verbatim; no price is inferred or flattened.",
    "Multiple matched tariff objects are retained rather than arbitrarily selecting one."
  ]
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n")
report={
  "country":"BE","asOf":"2026-09-29","phase":"road-tariff-join",
  "inventoryEvseRows":payload["inventoryEvseRows"],"tariffObjects":len(tariffs),
  "matchedEvses":len(matched),"missingEvses":len(missing),"ambiguousEvses":len(ambiguous),
  "coveragePct":round(len(matched)/(len(matched)+len(missing))*100,2) if matched or missing else 0,
  "operators":[
    {"operator":op,**s,"coveragePct":round(s["matched"]/s["evses"]*100,2) if s["evses"] else 0}
    for op,s in sorted(op_stats.items(),key=lambda kv:-kv[1]["evses"])
  ],
  "componentTypes":dict(component_types),
  "currencies":dict(currencies),
  "distinctTariffIdsReferenced":len(tariff_id_use),
  "distinctTariffIdsAvailable":len(byid),
  "missingSample":missing[:100],
  "ambiguousSample":ambiguous[:100]
}
REP.parent.mkdir(parents=True,exist_ok=True)
REP.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({
 "matchedEvses":len(matched),"missingEvses":len(missing),"ambiguousEvses":len(ambiguous),
 "coveragePct":report["coveragePct"],"operators":report["operators"],
 "componentTypes":report["componentTypes"],"currencies":report["currencies"]
},ensure_ascii=False,indent=2))
