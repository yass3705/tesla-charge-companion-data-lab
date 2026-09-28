#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
PRICE="https://www.evpass.ch/fr_ch/laden/preise.html"
PREFIX="CHEVP"
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}
req=urllib.request.Request(URL,headers=UA)
with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
j=json.loads(raw.decode("utf-8"))
owned={}
def walk(x,owner=None,owner_name=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str) and x["OperatorID"].strip():
            owner=x["OperatorID"].strip();owner_name=x.get("OperatorName")
        eid=x.get("EvseID")
        if owner==PREFIX and isinstance(eid,str) and eid.strip():
            owned[eid.strip()]={"record":x,"operatorName":owner_name}
        for v in x.values():walk(v,owner,owner_name)
    elif isinstance(x,list):
        for v in x:walk(v,owner,owner_name)
walk(j)
def tariff(p):
    if p is None:return None
    if p<=22.0001:return {"pricePerKwhCHF":0.65,"sessionFeeCHF":1.50,"tier":"<=22kW"}
    if p<=80.0001:return {"pricePerKwhCHF":0.79,"sessionFeeCHF":0.0,"tier":">22kW_and_<=80kW"}
    return {"pricePerKwhCHF":0.89,"sessionFeeCHF":0.0,"tier":">80kW"}
rows=[];unresolved=[]
for eid,item in sorted(owned.items()):
    d=item["record"]; powers=[]
    for cf in d.get("ChargingFacilities") or []:
        try:
            p=float(cf.get("power"))
            if p>0:powers.append(p)
        except:pass
    p=max(powers) if powers else None
    t=tariff(p)
    if item.get("operatorName") and str(item["operatorName"]).lower()!="evpass":
        unresolved.append({"evseId":eid,"reason":"current_national_operator_name_not_evpass","operatorName":item.get("operatorName")})
        continue
    if not t:
        unresolved.append({"evseId":eid,"reason":"missing_power"})
        continue
    rows.append({"evseId":eid,"maxPowerKw":p,**t,"currency":"CHF","source":PRICE,
                 "parkingPenalty":"excluded; station-specific if applicable"})
now=datetime.now(timezone.utc).isoformat()
total=len(owned);priced=len(rows);status="complete" if total and priced==total and not unresolved else "partial"
policy=("Apply evpass's current uniform Scan, Pay & Charge tariff only to current national CHEVP records whose current owner is evpass. "
        "Tier selection uses each EVSE's own national power. <=22kW: CHF 1.50/session + 0.65/kWh; <=80kW above 22kW: 0.79/kWh; >80kW: 0.89/kWh. "
        "The official evpass page states Scan, Pay & Charge works without an account at evpass stations; park/penalty fees remain excluded.")
payload={"schemaVersion":1,"country":"CH","cpo":"evpass legacy CHEVP","operatorId":PREFIX,"generatedAt":now,
         "sources":{"national":URL,"officialPrice":PRICE},"counts":{"nationalEvseCount":total,"pricedEvseCount":priced,"unresolvedEvseCount":len(unresolved)},
         "policy":policy,"evses":rows,"unresolved":unresolved}
final={"schemaVersion":1,"country":"CH","cpo":"evpass","operatorId":PREFIX,"status":status,"updatedAt":now,"nationalEvseCount":total,
       "pricedEvseCount":priced,"unresolvedEvseCount":len(unresolved),
       "method":"Current national CHEVP owner scope + current evpass uniform Scan, Pay & Charge tariff by exact EVSE power",
       "policy":policy,"productionSource":"data/switzerland/chevp-evpass-official-direct-tariffs.json"}
Path("data/switzerland").mkdir(parents=True,exist_ok=True);Path("docs").mkdir(exist_ok=True)
Path("data/switzerland/chevp-evpass-official-direct-tariffs.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
Path("docs/switzerland-chevp-finalization-2026-09-28.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
