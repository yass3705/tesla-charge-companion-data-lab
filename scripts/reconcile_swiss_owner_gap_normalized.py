#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone

URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
OPS={"CH*REP":"rep","CH*911":"911","CH*CPI":"cpi","CH*505":"505"}
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}

req=urllib.request.Request(URL,headers=UA)
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
nat=json.loads(raw.decode())

owned={op:set() for op in OPS}
def walk(x,owner=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str): owner=x["OperatorID"]
        eid=x.get("EvseID")
        if owner in owned and isinstance(eid,str): owned[owner].add(eid)
        for v in x.values(): walk(v,owner)
    elif isinstance(x,list):
        for v in x: walk(v,owner)
walk(nat)
def norm(s): return "".join(c for c in (s or "").upper() if c.isalnum())

rows=[]
for op,slug in OPS.items():
    x=json.loads(Path(f"data/switzerland/{slug}-direct-tariffs-second-pass.json").read_text(encoding="utf-8"))
    atlas={}
    for st in x.get("stations",[]):
        for cp in st.get("chargePoints",[]):
            ids=(cp.get("chargePoint") or {}).get("evse_ids") or []
            for eid in ids:
                atlas.setdefault(eid,{"priced":False,"stationId":st.get("stationId"),"stationName":st.get("name")})
                if cp.get("directTariffs"): atlas[eid]["priced"]=True
    n_by=defaultdict(list); a_by=defaultdict(list)
    for eid in owned[op]: n_by[norm(eid)].append(eid)
    for eid in atlas: a_by[norm(eid)].append(eid)
    matched=[];amb=[]
    for k,nids in n_by.items():
        aids=a_by.get(k,[])
        if len(nids)==1 and len(aids)==1:
            matched.append({"nationalEvseId":nids[0],"atlasEvseId":aids[0],"priced":atlas[aids[0]]["priced"],
                            "stationId":atlas[aids[0]]["stationId"],"stationName":atlas[aids[0]]["stationName"]})
        elif aids:
            amb.append({"normalizedId":k,"nationalEvseIds":nids,"atlasEvseIds":aids})
    matched_n={m["nationalEvseId"] for m in matched}
    priced_n={m["nationalEvseId"] for m in matched if m["priced"]}
    rows.append({"operatorId":op,"nationalEvseCount":len(owned[op]),"normalizedUniqueMatchCount":len(matched),
                 "normalizedPricedCurrentEvseCount":len(priced_n),"normalizedMatchedUnpricedCount":len(matched)-len(priced_n),
                 "unmatchedCurrentEvseCount":len(owned[op]-matched_n),"ambiguousNormalizedCount":len(amb),
                 "matchedUnpriced":[m for m in matched if not m["priced"]],
                 "unmatchedCurrentEvseIds":sorted(owned[op]-matched_n),"ambiguities":amb})
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"normalization":"uppercase alphanumeric only; accepted only when 1:1 unique on both national and atlas sides","operators":rows}
Path("docs/switzerland-owner-gap-normalized-reconciliation-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps([{k:v for k,v in r.items() if k not in ("matchedUnpriced","unmatchedCurrentEvseIds","ambiguities")} for r in rows],ensure_ascii=False,indent=2))
