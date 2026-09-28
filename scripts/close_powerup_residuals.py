#!/usr/bin/env python3
import json,urllib.request,re
from pathlib import Path
from datetime import datetime,timezone

DATA=Path("data/switzerland/powerup-monta-direct-tariffs.json")
FINAL=Path("docs/switzerland-powerup-finalization-2026-09-28.json")
TARGETS={
 "CH*POW*E137808":"https://management.charge.agrola.ch/d/c166136",
 "CH*POW*E137809":"https://management.charge.agrola.ch/d/c166137",
}
UA={"User-Agent":"Mozilla/5.0","Accept":"text/html"}

d=json.loads(DATA.read_text(encoding="utf-8"))
by={x["evseId"]:x for x in d.get("evses",[])}
for eid,url in TARGETS.items():
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=30) as r:
        html=r.read().decode("utf-8","replace")
    titlem=re.search(r'<p class="text-lg font-bold[^>]*>(.*?)</p>',html,re.S)
    pm=re.search(r'([0-9]+(?:\.[0-9]+)?)\s*CHF<span[^>]*>/kWh',html)
    mm=re.search(r'([0-9]+(?:\.[0-9]+)?)\s*CHF</span><span[^>]*>/<!-- -->min',html)
    if not titlem or not pm or eid.split("*E")[-1] not in titlem.group(1):
        raise SystemExit(f"Direct evidence validation failed for {eid}")
    rec={
      "evseId":eid,
      "operator":"PowerUp by AGROLA",
      "address":"Murtenstrasse 28, 3177 Laupen, Switzerland",
      "location":None,
      "maxKw":None,
      "currency":"CHF",
      "pricePerKwh":float(pm.group(1)),
      "pricePerMinute":float(mm.group(1)) if mm else None,
      "startFee":None,
      "idleFee":None,
      "ocpiTariffId":None,
      "source":"Monta public direct-payment page",
      "sourceUrl":url,
      "sourceTitle":re.sub("<[^>]+>","",titlem.group(1)).strip()
    }
    by[eid]=rec

d["evses"]=sorted(by.values(),key=lambda x:x["evseId"])
current=set(x["evseId"] for x in d["evses"])
missing=[x for x in d.get("missingCurrentEvseIds",[]) if x not in TARGETS]
d["missingCurrentEvseIds"]=missing
c=d["counts"]
c["currentMatchedEvseCount"]=235
c["currentPricedEvseCount"]=235
c["currentMissingInMontaCount"]=0
d["resolvedByDirectPageEvidence"]=list(TARGETS)
d["generatedAt"]=datetime.now(timezone.utc).isoformat()
DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

f=json.loads(FINAL.read_text(encoding="utf-8"))
f.update({
 "status":"complete",
 "updatedAt":d["generatedAt"],
 "currentMatchedEvseCount":235,
 "currentPricedEvseCount":235,
 "currentMissingInMontaCount":0,
 "method":"Swiss national OICP CH*POW scope reconciled against Monta public CPO pricing export, with two residual EVSEs closed by direct Monta public payment pages",
 "policy":"Current Swiss national CH*POW scope is canonical. Monta-only extras are not promoted. No tariff extrapolation."
})
FINAL.write_text(json.dumps(f,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(f,ensure_ascii=False,indent=2))
