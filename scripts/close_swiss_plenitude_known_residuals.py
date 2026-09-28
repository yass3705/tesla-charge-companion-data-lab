#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime,timezone

DATA=Path("data/switzerland/plenitude-official-direct-tariffs.json")
FINAL=Path("docs/switzerland-plenitude-finalization-2026-09-28.json")
OFFICIAL="https://eniplenitude.com/mobilita-elettrica/tariffe-ricarica-auto-elettrica"
MONTHEY="https://map.evromandie.ch/?location=81976c4d-c319-4715-820b-3adcbba7dacc"
MENDRISIO="https://www.goingelectric.de/stromtankstellen/Schweiz/Mendrisio/Via-Moree-Via-Moree-16/109549/"
mapping={
 "CH*PLN*EH000762*1":("dc",60,"ccs",MONTHEY),"CH*PLN*EH000762*2":("dc",60,"ccs",MONTHEY),"CH*PLN*EH000762*3":("ac",22,"type2",MONTHEY),
 "CH*PLN*EH002719*1":("dc",400,"ccs",MENDRISIO),"CH*PLN*EH002719*2":("dc",50,"chademo",MENDRISIO),"CH*PLN*EH002719*3":("dc",400,"ccs",MENDRISIO),
 "CH*PLN*EH002726*1":("dc",400,"ccs",MENDRISIO),"CH*PLN*EH002726*2":("dc",50,"chademo",MENDRISIO),"CH*PLN*EH002726*3":("dc",400,"ccs",MENDRISIO),
 "CH*PLN*EH002738*1":("dc",400,"ccs",MENDRISIO),"CH*PLN*EH002738*2":("dc",50,"chademo",MENDRISIO),"CH*PLN*EH002738*3":("dc",400,"ccs",MENDRISIO),
 "CH*PLN*EH003299*1":("dc",100,"ccs",MENDRISIO),"CH*PLN*EH003299*2":("dc",100,"ccs",MENDRISIO),
 "CH*PLN*EH003300*1":("dc",100,"ccs",MENDRISIO),"CH*PLN*EH003300*2":("dc",100,"ccs",MENDRISIO),
 "CH*PLN*EH003301*1":("dc",100,"ccs",MENDRISIO),"CH*PLN*EH003301*2":("dc",100,"ccs",MENDRISIO),
 "CH*PLN*EH003302*1":("dc",100,"ccs",MENDRISIO),"CH*PLN*EH003302*2":("dc",100,"ccs",MENDRISIO),
}
def tariff(et,p):
    if et=="ac" and p<=22:return (0.50,"Quick")
    if et=="dc" and p<75:return (0.65,"Fast")
    if et=="dc" and p>75:return (0.70,"Fast+/Ultra Fast")
    return (None,None)
d=json.loads(DATA.read_text(encoding="utf-8"))
by={x["evseId"]:x for x in d.get("evses",[])}
remaining=[]
resolved=[]
for u in d.get("unresolved",[]):
    eid=u["evseId"]
    if eid not in mapping:
        remaining.append(u); continue
    et,p,plug,evidence=mapping[eid]; price,cat=tariff(et,p)
    if price is None:
        remaining.append(u); continue
    by[eid]={"evseId":eid,"powerKw":p,"energyType":et,"plug":plug,
      "classificationSource":"Exact EVSE connector metadata from public station record",
      "connectorEvidenceUrl":evidence,"pricePerKwh":price,"category":cat,"currency":"CHF",
      "idleFeePolicy":"Official Plenitude page states 60 min post-charge grace; exact CHF idle fee is not guessed.",
      "source":OFFICIAL}
    resolved.append(eid)
d["evses"]=sorted(by.values(),key=lambda x:x["evseId"]); d["unresolved"]=remaining
d["counts"]["pricedEvseCount"]=len(d["evses"]); d["counts"]["unresolvedEvseCount"]=len(remaining)
d["counts"]["externallyMappedResidualEvseCount"]=len(resolved); d["generatedAt"]=datetime.now(timezone.utc).isoformat()
DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
f=json.loads(FINAL.read_text(encoding="utf-8")); f["updatedAt"]=d["generatedAt"]; f["pricedEvseCount"]=len(d["evses"]); f["unresolvedEvseCount"]=len(remaining)
f["status"]="complete" if not remaining and len(d["evses"])==f["nationalEvseCount"] else "partial"
f["method"]="Current national CH*PLN scope + official Plenitude Switzerland tariff tiers; exact connector metadata from Chargeprice plus targeted public EVSE records for residual stations"
FINAL.write_text(json.dumps(f,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(f,ensure_ascii=False,indent=2)); print(json.dumps({"resolved":resolved,"remaining":[x["evseId"] for x in remaining]},ensure_ascii=False,indent=2))
