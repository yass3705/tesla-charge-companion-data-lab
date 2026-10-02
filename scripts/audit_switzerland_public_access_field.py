#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path
p=Path("data/national/switzerland_public_charging_v9.json")
d=json.loads(p.read_text(encoding="utf-8"))
c=Counter(str(x.get("accessibility") or "MISSING") for x in d.get("evses",[]))
r={"country":"CH","nationalEvseCount":len(d.get("evses",[])),"accessibilityCounts":dict(c),"nonDestructive":True}
Path("docs/switzerland-public-access-field-audit-2026-10-03.json").write_text(json.dumps(r,indent=2)+"\n")
print(json.dumps(r,indent=2))
