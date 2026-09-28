#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime,timezone
DATA=Path("data/switzerland/ebs-ecarup-direct-tariffs.json")
FINAL=Path("docs/switzerland-ebs-finalization-2026-09-28.json")
d=json.loads(DATA.read_text(encoding="utf-8"))
official={
 "CH*EBS*E123*0004":{"energyPrice":0.47,"currency":"CHF","source":"https://parkhaushofmatt.ch/tarife/","sourceType":"official location website","station":"Parkhaus Hofmatt","note":"Current page lists Ladetarif Elektrofahrzeuge CHF 0.47/kWh."},
 "CH*EBS*E123*0005":{"energyPrice":0.42,"currency":"CHF","source":"https://mythenforum.ch/parking/","sourceType":"official location website","station":"Parkhaus MythenForum","note":"Current parking page lists Stromtankstelle CHF 0.42/kWh."}
}
existing={x["evseId"]:x for x in d.get("evses",[])}
remaining=[]
resolvedOfficial=[]
for u in d.get("unresolved",[]):
 eid=u.get("evseId")
 if eid in official:
   x={"evseId":eid,"tariff":{"energyPrice":official[eid]["energyPrice"],"currency":official[eid]["currency"],"parkingPrice":"separate_location_parking_tariff"},
      "classificationSource":official[eid]["sourceType"],"source":official[eid]["source"],"station":official[eid]["station"],"note":official[eid]["note"]}
   existing[eid]=x;resolvedOfficial.append(eid)
 else: remaining.append(u)
d["evses"]=sorted(existing.values(),key=lambda x:x["evseId"])
d["unresolved"]=remaining
d["counts"]["pricedEvseCount"]=len(d["evses"]);d["counts"]["unresolvedEvseCount"]=len(remaining)
d["officialLocationWebsiteResolvedEvseIds"]=resolvedOfficial
d["generatedAt"]=datetime.now(timezone.utc).isoformat()
d["policy"]="Exact eCarUp same-operator prices where available, plus exact official location-site tariffs for Hofmatt and MythenForum. Sahli remains unresolved because current public sources disagree on direct/ad-hoc payment availability; no extrapolation."
DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
f=json.loads(FINAL.read_text(encoding="utf-8"));f["updatedAt"]=d["generatedAt"];f["pricedEvseCount"]=len(d["evses"]);f["unresolvedEvseCount"]=len(remaining)
f["status"]="complete" if not remaining and len(d["evses"])==f["nationalEvseCount"] else "partial"
f["method"]="Current national CH*EBS scope + exact eCarUp same-operator pricing + current official Hofmatt/MythenForum location tariffs"
f["policy"]=d["policy"]
FINAL.write_text(json.dumps(f,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(f,ensure_ascii=False,indent=2));print(json.dumps({"resolvedOfficial":resolvedOfficial,"remaining":remaining},ensure_ascii=False,indent=2))
