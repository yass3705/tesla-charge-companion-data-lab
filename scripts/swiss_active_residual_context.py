#!/usr/bin/env python3
import json, urllib.request, collections
from pathlib import Path
from datetime import datetime, timezone
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
OPS={"CH*CCI","CH*SUI","CH*EPO","CH*IWB","CH*SOC","CH*MMN","CH*EBS","CH*EVT","CH*DIE","CH*HER","CH*PAR","CH*ECU"}
req=urllib.request.Request(URL,headers={"User-Agent":"TCC-V9-Swiss-active-audit/1.0","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=120) as r: data=json.load(r)
rows={op:[] for op in OPS}
def walk(x, owner=None):
    if isinstance(x,dict):
        new_owner=owner
        oid=x.get("OperatorID")
        if oid in OPS: new_owner=oid
        eid=x.get("EvseID")
        if new_owner in OPS and eid:
            rows[new_owner].append({
              "evseId":eid,
              "accessibility":x.get("Accessibility"),
              "authenticationModes":x.get("AuthenticationModes"),
              "paymentOptions":x.get("PaymentOptions"),
              "address":x.get("Address"),
              "names":x.get("ChargingStationNames"),
              "facilities":x.get("ChargingFacilities")
            })
        for v in x.values(): walk(v,new_owner)
    elif isinstance(x,list):
        for v in x: walk(v,owner)
walk(data)
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"source":URL,"operators":{}}
for op,rs in rows.items():
    uniq={r["evseId"]:r for r in rs}
    rs=list(uniq.values())
    access=collections.Counter(str(r.get("accessibility")) for r in rs)
    auth=collections.Counter(json.dumps(r.get("authenticationModes"),sort_keys=True,ensure_ascii=False) for r in rs)
    pay=collections.Counter(json.dumps(r.get("paymentOptions"),sort_keys=True,ensure_ascii=False) for r in rs)
    restricted_no_auth=[r for r in rs if str(r.get("accessibility") or "").lower().startswith("restricted") and not (r.get("authenticationModes") or [])]
    public_direct=[r for r in rs if "publicly accessible" in str(r.get("accessibility") or "").lower() and ("Direct Payment" in (r.get("authenticationModes") or []) or "Direct" in (r.get("paymentOptions") or []))]
    out["operators"][op]={
      "evseCount":len(rs),
      "accessibilityCounts":dict(access),
      "authenticationCounts":dict(auth),
      "paymentOptionCounts":dict(pay),
      "restrictedNoAuthCount":len(restricted_no_auth),
      "publicDirectCapableCount":len(public_direct),
      "restrictedNoAuthEvseIds":[r["evseId"] for r in restricted_no_auth],
      "publicDirectCapableSample":public_direct[:30]
    }
Path("docs/switzerland-active-residual-context-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({op:{k:v for k,v in d.items() if k not in ("restrictedNoAuthEvseIds","publicDirectCapableSample")} for op,d in out["operators"].items()},ensure_ascii=False,indent=2))

# trigger
