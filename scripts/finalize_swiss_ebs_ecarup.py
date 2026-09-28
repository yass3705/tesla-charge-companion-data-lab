#!/usr/bin/env python3
import json,math
from pathlib import Path
from datetime import datetime,timezone
SRC=Path("docs/switzerland-ecarup-targeted-national-queries-2026-09-28.json")
OUT=Path("data/switzerland/ebs-ecarup-direct-tariffs.json")
FINAL=Path("docs/switzerland-ebs-finalization-2026-09-28.json")
OP="CH*EBS";NAME="EBS / ebs Energie AG"
x=json.loads(SRC.read_text(encoding="utf-8"))
rows=(x.get("operators") or {}).get(OP) or []
resolved=[];unresolved=[]
for r in rows:
    same=[c for c in r.get("candidates") or [] if c.get("operatorName")=="ebs Energie AG" and c.get("distanceMeters") is not None and c["distanceMeters"]<=50]
    if not same:
        unresolved.append({"evseId":r.get("evseId"),"reason":"no_same_operator_ecarup_station_within_50m","address":r.get("address"),"geo":r.get("geo")});continue
    public=[]
    for s in same:
        for c in s.get("connectors") or []:
            p=c.get("price") or {}
            if c.get("accessType")==0 and p.get("EnergyPrice") is not None:
                public.append({"ecarupStationId":s.get("stationId"),"ecarupStationName":s.get("name"),"distanceMeters":s.get("distanceMeters"),
                               "maxPowerKw":(float(c["maxPowerW"])/1000 if isinstance(c.get("maxPowerW"),(int,float)) else None),
                               "energyPrice":p.get("EnergyPrice"),"parkingPrice":p.get("ParkingPrice"),"currency":p.get("Currency"),
                               "penaltyGracePeriodMinutes":p.get("PenaltyGracePeriodMinutes"),"penaltyPricePerMinute":p.get("PenaltyPricePerMinute"),
                               "penaltyMaxFee":p.get("PenaltyMaxFee")})
    prices={(p["energyPrice"],str(p["currency"]).upper(),p.get("parkingPrice")) for p in public}
    if not public or len(prices)!=1:
        unresolved.append({"evseId":r.get("evseId"),"reason":"same_operator_price_not_unique","publicCandidates":public});continue
    resolved.append({"evseId":r.get("evseId"),"nationalAddress":r.get("address"),"nationalFacilities":r.get("facilities"),
                     "tariff":{"energyPrice":next(iter(prices))[0],"currency":next(iter(prices))[1],"parkingPrice":next(iter(prices))[2]},
                     "matchedPublicConnectors":public})
now=datetime.now(timezone.utc).isoformat()
status="complete" if rows and len(resolved)==len(rows) else "partial"
policy="Only same-operator ebs Energie AG public eCarUp stations within 50 m of the current national record are accepted, and only when the explicit public connector price is unique. Missing Hofmatt/Mythenforum/Sahli records remain unresolved; no tariff extrapolation."
payload={"schemaVersion":1,"country":"CH","cpo":NAME,"operatorId":OP,"generatedAt":now,
         "source":"eCarUp public API discovered from user-supplied Android APK","counts":{"nationalEvseCount":len(rows),"pricedEvseCount":len(resolved),"unresolvedEvseCount":len(unresolved)},
         "policy":policy,"evses":resolved,"unresolved":unresolved}
final={"schemaVersion":1,"country":"CH","cpo":NAME,"operatorId":OP,"status":status,"updatedAt":now,
       "nationalEvseCount":len(rows),"pricedEvseCount":len(resolved),"unresolvedEvseCount":len(unresolved),
       "method":"Current national CH*EBS scope + exact nearby same-operator eCarUp public connector pricing","policy":policy,"productionSource":str(OUT)}
OUT.parent.mkdir(parents=True,exist_ok=True);FINAL.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
FINAL.write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
print(json.dumps(unresolved,ensure_ascii=False,indent=2))
