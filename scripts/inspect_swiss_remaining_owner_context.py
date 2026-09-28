#!/usr/bin/env python3
import gzip,json,urllib.request
from collections import defaultdict,Counter
from pathlib import Path
from datetime import datetime,timezone
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
TARGETS={"CH*AUTOSENSE","CH*AIL","CH*EVT","CH*DIE","CH*HER","CH*EBS","CH*CCC"}
req=urllib.request.Request(URL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
j=json.loads(raw.decode("utf-8"))
by=defaultdict(list)
def walk(x,owner=None,owner_name=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str) and x["OperatorID"].strip():
            owner=x["OperatorID"].strip();owner_name=x.get("OperatorName")
        eid=x.get("EvseID")
        if owner in TARGETS and isinstance(eid,str):
            by[owner].append({"record":x,"operatorName":owner_name})
        for v in x.values():walk(v,owner,owner_name)
    elif isinstance(x,list):
        for v in x:walk(v,owner,owner_name)
walk(j)
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"operators":{}}
for op in sorted(TARGETS):
    rows=[]; names=Counter(); accesses=Counter(); auth=Counter(); pays=Counter(); prefixes=Counter()
    for item in by.get(op,[]):
        d=item["record"]; eid=d.get("EvseID","")
        names[item.get("operatorName") or ""]+=1
        accesses[str(d.get("Accessibility"))]+=1
        auth[json.dumps(d.get("AuthenticationModes") or [],sort_keys=True,ensure_ascii=False)]+=1
        pays[json.dumps(d.get("PaymentOptions") or [],sort_keys=True,ensure_ascii=False)]+=1
        pref=eid.split("*E",1)[0] if "*E" in eid else eid[:12]
        prefixes[pref]+=1
        if len(rows)<100:
            rows.append({"evseId":eid,"operatorName":item.get("operatorName"),"accessibility":d.get("Accessibility"),
                         "auth":d.get("AuthenticationModes"),"paymentOptions":d.get("PaymentOptions"),
                         "address":d.get("Address"),"names":d.get("ChargingStationNames"),
                         "chargingFacilities":d.get("ChargingFacilities"),"plugs":d.get("Plugs"),
                         "stationId":d.get("ChargingStationId")})
    out["operators"][op]={"evseCount":len(by.get(op,[])),"operatorNames":names.most_common(),"accessibility":accesses.most_common(),
                          "authentication":auth.most_common(),"paymentOptions":pays.most_common(),"prefixes":prefixes.most_common(),"samples":rows}
Path("docs/switzerland-remaining-owner-context-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({op:{k:v for k,v in x.items() if k!="samples"} for op,x in out["operators"].items()},ensure_ascii=False,indent=2))
