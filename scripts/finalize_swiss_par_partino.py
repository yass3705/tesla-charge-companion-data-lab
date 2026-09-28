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
    explicitly_free=(access=="Free publicly accessible" and not auth)
    classification="no_public_direct_tariff" if no_public else ("free_public_charging" if explicitly_free else "unresolved")
    rows.append({"evseId":eid,"accessibility":access,"authenticationModes":auth,
                 "classification":classification,"pricePerKwhCHF":0.0 if explicitly_free else None})
    if not no_public and not explicitly_free:
        unresolved.append({"evseId":eid,"accessibility":access,"authenticationModes":auth,
                           "reason":"not_explicitly_restricted_without_authentication_or_free_public"})
now=datetime.now(timezone.utc).isoformat()
no_public_count=sum(1 for x in rows if x["classification"]=="no_public_direct_tariff")
free_count=sum(1 for x in rows if x["classification"]=="free_public_charging")
classified=no_public_count+free_count; status="complete" if rows and not unresolved else "partial"
policy="Classify no public direct tariff only where the current national record explicitly says Restricted access with no authentication. Classify CHF 0/kWh only where the current national record explicitly says Free publicly accessible with no authentication. Otherwise fail closed."
payload={"schemaVersion":1,"country":"CH","cpo":NAME,"operatorId":PREFIX,"generatedAt":now,"source":URL,
         "counts":{"nationalEvseCount":len(rows),"classifiedNoPublicDirectTariffCount":no_public_count,"freePublicEvseCount":free_count,"unresolvedEvseCount":len(unresolved)},
         "policy":policy,"evses":rows,"unresolved":unresolved}
final={"schemaVersion":1,"country":"CH","cpo":NAME,"operatorId":PREFIX,"status":status,"updatedAt":now,
       "nationalEvseCount":len(rows),"pricedEvseCount":free_count,"classifiedNoPublicDirectTariffCount":no_public_count,"freePublicEvseCount":free_count,
       "unresolvedEvseCount":len(unresolved),"method":"Current national owner scope + explicit restricted/no-auth classification",
       "policy":policy,"productionSource":"data/switzerland/par-partino-restricted-direct-classification.json"}
Path("data/switzerland").mkdir(parents=True,exist_ok=True);Path("docs").mkdir(exist_ok=True)
Path("data/switzerland/par-partino-restricted-direct-classification.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
Path("docs/switzerland-par-finalization-2026-09-28.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(final,ensure_ascii=False,indent=2))
