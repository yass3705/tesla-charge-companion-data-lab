#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime,timezone
DATA=Path("data/switzerland/plenitude-official-direct-tariffs.json")
FINAL=Path("docs/switzerland-plenitude-finalization-2026-09-28.json")
CTX=Path("docs/switzerland-plenitude-residual-national-context-2026-09-28.json")
d=json.loads(DATA.read_text(encoding="utf-8")); f=json.loads(FINAL.read_text(encoding="utf-8")); ctx=json.loads(CTX.read_text(encoding="utf-8"))
classified=[];still=[]
for u in d.get("unresolved",[]):
    eid=u.get("evseId"); rec=ctx.get(eid) or {}
    if rec.get("Accessibility")=="Restricted access" and not (rec.get("AuthenticationModes") or []):
        classified.append({"evseId":eid,"classification":"restricted_no_public_direct_tariff",
                           "accessibility":rec.get("Accessibility"),"authenticationModes":rec.get("AuthenticationModes"),
                           "chargingStationId":rec.get("ChargingStationId"),"address":rec.get("Address"),
                           "plugs":rec.get("Plugs"),"chargingFacilities":rec.get("ChargingFacilities"),
                           "evidence":"current Swiss national OICP record"})
    else: still.append(u)
d["unresolved"]=still;d["classifiedNoPublicDirectTariff"]=classified
d["counts"]["unresolvedEvseCount"]=len(still);d["counts"]["classifiedNoPublicDirectTariffCount"]=len(classified)
d["generatedAt"]=datetime.now(timezone.utc).isoformat()
d["policy"]="Apply official Switzerland Plenitude energy tariffs only where connector category is exactly known. Current national records explicitly marked Restricted access with no authentication modes are classified as no public direct tariff, not assigned a guessed price."
DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
f["updatedAt"]=d["generatedAt"];f["unresolvedEvseCount"]=len(still);f["classifiedNoPublicDirectTariffCount"]=len(classified)
f["status"]="complete" if f["pricedEvseCount"]+len(classified)==f["nationalEvseCount"] and not still else "partial"
f["method"]="Current national CH*PLN scope + official Plenitude Switzerland tariff tiers; exact connector metadata for priced EVSEs and explicit restricted/no-auth classification for non-public residuals"
f["policy"]=d["policy"]
FINAL.write_text(json.dumps(f,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(f,ensure_ascii=False,indent=2));print(json.dumps(classified,ensure_ascii=False,indent=2))
