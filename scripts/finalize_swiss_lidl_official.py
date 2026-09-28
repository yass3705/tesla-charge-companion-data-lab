#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone
NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
PRICE_SOURCE="https://www.lidl.ch/c/de-CH/e-ladesaeulen/s10023632"
PREFIX="CH*LDL"
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}
def getj(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
    if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))
def walk(o):
    if isinstance(o,dict):
        yield o
        for v in o.values(): yield from walk(v)
    elif isinstance(o,list):
        for v in o: yield from walk(v)
nat=getj(NATIONAL)
by={}
for d in walk(nat):
    eid=d.get("EvseID") if isinstance(d,dict) else None
    if isinstance(eid,str) and eid.startswith(PREFIX+"*E"): by[eid]=d
rows=[]; unresolved=[]
for eid,d in sorted(by.items()):
    powers=[]
    for f in d.get("ChargingFacilities") or []:
        try:powers.append(float(f.get("power")))
        except Exception:pass
    p=max(powers) if powers else None
    if p is None:
        typ=None
    elif p<=22.0+1e-9:
        typ="AC"
    else:
        typ="DC"
    if typ=="AC":
        web=0.50; app=0.26
    elif typ=="DC":
        web=0.62; app=0.42
    else:
        web=app=None
    row={"evseId":eid,"chargingStationId":d.get("ChargingStationId"),"maxPowerKw":p,"energyType":typ,
         "currency":"CHF","directWebPricePerKwh":web,"lidlPlusPricePerKwh":app,
         "source":"Lidl Switzerland official e-mobility pricing"}
    rows.append(row)
    if web is None: unresolved.append({"evseId":eid,"maxPowerKw":p,"reason":"power_missing"})
now=datetime.now(timezone.utc).isoformat()
status="complete" if rows and not unresolved else "partial"
policy="Apply Lidl Switzerland's published national AC/DC prices to each current CH*LDL EVSE using only that EVSE's own national-feed power. Direct web/ad-hoc: AC 0.50 CHF/kWh, DC 0.62 CHF/kWh. Lidl Plus: AC 0.26, DC 0.42. No cross-station extrapolation."
payload={"schemaVersion":1,"country":"CH","cpo":"Lidl","operatorId":PREFIX,"generatedAt":now,
 "source":{"national":NATIONAL,"pricing":PRICE_SOURCE},
 "tariffSchedule":{"directWeb":{"AC":0.50,"DC":0.62},"lidlPlus":{"AC":0.26,"DC":0.42},"currency":"CHF"},
 "counts":{"nationalEvseCount":len(rows),"pricedEvseCount":len(rows)-len(unresolved),"unresolvedEvseCount":len(unresolved)},
 "policy":policy,"unresolved":unresolved,"evses":rows}
final={"schemaVersion":1,"country":"CH","cpo":"Lidl","operatorId":PREFIX,"status":status,"updatedAt":now,
 "nationalEvseCount":len(rows),"pricedEvseCount":len(rows)-len(unresolved),"unresolvedEvseCount":len(unresolved),
 "method":"Current Swiss national CH*LDL scope + Lidl Switzerland official AC/DC web and Lidl Plus tariff schedule",
 "policy":policy,"productionSource":"data/switzerland/lidl-official-direct-tariffs.json"}
Path("data/switzerland").mkdir(parents=True,exist_ok=True);Path("docs").mkdir(exist_ok=True)
Path("data/switzerland/lidl-official-direct-tariffs.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
Path("docs/switzerland-lidl-finalization-2026-09-28.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
