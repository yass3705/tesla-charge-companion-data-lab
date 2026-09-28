#!/usr/bin/env python3
import gzip,json
from pathlib import Path
from collections import defaultdict

TARGETS={"Gabriels","Shell Recharge","IONITY","Sowalwatt","recticel","VIR"}
root=Path("data/belgium/pages")
outdir=Path("reports/belgium"); outdir.mkdir(parents=True,exist_ok=True)

def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)

# Reuse the broad field heuristics used by the Belgium extractors, but keep raw records.
records=[]
for fp in sorted(root.glob("nap-belgium-*.json.gz")):
    with gzip.open(fp,"rt",encoding="utf-8") as f:
        data=json.load(f)
    for d in walk(data):
        # candidate EVSE-like dict
        ext=d.get("externalIdentifiers") or d.get("externalIdentifier") or d.get("evseId") or d.get("evseID")
        prices=d.get("prices") or d.get("energyRates") or d.get("energyRate") or d.get("tariffs")
        # operator can be nested/nearby, so retain candidate and infer from strings
        s=json.dumps(d,ensure_ascii=False)
        target=next((t for t in TARGETS if t.lower() in s.lower()),None)
        if not target or not ext:
            continue
        # avoid giant location dicts that simply contain all nested EVSEs
        keys=set(d)
        evseish=bool(keys & {"connectors","status","evseId","evseID","externalIdentifiers","maximumPower","maxPower"})
        if not evseish: continue
        records.append({"target":target,"page":fp.name,"raw":d})

# Deduplicate by compact fingerprint and isolate unpriced candidates.
seen=set(); compact=[]
for r in records:
    raw=r["raw"]
    ident=raw.get("evseId") or raw.get("evseID") or raw.get("id") or raw.get("externalIdentifiers") or raw.get("externalIdentifier")
    k=(r["target"],json.dumps(ident,sort_keys=True,ensure_ascii=False),r["page"])
    if k in seen: continue
    seen.add(k)
    prices=raw.get("prices") or raw.get("energyRates") or raw.get("energyRate") or raw.get("tariffs") or []
    compact.append({
      "operator":r["target"],"page":r["page"],
      "id":raw.get("id"),"evseId":raw.get("evseId") or raw.get("evseID"),
      "externalIdentifiers":raw.get("externalIdentifiers") or raw.get("externalIdentifier"),
      "status":raw.get("status"),"prices":prices,
      "connectors":raw.get("connectors"),
      "rawKeys":sorted(raw.keys())
    })

summary=defaultdict(lambda:{"candidates":0,"unpriced":[]})
for r in compact:
    s=summary[r["operator"]]; s["candidates"]+=1
    if not r["prices"]: s["unpriced"].append(r)

payload={"targets":{}}
for op in sorted(TARGETS):
    un=summary[op]["unpriced"]
    payload["targets"][op]={"candidateRecords":summary[op]["candidates"],"unpricedCount":len(un),"unpriced":un[:200]}
(outdir/"belgium-residual-unpriced-detail-2026-09-28.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({k:{"candidateRecords":v["candidateRecords"],"unpricedCount":v["unpricedCount"]} for k,v in payload["targets"].items()},indent=2))
