#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
PRICE_SOURCE="https://www.ewd.ch/ueber-uns/faq"
PREFIX="CH*EWD"
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

nat=getj(NATIONAL); rows=[]
for d in walk(nat):
    eid=d.get("EvseID") if isinstance(d,dict) else None
    if isinstance(eid,str) and eid.startswith(PREFIX+"*E"):
        rows.append({"evseId":eid,"chargingStationId":d.get("ChargingStationId"),
                     "currency":"CHF","startFee":1.0,"pricePerKwh":0.58,
                     "source":"EWD official FAQ public charging tariff"})
rows={r["evseId"]:r for r in rows}
now=datetime.now(timezone.utc).isoformat()
payload={"schemaVersion":1,"country":"CH","cpo":"EWD Elektrizitaetswerk Davos AG","operatorId":PREFIX,
 "generatedAt":now,"source":{"national":NATIONAL,"pricing":PRICE_SOURCE},
 "counts":{"nationalEvseCount":len(rows),"pricedEvseCount":len(rows),"unresolvedEvseCount":0},
 "policy":"Tariff applied only to current national CH*EWD EVSE IDs. EWD official FAQ states CHF 1 start fee and CHF 0.58/kWh for EWD charging stations.",
 "evses":sorted(rows.values(),key=lambda x:x["evseId"])}
final={"schemaVersion":1,"country":"CH","cpo":"EWD Elektrizitaetswerk Davos AG","operatorId":PREFIX,
 "status":"complete" if rows else "partial","updatedAt":now,"nationalEvseCount":len(rows),
 "pricedEvseCount":len(rows),"unresolvedEvseCount":0 if rows else 1,
 "method":"Current Swiss national CH*EWD scope + EWD official public charging tariff",
 "policy":payload["policy"],"productionSource":"data/switzerland/ewd-official-direct-tariffs.json"}
Path("data/switzerland").mkdir(parents=True,exist_ok=True);Path("docs").mkdir(exist_ok=True)
Path("data/switzerland/ewd-official-direct-tariffs.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
Path("docs/switzerland-ewd-finalization-2026-09-28.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
