#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime,timezone

SRC=Path("docs/switzerland-small-cpo-national-context-2026-09-28.json")
OUT=Path("data/switzerland/ail-emoti-official-direct-tariffs.json")
FINAL=Path("docs/switzerland-ail-finalization-2026-09-28.json")
AIL_SOURCE="https://www.ail.ch/aziende/elettricita/prodotti/mobilita-elettrica.html"
PRICE_SOURCE="https://www.emoti.swiss/prezzi/"
j=json.loads(SRC.read_text(encoding="utf-8"))
rows=j["operators"]["CH*AIL"]
evses=[]; unresolved=[]
for r in rows:
    e=r["evse"]; fac=e.get("ChargingFacilities") or []
    powers=[float(x["power"]) for x in fac if x.get("power") is not None]
    p=max(powers) if powers else None
    if p is not None and p<=22:
        evses.append({
          "evseId":r["evseId"],"powerKw":p,"city":(e.get("Address") or {}).get("City"),"street":(e.get("Address") or {}).get("Street"),
          "nonMemberPricePerKwh":0.54,"memberPricePerKwh":0.39,"memberAnnualFeeChf":96.0,"currency":"CHF",
          "parkingPenaltyPolicy":"Location/time dependent; consult app. No fixed fee guessed.",
          "sources":[AIL_SOURCE,PRICE_SOURCE]
        })
    else:
        unresolved.append({"evseId":r["evseId"],"powerKw":p,"reason":"outside_published_emoti_le22_band"})
now=datetime.now(timezone.utc).isoformat()
payload={"schemaVersion":1,"country":"CH","cpo":"AIL / emotì","operatorId":"CH*AIL","generatedAt":now,
 "sources":{"network":AIL_SOURCE,"tariff":PRICE_SOURCE},
 "counts":{"nationalEvseCount":len(rows),"pricedEvseCount":len(evses),"unresolvedEvseCount":len(unresolved)},
 "policy":"AIL identifies emotì as its public/semi-public charging solution. Apply current emotì <=22 kW member/non-member energy prices only to current CH*AIL EVSEs whose national power is <=22 kW. Parking/penalty remains location/time-specific and is not guessed.",
 "evses":evses,"unresolved":unresolved}
OUT.parent.mkdir(parents=True,exist_ok=True); FINAL.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
final={"schemaVersion":1,"country":"CH","cpo":"AIL / emotì","operatorId":"CH*AIL","status":"complete" if not unresolved and rows else "partial","updatedAt":now,
 **payload["counts"],"method":"Current CH*AIL national scope + official AIL emotì network identification + current emotì <=22 kW tariffs",
 "policy":payload["policy"],"productionSource":str(OUT)}
FINAL.write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
