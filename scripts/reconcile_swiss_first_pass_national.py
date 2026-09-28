#!/usr/bin/env python3
import gzip,json,urllib.request,glob
from pathlib import Path
from datetime import datetime,timezone

URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
req=urllib.request.Request(URL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
nat=json.loads(raw.decode("utf-8"))

def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)

national={}
for d in walk(nat):
    for k,v in d.items():
        if isinstance(v,str) and "evse" in k.lower() and "*E" in v:
            op=v.split("*E",1)[0]
            national.setdefault(op,set()).add(v)

rows=[]
for fn in sorted(glob.glob("data/switzerland/*-direct-tariffs.json")):
    try: x=json.load(open(fn,encoding="utf-8"))
    except Exception: continue
    op=x.get("operatorId")
    if not op or op not in national: continue
    all_seen=set(); priced=set()
    for st in x.get("stations",[]):
        all_seen.update(st.get("evseIds") or [])
        for cp in st.get("chargePoints",[]):
            ids=(cp.get("chargePoint") or {}).get("evse_ids") or []
            if cp.get("directTariffs"):
                priced.update(ids)
    n=national[op]
    rows.append({
      "operatorId":op,"file":fn,
      "nationalEvseCount":len(n),
      "seenCurrentEvseCount":len(n & all_seen),
      "pricedCurrentEvseCount":len(n & priced),
      "missingCurrentEvseCount":len(n-priced),
      "extraSeenVsNationalCount":len(all_seen-n),
      "coveragePct":round(100*len(n&priced)/len(n),3) if n else 0,
      "status":"complete" if n and n <= priced else "partial",
      "missingCurrentEvseIds":sorted(n-priced)[:500]
    })

out={"generatedAt":datetime.now(timezone.utc).isoformat(),"source":URL,"operators":rows}
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-first-pass-national-reconciliation-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
