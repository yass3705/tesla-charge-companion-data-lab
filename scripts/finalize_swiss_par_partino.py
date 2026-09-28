#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
PREFIX="CH*PAR"
NAME="Partino Mobile Energie AG"
req=urllib.request.Request(URL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
j=json.loads(raw.decode("utf-8"))
owned={}
def walk(x,owner=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str) and x["OperatorID"].strip(): owner=x["OperatorID"].strip()
        eid=x.get("EvseID")
        if owner==PREFIX and isinstance(eid,str) and eid.strip(): owned[eid.strip()]=x
        for v in x.values(): walk(v,owner)
    elif isinstance(x,list):
        for v in x: walk(v,owner)
walk(j)
rows=[];unresolved=[]
for eid,d in sorted(owned.items()):
    access=d.get("Accessibility"); auth=d.get("AuthenticationModes") or []
    no_public=(access=="Restricted access" and not auth)
    rows.append({"evseId":eid,"accessibility":access,"authenticationModes":auth,
                 "classification":"no_public_direct_tariff" if no_public else "unresolved"})
    if not no_public:
        unresolved.append({"evseId":eid,"accessibility":access,"authenticationModes":auth,
                           "reason":"not_explicitly_restricted_without_authentication"})
now=datetime.now(timezone.utc).isoformat()
classified=len(rows)-len(unresolved); status="complete" if rows and not unresolved else "partial"
policy="Classify no public direct tariff only where the current national record explicitly says Restricted access and exposes no authentication mode. No numeric price is inferred."
payload={"schemaVersion":1,"country":"CH","cpo":NAME,"operatorId":PREFIX,"generatedAt":now,"source":URL,
         "counts":{"nationalEvseCount":len(rows),"classifiedNoPublicDirectTariffCount":classified,"unresolvedEvseCount":len(unresolved)},
         "policy":policy,"evses":rows,"unresolved":unresolved}
final={"schemaVersion":1,"country":"CH","cpo":NAME,"operatorId":PREFIX,"status":status,"updatedAt":now,
       "nationalEvseCount":len(rows),"pricedEvseCount":0,"classifiedNoPublicDirectTariffCount":classified,
       "unresolvedEvseCount":len(unresolved),"method":"Current national owner scope + explicit restricted/no-auth classification",
       "policy":policy,"productionSource":"data/switzerland/par-partino-restricted-direct-classification.json"}
Path("data/switzerland").mkdir(parents=True,exist_ok=True);Path("docs").mkdir(exist_ok=True)
Path("data/switzerland/par-partino-restricted-direct-classification.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
Path("docs/switzerland-par-finalization-2026-09-28.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(final,ensure_ascii=False,indent=2))
