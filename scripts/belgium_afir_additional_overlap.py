#!/usr/bin/env python3
from __future__ import annotations
import gzip,json,re,xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter,defaultdict

NAP=Path("data/belgium/pages")
ROAD=Path("data/belgium/additional/road-2026-09-28.json")
INDIGO=Path("data/belgium/additional/indigo-2026-09-28.xml")
OUT=Path("reports/belgium"); OUT.mkdir(parents=True,exist_ok=True)

def norm_evse(x):
    if not x: return None
    s=str(x).strip().upper().replace(" ","")
    return s

# Canonical selected-CPO EVSE external ids.
nap_ids=set()
nap_ops=Counter()
for fp in NAP.glob("nap-belgium-*.json.gz"):
    with gzip.open(fp,"rt",encoding="utf-8") as f:
        can=json.load(f)
    for loc in can.get("locations") or []:
        op=str(loc.get("operator") or "UNKNOWN")
        for st in loc.get("stations") or []:
            for ev in st.get("evses") or []:
                for eid in ev.get("externalIdentifiers") or []:
                    n=norm_evse(eid)
                    if n:
                        nap_ids.add(n)
                        nap_ops[op]+=1

# Road: recursively find OCPI-ish location/EVSE structures.
road=json.loads(ROAD.read_text())
road_rows=[]
def walk_road(x,path=""):
    if isinstance(x,dict):
        low={str(k).lower():v for k,v in x.items()}
        evses=low.get("evses")
        coords=low.get("coordinates")
        if isinstance(evses,list) and (coords is not None or "country" in low or "city" in low):
            operator=low.get("operator") or low.get("cpo") or low.get("party_id") or low.get("partyid") or low.get("network")
            if isinstance(operator,dict):
                operator=operator.get("name") or operator.get("id")
            for ev in evses:
                if not isinstance(ev,dict): continue
                eids=[]
                for k in ("evse_id","evseid","uid","id"):
                    v=ev.get(k)
                    if isinstance(v,str): eids.append(v)
                ext=ev.get("external_identifiers") or ev.get("externalIdentifiers") or []
                if isinstance(ext,str): ext=[ext]
                if isinstance(ext,list): eids.extend(str(v) for v in ext if isinstance(v,(str,int)))
                for eid in eids:
                    n=norm_evse(eid)
                    if n and ("*" in n or re.match(r"^[A-Z]{2}[A-Z0-9]",n)):
                        road_rows.append({
                          "id":n,
                          "operator":operator,
                          "locationName":low.get("name"),
                          "city":low.get("city"),
                          "country":low.get("country"),
                          "locationId":low.get("id")
                        })
        for k,v in x.items(): walk_road(v,path+"/"+str(k))
    elif isinstance(x,list):
        for i,v in enumerate(x): walk_road(v,path+f"/{i}")
walk_road(road)

# fallback generic EVSE id extraction with nearby operator isn't reliable; summarize discovered structured rows only.
road_unique={}
for r in road_rows:
    road_unique.setdefault(r["id"],r)
road_ids=set(road_unique)
road_new=road_ids-nap_ids
road_overlap=road_ids&nap_ids

# Indigo XML: externalIdentifier on refillPoint objects.
tree=ET.parse(INDIGO); root=tree.getroot()
indigo_rows=[]
def local(tag): return tag.split("}")[-1]
for rp in root.iter():
    if local(rp.tag)!="refillPoint": continue
    eid=None
    for ch in rp.iter():
        if local(ch.tag)=="externalIdentifier" and ch.text and ch.text.strip():
            eid=norm_evse(ch.text); break
    if eid:
        indigo_rows.append({"id":eid})
indigo_ids={r["id"] for r in indigo_rows}
indigo_new=indigo_ids-nap_ids
indigo_overlap=indigo_ids&nap_ids

op_counts=Counter()
for eid in road_new:
    op=road_unique[eid].get("operator")
    op_counts[str(op or "UNKNOWN")]+=1

payload={
 "country":"BE","asOf":"2026-09-29","phase":"additional-source-overlap",
 "canonicalSelectedCpo":{"distinctExternalEvseIds":len(nap_ids)},
 "road":{
   "structuredDistinctEvseIds":len(road_ids),
   "overlapWithSelectedCpo":len(road_overlap),
   "netNewVsSelectedCpo":len(road_new),
   "netNewOperatorTokens":op_counts.most_common(),
   "netNewSample":[road_unique[x] for x in sorted(road_new)[:100]]
 },
 "indigo":{
   "distinctEvseIds":len(indigo_ids),
   "overlapWithSelectedCpo":len(indigo_overlap),
   "netNewVsSelectedCpo":len(indigo_new),
   "netNewSample":sorted(indigo_new)[:100]
 },
 "rules":[
   "Comparison uses normalized EVSE external identifiers only.",
   "Net-new means absent from the current Eco-Movement selected-CPO snapshot; it does not by itself prove public accessibility or tariff availability.",
   "No tariff is inferred."
 ]
}
(OUT/"belgium-afir-additional-overlap-2026-09-29.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({
 "nap":len(nap_ids),
 "road":{k:payload["road"][k] for k in ("structuredDistinctEvseIds","overlapWithSelectedCpo","netNewVsSelectedCpo")},
 "indigo":{k:payload["indigo"][k] for k in ("distinctEvseIds","overlapWithSelectedCpo","netNewVsSelectedCpo")},
 "roadTopNewOperators":payload["road"]["netNewOperatorTokens"][:20]
},ensure_ascii=False,indent=2))
