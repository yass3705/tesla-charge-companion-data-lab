#!/usr/bin/env python3
import json,re
from pathlib import Path
from collections import Counter,defaultdict

SRC=Path("data/belgium/additional/canonical/road-belgium-canonical-2026-09-29.json")
OUT=Path("reports/belgium/road"); OUT.mkdir(parents=True,exist_ok=True)
d=json.loads(SRC.read_text())
prefixes=Counter(); byop=defaultdict(Counter); counts=Counter()
for x in d.get("items") or []:
    op=str(x.get("operator") or "UNKNOWN")
    eid=str(x.get("evseId") or "")
    m=re.match(r"^([A-Z]{2})\*([A-Z0-9]+)",eid,re.I)
    pref=(m.group(1)+"*"+m.group(2)).upper() if m else "OTHER"
    prefixes[pref]+=1; byop[op][pref]+=1; counts[op]+=1

payload={
 "country":"BE","asOf":"2026-09-29","source":"Road canonical inventory",
 "evseRows":sum(prefixes.values()),
 "prefixes":prefixes.most_common(),
 "operators":[
   {"name":op,"evses":counts[op],"prefixes":byop[op].most_common()}
   for op in sorted(counts,key=lambda x:(-counts[x],x))
 ],
 "familyAssessment":{
   "allBeEfl":sum(v for k,v in prefixes.items() if k=="BE*EFL")==sum(prefixes.values()),
   "dominantPrefix":prefixes.most_common(1)[0][0] if prefixes else None,
   "note":"Operator labels are treated as Road/E-Flux managed sub-networks unless a distinct CPO party identifier is proven."
 }
}
(OUT/"road-operator-family-audit-2026-09-29.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(payload,ensure_ascii=False,indent=2))
