#!/usr/bin/env python3
import json,re
from pathlib import Path
from collections import Counter,defaultdict

SRC=Path("data/belgium/additional/canonical/road-belgium-canonical-2026-09-29.json")
OUT=Path("reports/belgium/belgium-road-operator-samples-2026-09-29.json")
d=json.loads(SRC.read_text())
items=d.get("items") or []
by=defaultdict(list); keys=Counter(); connkeys=Counter()
for x in items:
    by[str(x.get("operator") or "UNKNOWN")].append(x)
    keys.update(x.keys())
    for c in x.get("connectors") or []:
        if isinstance(c,dict): connkeys.update(c.keys())
payload={
 "country":"BE","asOf":"2026-09-29",
 "topLevelKeys":keys.most_common(),
 "connectorKeys":connkeys.most_common(),
 "operators":{}
}
for op,rows in sorted(by.items(),key=lambda kv:-len(kv[1])):
    payload["operators"][op]={
      "evses":len(rows),
      "sample":[{
        "evseId":r.get("evseId"),
        "locationId":r.get("locationId"),
        "locationName":r.get("locationName"),
        "city":r.get("city"),
        "access":r.get("access"),
        "connectors":r.get("connectors")
      } for r in rows[:8]]
    }
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({
 "operators":[[op,v["evses"]] for op,v in list(payload["operators"].items())[:20]],
 "topLevelKeys":payload["topLevelKeys"],
 "connectorKeys":payload["connectorKeys"]
},ensure_ascii=False,indent=2))
