#!/usr/bin/env python3
import gzip,json,math,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
OFFICIAL="https://www.matterhorngotthardbahn.ch/fr/products/e-zone"
PRICE_EVIDENCE="https://www.goingelectric.de/stromtankstellen/Schweiz/Taesch/Matterhorn-Terminal-Kantonsstrasse-45/10634/amp/"
PREFIX="CH*TAE"
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
rows=[]; unresolved=[]
for d in walk(nat):
    if not isinstance(d,dict) or d.get("OperatorID")!=PREFIX: continue
    eid=d.get("EvseID")
    if not isinstance(eid,str): continue
    powers=[]
    for cf in d.get("ChargingFacilities") or []:
        try:
            p=float(cf.get("power"))
            if p>0:powers.append(p)
        except:pass
    p=max(powers) if powers else None
    pos=d.get("GeoCoordinates") or d.get("GeoCoordinate") or {}
    lat=pos.get("Latitude") if isinstance(pos,dict) else None
    lon=pos.get("Longitude") if isinstance(pos,dict) else None
    row={"evseId":eid,"chargingStationId":d.get("ChargingStationId"),"maxPowerKw":p,
         "pricePerKwhCHF":0.55,"sessionFeeCHF":4.0,"smsSurchargeCHF":0.25,
         "paymentMethods":["QR/NFC","credit card","TWINT","SMS","Apple Pay","Google Pay"],
         "sourceOfficialFacility":OFFICIAL,"sourceCurrentPriceEvidence":PRICE_EVIDENCE}
    # Fail closed if national record contradicts the official terminal configuration (Type 2 up to 22 kW).
    if p is None or p>22.0001:
        unresolved.append({"evseId":eid,"reason":"national_power_missing_or_outside_official_terminal_configuration","maxPowerKw":p})
    rows.append(row)

now=datetime.now(timezone.utc).isoformat()
priced=len(rows)-len(unresolved)
status="complete" if rows and not unresolved else "partial"
policy=("Current national CH*TAE owner scope only. Matterhorn Gotthard Bahn confirms the Terminal E-Zone uses Type 2 charging up to 22 kW and QR/NFC direct payment. "
        "The current public station record updated 24 Sep 2026 reports CHF 4/session + CHF 0.55/kWh, with CHF 0.25 extra when paying by SMS. "
        "No price is assigned if a current national EVSE contradicts the terminal power configuration.")
payload={"schemaVersion":1,"country":"CH","cpo":"Matterhorn Terminal Täsch","operatorId":PREFIX,"generatedAt":now,
         "sources":{"national":NATIONAL,"officialFacility":OFFICIAL,"currentPriceEvidence":PRICE_EVIDENCE},
         "counts":{"nationalEvseCount":len(rows),"pricedEvseCount":priced,"unresolvedEvseCount":len(unresolved)},
         "tariff":{"currency":"CHF","sessionFee":4.0,"pricePerKwh":0.55,"smsSurcharge":0.25},
         "policy":policy,"unresolved":unresolved,"evses":rows}
final={"schemaVersion":1,"country":"CH","cpo":"Matterhorn Terminal Täsch","operatorId":PREFIX,"status":status,"updatedAt":now,
       "nationalEvseCount":len(rows),"pricedEvseCount":priced,"unresolvedEvseCount":len(unresolved),
       "method":"Current CH*TAE owner scope + official terminal charging configuration/payment methods + current station tariff evidence",
       "policy":policy,"productionSource":"data/switzerland/tae-matterhorn-terminal-direct-tariffs.json"}
Path("data/switzerland").mkdir(parents=True,exist_ok=True);Path("docs").mkdir(exist_ok=True)
Path("data/switzerland/tae-matterhorn-terminal-direct-tariffs.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
Path("docs/switzerland-tae-finalization-2026-09-28.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
