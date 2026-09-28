#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
OPS={"CH*REP":"rep","CH*911":"911","CH*CPI":"cpi","CH*505":"505"}
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}
req=urllib.request.Request(NATIONAL,headers=UA)
with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
nat=json.loads(raw.decode())

owned={op:set() for op in OPS}
def walk(x,owner=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str):owner=x["OperatorID"]
        eid=x.get("EvseID")
        if owner in owned and isinstance(eid,str):owned[owner].add(eid)
        for v in x.values():walk(v,owner)
    elif isinstance(x,list):
        for v in x:walk(v,owner)
walk(nat)

rows=[]
for op,slug in OPS.items():
    p=Path(f"data/switzerland/{slug}-direct-tariffs-second-pass.json")
    x=json.loads(p.read_text(encoding="utf-8"))
    seen=set();priced=set()
    for st in x.get("stations",[]):
        seen.update(st.get("evseIds") or [])
        for cp in st.get("chargePoints",[]):
            if cp.get("directTariffs"):
                priced.update((cp.get("chargePoint") or {}).get("evse_ids") or [])
    n=owned[op]
    rows.append({"operatorId":op,"nationalEvseCount":len(n),"atlasSeenEvseCount":len(seen),
                 "seenCurrentEvseCount":len(n&seen),"pricedCurrentEvseCount":len(n&priced),
                 "unpricedCurrentEvseCount":len(n-priced),"extraAtlasEvseCount":len(seen-n),
                 "unpricedCurrentEvseIds":sorted(n-priced),"extraAtlasEvseIds":sorted(seen-n)})
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"source":NATIONAL,"operators":rows}
Path("docs/switzerland-owner-gap-national-reconciliation-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(rows,ensure_ascii=False,indent=2))
