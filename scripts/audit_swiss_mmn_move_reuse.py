#!/usr/bin/env python3
import json
from pathlib import Path
targets={"CH*MMN*E00160","CH*MMN*E00145","CH*MMN*E04456","CH*MMN*E04455","CH*MMN*E03226","CH*MMN*E01032"}
out={}
for p in ["data/switzerland/move-direct-tariffs.json","data/switzerland/move-direct-tariffs-second-pass.json"]:
    x=json.loads(Path(p).read_text(encoding="utf-8"))
    hits=[]
    for s in x.get("stations",[]):
        ids=set(s.get("evseIds") or [])
        if ids & targets:
            hits.append({"stationId":s.get("stationId"),"name":s.get("name"),"address":s.get("address"),"evseIds":s.get("evseIds"),"chargePoints":s.get("chargePoints")})
    out[p]={"summary":x.get("summary"),"hits":hits}
Path("docs/switzerland-mmn-move-reuse-audit-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out,ensure_ascii=False,indent=2))
