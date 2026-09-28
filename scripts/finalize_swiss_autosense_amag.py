#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
OFFICIAL="https://www.amag.ch/fr/cartes/carte-de-recharge.html"
CHAM="https://parking.amag.ch/en/parkhaus/cham/amag.html"
PREFIX="CH*AUTOSENSE"
req=urllib.request.Request(URL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
j=json.loads(raw.decode("utf-8"))
owned={}
def walk(x,owner=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str) and x["OperatorID"].strip():owner=x["OperatorID"].strip()
        eid=x.get("EvseID")
        if owner==PREFIX and isinstance(eid,str) and eid.strip():owned[eid.strip()]=x
        for v in x.values():walk(v,owner)
    elif isinstance(x,list):
        for v in x:walk(v,owner)
walk(j)
rows=[];unresolved=[]
for eid,d in sorted(owned.items()):
    names=d.get("ChargingStationNames") or []
    if isinstance(names,dict): names=[names]
    vals=[str(x.get("value","")) for x in names if isinstance(x,dict)]
    station_name=" | ".join(vals)
    amag=("AMAG Charging Station" in station_name)
    powers=[]
    for cf in d.get("ChargingFacilities") or []:
        try:
            p=float(cf.get("power"))
            if p>0:powers.append(p)
        except:pass
    if not amag:
        unresolved.append({"evseId":eid,"reason":"current_station_not_identified_as_AMAG","stationName":station_name})
        continue
    rows.append({
      "evseId":eid,"stationName":station_name,"maxPowerKw":max(powers) if powers else None,
      "currency":"CHF","standardPricePerKwh":0.56,
      "conditionalEligibleBrandPricePerKwh":0.28,
      "eligibleBrands":["Volkswagen","Audi","SEAT","Skoda","CUPRA","VW Commercial Vehicles"],
      "eligibility":"AMAG app or Helion chargeON app/card and eligible imported brand for CHF 0.28/kWh",
      "source":OFFICIAL
    })
now=datetime.now(timezone.utc).isoformat()
total=len(owned);priced=len(rows);status="complete" if total and priced==total and not unresolved else "partial"
policy=("Current CH*AUTOSENSE owner scope only; every EVSE must identify as an AMAG Charging Station. "
        "Current AMAG public tariff: CHF 0.56/kWh for other vehicles; CHF 0.28/kWh is retained only as a conditional eligible-brand/app tariff, not used as an unconditional direct price.")
payload={"schemaVersion":1,"country":"CH","cpo":"autoSense / AMAG public charging","operatorId":PREFIX,"generatedAt":now,
         "sources":{"national":URL,"officialTariff":OFFICIAL,"officialChamSite":CHAM},
         "counts":{"nationalEvseCount":total,"pricedEvseCount":priced,"unresolvedEvseCount":len(unresolved)},
         "policy":policy,"evses":rows,"unresolved":unresolved}
final={"schemaVersion":1,"country":"CH","cpo":"autoSense / AMAG","operatorId":PREFIX,"status":status,"updatedAt":now,
       "nationalEvseCount":total,"pricedEvseCount":priced,"unresolvedEvseCount":len(unresolved),
       "method":"Current national CH*AUTOSENSE owner scope + current AMAG public charging tariff; conditional eligible-brand tariff stored separately",
       "policy":policy,"productionSource":"data/switzerland/autosense-amag-direct-tariffs.json"}
Path("data/switzerland").mkdir(parents=True,exist_ok=True);Path("docs").mkdir(exist_ok=True)
Path("data/switzerland/autosense-amag-direct-tariffs.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
Path("docs/switzerland-autosense-finalization-2026-09-28.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(final,ensure_ascii=False,indent=2))
