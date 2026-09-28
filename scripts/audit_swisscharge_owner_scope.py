#!/usr/bin/env python3
import gzip,json,urllib.request
from collections import Counter
from pathlib import Path
from datetime import datetime,timezone
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
req=urllib.request.Request(URL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
j=json.loads(raw.decode("utf-8"))
rows={}
def prefix(e):
    if "*E" in e:return e.split("*E",1)[0]
    return e[:20]
def walk(x,owner=None,owner_name=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str) and x["OperatorID"].strip():
            owner=x["OperatorID"].strip();owner_name=x.get("OperatorName")
        eid=x.get("EvseID")
        if owner=="CH*SUI" and isinstance(eid,str) and eid.strip():
            rows[eid.strip()]={"evseId":eid.strip(),"operatorName":owner_name,"stationId":x.get("ChargingStationId"),
                               "address":x.get("Address"),"accessibility":x.get("Accessibility"),
                               "authenticationModes":x.get("AuthenticationModes"),"paymentOptions":x.get("PaymentOptions")}
        for v in x.values():walk(v,owner,owner_name)
    elif isinstance(x,list):
        for v in x:walk(v,owner,owner_name)
walk(j)
pc=Counter(prefix(e) for e in rows)
non=[v for e,v in rows.items() if not e.upper().startswith("CH*SUI*E")]
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"ownerId":"CH*SUI","ownerEvseCount":len(rows),
     "prefixCounts":pc.most_common(),"nonCanonicalPrefixCount":len(non),"nonCanonicalPrefixEvses":non}
Path("docs/switzerland-swisscharge-owner-scope-audit-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"ownerEvseCount":len(rows),"prefixCounts":pc.most_common(),"nonCanonicalPrefixCount":len(non)},ensure_ascii=False,indent=2))
