#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime,timezone

SRC=Path("docs/switzerland-iwb-owner-reconciliation-2026-09-28.json")
OUT=Path("data/switzerland/iwb-official-basel-overlay.json")
FINAL=Path("docs/switzerland-iwb-finalization-2026-09-28.json")
SOURCE="https://www.iwb.ch/servicecenter/oeffentliches-ladenetz/mobilitaet-tarife"
j=json.loads(SRC.read_text(encoding="utf-8"))
overlay=[]; remaining=[]
for r in j["classes"].get("public_unpriced",[]):
    city=(r.get("address") or {}).get("City")
    facilities=r.get("chargingFacilities") or []
    powers=[float(x["power"]) for x in facilities if x.get("power") is not None]
    types=[str(x.get("powertype","")).upper() for x in facilities]
    power=max(powers) if powers else None
    typ="DC" if any("DC" in t for t in types) else ("AC" if any("AC" in t for t in types) else None)
    tariff=None
    if city=="Basel" and typ=="AC":
        tariff={"pricePerKwh":0.48,"currency":"CHF","blockingFee":None,"category":"IWB Allmend Basel-Stadt AC"}
    elif city=="Basel" and typ=="DC" and power is not None and power<=50:
        tariff={"pricePerKwh":0.60,"currency":"CHF","blockingFee":{"graceMinutes":150,"pricePerMinute":0.15},"category":"IWB Allmend Basel-Stadt DC <=50 kW"}
    elif city=="Basel" and typ=="DC" and power is not None and 50<power<=150:
        tariff={"pricePerKwh":0.64,"currency":"CHF","blockingFee":{"graceMinutes":60,"pricePerMinute":0.25},"category":"IWB Allmend Basel-Stadt DC <=150 kW"}
    if tariff:
        overlay.append({"evseId":r["evseId"],"city":city,"street":(r.get("address") or {}).get("Street"),"powerKw":power,"energyType":typ,**tariff,"source":SOURCE})
    else:
        remaining.append(r["evseId"])
cc=j["classCounts"]
priced=cc.get("priced_exact",0)+len(overlay)
restricted=cc.get("restricted_no_auth",0)
unseen=cc.get("owner_not_seen_in_atlas",0)
unresolved=len(remaining)+unseen
now=datetime.now(timezone.utc).isoformat()
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps({"generatedAt":now,"operatorId":"CH*IWB","source":SOURCE,"overlayCount":len(overlay),"evses":overlay},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
final={"schemaVersion":1,"country":"CH","cpo":"IWB","operatorId":"CH*IWB","status":"complete" if unresolved==0 else "partial","updatedAt":now,
"nationalEvseCount":j["nationalOwnerEvseCount"],"pricedEvseCount":priced,"classifiedNoPublicDirectTariffCount":restricted,
"unresolvedEvseCount":unresolved,"remainingPublicUnpricedCount":len(remaining),"ownerNotSeenInAtlasCount":unseen,
"officialBaselOverlayCount":len(overlay),
"method":"Current national CH*IWB owner scope + exact direct tariff evidence + official IWB Allmend Basel-Stadt tariff for exact Basel public residuals + restricted/no-auth classification",
"policy":"Official Basel-Stadt tariff is applied only to public unpriced EVSEs whose current national city is exactly Basel and whose power/type fits a published IWB tariff band. No extrapolation to Riehen or other municipalities.",
"productionSources":["data/switzerland/iwb-direct-tariffs-second-pass.json",str(OUT)]}
FINAL.write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
print(json.dumps({"remainingPublicUnpricedEvseIds":remaining},ensure_ascii=False,indent=2))
