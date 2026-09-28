#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
TARGETS={
 "CH*505":"50five",
 "CH*911":"Porsche Sales & Marketplace GmbH",
 "CH*BCK":"Backcharge GmbH",
}
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}
req=urllib.request.Request(URL,headers=UA)
with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
j=json.loads(raw.decode("utf-8"))
by={k:{} for k in TARGETS}
def walk(x,owner=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str) and x["OperatorID"].strip():owner=x["OperatorID"].strip()
        eid=x.get("EvseID")
        if owner in by and isinstance(eid,str) and eid.strip():by[owner][eid.strip()]=x
        for v in x.values():walk(v,owner)
    elif isinstance(x,list):
        for v in x:walk(v,owner)
walk(j)
now=datetime.now(timezone.utc).isoformat()
Path("data/switzerland").mkdir(parents=True,exist_ok=True);Path("docs").mkdir(exist_ok=True)
summary=[]
for op,name in TARGETS.items():
    rows=[];unresolved=[]
    for eid,d in sorted(by[op].items()):
        access=d.get("Accessibility")
        auth=d.get("AuthenticationModes") or []
        no_public=(access=="Restricted access" and not auth)
        row={"evseId":eid,"accessibility":access,"authenticationModes":auth,
             "classification":"no_public_direct_tariff" if no_public else "unresolved"}
        rows.append(row)
        if not no_public:
            unresolved.append({"evseId":eid,"accessibility":access,"authenticationModes":auth,
                               "reason":"not_explicitly_restricted_without_authentication"})
    classified=len(rows)-len(unresolved)
    status="complete" if rows and not unresolved else "partial"
    slug={"CH*505":"505","CH*911":"911","CH*BCK":"bck"}[op]
    policy="Classify no public direct tariff only where the current national record explicitly says Restricted access and exposes no authentication mode. No numeric tariff is inferred."
    payload={"schemaVersion":1,"country":"CH","cpo":name,"operatorId":op,"generatedAt":now,"source":URL,
             "counts":{"nationalEvseCount":len(rows),"classifiedNoPublicDirectTariffCount":classified,"unresolvedEvseCount":len(unresolved)},
             "policy":policy,"evses":rows,"unresolved":unresolved}
    final={"schemaVersion":1,"country":"CH","cpo":name,"operatorId":op,"status":status,"updatedAt":now,
           "nationalEvseCount":len(rows),"pricedEvseCount":0,"classifiedNoPublicDirectTariffCount":classified,
           "unresolvedEvseCount":len(unresolved),"method":"Current national owner scope + explicit restricted/no-auth classification",
           "policy":policy,"productionSource":f"data/switzerland/{slug}-restricted-direct-classification.json"}
    Path(f"data/switzerland/{slug}-restricted-direct-classification.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path(f"docs/switzerland-{slug}-finalization-2026-09-28.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary.append(final)
print(json.dumps(summary,ensure_ascii=False,indent=2))
