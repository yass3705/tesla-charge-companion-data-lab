#!/usr/bin/env python3
import gzip,json,urllib.request,glob,os,re
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
            national.setdefault(v.split("*E",1)[0],set()).add(v)

def priced_ids(path):
    try:x=json.load(open(path,encoding="utf-8"))
    except:return None,set(),set()
    op=x.get("operatorId"); seen=set(); priced=set()
    for st in x.get("stations",[]):
        seen.update(st.get("evseIds") or [])
        for cp in st.get("chargePoints",[]):
            ids=(cp.get("chargePoint") or {}).get("evse_ids") or []
            if cp.get("directTariffs"): priced.update(ids)
    return op,seen,priced

byop={}
for p in glob.glob("data/switzerland/*-direct-tariffs.json")+glob.glob("data/switzerland/*-direct-tariffs-second-pass.json"):
    op,seen,priced=priced_ids(p)
    if not op or op not in national: continue
    e=byop.setdefault(op,{"files":[],"seen":set(),"priced":set()})
    e["files"].append(p);e["seen"].update(seen);e["priced"].update(priced)
rows=[]
for op,e in sorted(byop.items()):
    n=national[op]
    rows.append({
      "operatorId":op,"files":sorted(e["files"]),"nationalEvseCount":len(n),
      "seenCurrentEvseCount":len(n&e["seen"]),"pricedCurrentEvseCount":len(n&e["priced"]),
      "missingCurrentEvseCount":len(n-e["priced"]),"extraSeenVsNationalCount":len(e["seen"]-n),
      "coveragePct":round(100*len(n&e["priced"])/len(n),3) if n else 0,
      "status":"complete" if n and n<=e["priced"] else "partial",
      "missingCurrentEvseIds":sorted(n-e["priced"])
    })
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"source":URL,"operators":rows}
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-second-pass-national-reconciliation-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps([{k:v for k,v in x.items() if k!="missingCurrentEvseIds"} for x in rows],ensure_ascii=False,indent=2))
