#!/usr/bin/env python3
import json
from pathlib import Path
SRC=Path("docs/switzerland-ecarup-remaining-targeted-queries-2026-09-28.json")
x=json.loads(SRC.read_text(encoding="utf-8"))
out={"operators":{}}
def norm(s):
    return "".join(c for c in (s or "").upper() if c.isalnum())
for op,rows in (x.get("operators") or {}).items():
    exact=[]; near=[]; none=0
    for r in rows:
        eid=r.get("evseId")
        cs=[]
        for s in r.get("candidates") or []:
            public_priced=[c for c in s.get("connectors") or [] if c.get("accessType")==0 and isinstance(c.get("price"),dict)]
            matches=[c for c in s.get("connectors") or [] if norm(c.get("hubjectId"))==norm(eid)]
            if matches:
                exact.append({"evseId":eid,"distanceMeters":s.get("distanceMeters"),"stationId":s.get("stationId"),"name":s.get("name"),"operatorName":s.get("operatorName"),"connectors":matches})
            if (s.get("distanceMeters") or 99999)<=20 and public_priced:
                cs.append({"distanceMeters":s.get("distanceMeters"),"stationId":s.get("stationId"),"name":s.get("name"),"operatorName":s.get("operatorName"),"connectors":public_priced})
        if len(cs)==1:
            near.append({"evseId":eid,"candidate":cs[0]})
        if not r.get("candidates"): none+=1
    out["operators"][op]={
      "nationalRowCount":len(rows),"exactHubjectMatchCount":len(exact),
      "uniquePricedPublicCandidateWithin20mCount":len(near),"noCandidateCount":none,
      "exactHubjectMatches":exact,"nearCandidates":near[:200]
    }
Path("docs/switzerland-ecarup-remaining-targeted-summary-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({op:{k:v for k,v in d.items() if k not in ("exactHubjectMatches","nearCandidates")} for op,d in out["operators"].items()},ensure_ascii=False,indent=2))
