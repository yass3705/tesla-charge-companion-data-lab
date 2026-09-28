#!/usr/bin/env python3
import json,re
from pathlib import Path
from collections import Counter,defaultdict

SRC=Path("data/belgium/additional/canonical/road-belgium-canonical-2026-09-29.json")
OUT=Path("reports/belgium/road"); OUT.mkdir(parents=True,exist_ok=True)
d=json.loads(SRC.read_text())
rows=[]; patterns=Counter(); byop=Counter()
for x in d.get("items") or []:
    eid=str(x.get("evseId") or "")
    if re.match(r"^[A-Z]{2}\*[A-Z0-9]+",eid,re.I): continue
    if "*" in eid: pat="starred-nonstandard"
    elif re.match(r"^[A-Z]{2}",eid,re.I): pat="country-prefixed-compact"
    elif eid: pat="opaque"
    else: pat="missing"
    patterns[pat]+=1; byop[str(x.get("operator") or "UNKNOWN")]+=1
    rows.append({
      "operator":x.get("operator"),"locationId":x.get("locationId"),
      "locationName":x.get("locationName"),"city":x.get("city"),"evseId":eid,
      "pattern":pat
    })
payload={"country":"BE","asOf":"2026-09-29","count":len(rows),"patterns":dict(patterns),"byOperator":byop.most_common(),"sample":rows[:150]}
(OUT/"road-nonstandard-evse-id-audit-2026-09-29.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(payload,ensure_ascii=False,indent=2))
