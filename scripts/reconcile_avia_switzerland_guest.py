#!/usr/bin/env python3
import json, gzip, urllib.request
from pathlib import Path
from datetime import datetime, timezone

NAT="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
GUEST=Path("data/switzerland/avia-guest-direct-tariffs.json")
OUT=Path("docs/switzerland-avia-guest-reconciliation-2026-09-29.json")

def norm(v):
    return ''.join(ch for ch in str(v or '').upper() if ch.isalnum())

req=urllib.request.Request(NAT,headers={"User-Agent":"TCC-V9-AVIA-Reconcile/1.0","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=120) as r:
    raw=r.read()
if raw[:2]==b"\x1f\x8b":
    raw=gzip.decompress(raw)
nat=json.loads(raw.decode("utf-8"))

national={}
def walk(x, owner=None, station=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str):
            owner=x.get("OperatorID")
        if isinstance(x.get("ChargingStationId"),str):
            station=x.get("ChargingStationId")
        eid=x.get("EvseID")
        if isinstance(eid,str) and owner=="CH*AVI":
            national[norm(eid)]={
                "evseId":eid,
                "stationId":station or x.get("ChargingStationId"),
                "accessibility":x.get("Accessibility"),
                "authenticationModes":x.get("AuthenticationModes"),
                "paymentOptions":x.get("PaymentOptions"),
            }
        for v in x.values():
            walk(v,owner,station)
    elif isinstance(x,list):
        for v in x:
            walk(v,owner,station)
walk(nat)

guest=json.loads(GUEST.read_text(encoding="utf-8"))
guest_rows=guest.get("connectors") or []
guest_by_norm={}
for row in guest_rows:
    eid=row.get("evseId")
    if isinstance(eid,str):
        guest_by_norm.setdefault(norm(eid),[]).append(row)

matched=sorted(set(national)&set(guest_by_norm))
missing=sorted(set(national)-set(guest_by_norm))
guest_only=sorted(set(guest_by_norm)-set(national))
national_stations={v.get("stationId") for v in national.values() if v.get("stationId")}
matched_stations={national[k].get("stationId") for k in matched if national[k].get("stationId")}
missing_stations=sorted(x for x in national_stations-matched_stations if x)

report={
  "schemaVersion":1,
  "country":"CH",
  "cpo":"AVIA VOLT",
  "operatorId":"CH*AVI",
  "generatedAt":datetime.now(timezone.utc).isoformat(),
  "nationalSource":NAT,
  "guestSource":str(GUEST),
  "policy":{"exactEvseMatch":True,"noTariffExtrapolation":True},
  "counts":{
    "nationalEvseCount":len(national),
    "nationalStationCount":len(national_stations),
    "guestPricedEvseCount":len(guest_by_norm),
    "guestPricedConnectorCount":len(guest_rows),
    "matchedNationalEvseCount":len(matched),
    "missingNationalEvseCount":len(missing),
    "guestOnlyEvseCount":len(guest_only),
    "matchedNationalStationCount":len(matched_stations),
    "missingNationalStationCount":len(missing_stations),
    "collectorFailures":len(guest.get("failures") or []),
    "collectorMapErrors":len(guest.get("mapErrors") or []),
  },
  "complete":len(missing)==0,
  "missingNationalEvses":[national[k] for k in missing],
  "missingNationalStationIds":missing_stations,
  "guestOnlyEvseIds":[(guest_by_norm[k][0].get("evseId")) for k in guest_only],
  "collectorFailures":guest.get("failures") or [],
  "collectorMapErrors":guest.get("mapErrors") or [],
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report["counts"],indent=2))
