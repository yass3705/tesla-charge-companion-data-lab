#!/usr/bin/env python3
import json
from pathlib import Path
SRC=Path("docs/switzerland-ecarup-soc-mmn-targeted-queries-2026-09-28.json")
x=json.loads(SRC.read_text(encoding="utf-8"))
def norm(s): return "".join(c for c in (s or "").upper() if c.isalnum())
out={"operators":{}}
for op,rows in (x.get("operators") or {}).items():
    exact=[]; near=[]; no=0
    for r in rows:
        eid=r.get("evseId"); cands=r.get("candidates") or []
        if not cands:no+=1
        priced20=[]
        for s in cands:
            for c in s.get("connectors") or []:
                if norm(c.get("hubjectId"))==norm(eid):
                    exact.append({"evseId":eid,"distanceMeters":s.get("distanceMeters"),"stationId":s.get("stationId"),"name":s.get("name"),"operatorName":s.get("operatorName"),"connector":c})
            if (s.get("distanceMeters") or 999999)<=20:
                pcs=[c for c in s.get("connectors") or [] if c.get("accessType")==0 and isinstance(c.get("price"),dict)]
                if pcs: priced20.append({"stationId":s.get("stationId"),"name":s.get("name"),"operatorName":s.get("operatorName"),"distanceMeters":s.get("distanceMeters"),"connectors":pcs})
        if len(priced20)==1:near.append({"evseId":eid,"candidate":priced20[0]})
    out["operators"][op]={"rowCount":len(rows),"exactHubjectMatchCount":len(exact),"uniquePricedWithin20mCount":len(near),"noCandidateCount":no,"exact":exact,"near":near}
Path("docs/switzerland-ecarup-soc-mmn-summary-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({op:{k:v for k,v in d.items() if k not in ("exact","near")} for op,d in out["operators"].items()},ensure_ascii=False,indent=2))
