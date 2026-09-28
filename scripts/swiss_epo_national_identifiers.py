#!/usr/bin/env python3
import json,urllib.request
from pathlib import Path
from datetime import datetime,timezone
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
req=urllib.request.Request(URL,headers={"User-Agent":"TCC-V9-Switzerland/1.0","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=120) as r:data=json.load(r)
rows=[]
def walk(x, owner=None):
 if isinstance(x,dict):
  own=owner
  if x.get("OperatorID"): own=x.get("OperatorID")
  if own=="CH*EPO" and x.get("EvseID"):
   rows.append({
    "evseId":x.get("EvseID"),"chargingStationId":x.get("ChargingStationId"),
    "chargingPoolId":x.get("ChargingPoolID"),"names":x.get("ChargingStationNames"),
    "address":x.get("Address"),"geo":x.get("GeoCoordinates"),
    "facilities":x.get("ChargingFacilities"),"plugs":x.get("Plugs"),
    "auth":x.get("AuthenticationModes"),"payment":x.get("PaymentOptions"),
    "accessibility":x.get("Accessibility"),"suboperator":x.get("SubOperatorName") or x.get("SuboperatorName"),
    "additionalInfo":x.get("AdditionalInfo")
   })
  for v in x.values():walk(v,own)
 elif isinstance(x,list):
  for v in x:walk(v,owner)
walk(data)
# unique evse
d={x["evseId"]:x for x in rows}; rows=list(d.values())
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"operatorId":"CH*EPO","count":len(rows),"rows":rows}
Path("docs/switzerland-epo-national-identifiers-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"count":len(rows),"sample":rows[:25]},ensure_ascii=False,indent=2))
