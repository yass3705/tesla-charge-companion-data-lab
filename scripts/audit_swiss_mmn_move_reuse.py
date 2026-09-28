#!/usr/bin/env python3
import json
from pathlib import Path
targets={"CH*MMN*E00160","CH*MMN*E00145","CH*MMN*E04456","CH*MMN*E04455","CH*MMN*E03226","CH*MMN*E01032"}
out={}
for p in ["data/switzerland/move-direct-tariffs.json","data/switzerland/move-direct-tariffs-second-pass.json"]:
    path=Path(p)
    raw=path.read_text(encoding="utf-8") if path.exists() else ""
    if not raw.strip():
        out[p]={"status":"empty_placeholder","size":path.stat().st_size if path.exists() else None,"hits":[]}
        continue
    try:
        x=json.loads(raw)
    except Exception as e:
        out[p]={"status":"invalid_json","error":type(e).__name__+": "+str(e),"size":len(raw),"hits":[]}
        continue
    hits=[]
    for s in x.get("stations",[]):
        ids=set(s.get("evseIds") or [])
        if ids & targets:
            hits.append({"stationId":s.get("stationId"),"name":s.get("name"),"address":s.get("address"),"evseIds":s.get("evseIds"),"chargePoints":s.get("chargePoints")})
    out[p]={"status":"parsed","summary":x.get("summary"),"hits":hits}
Path("docs/switzerland-mmn-move-reuse-audit-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
