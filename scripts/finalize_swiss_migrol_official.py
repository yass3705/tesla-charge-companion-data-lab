#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
PRICE_SOURCE="https://www.migrol.ch/fr/concernant-la-voiture/bornes-de-recharge/bornes-de-recharge-publiques/"
PREFIX="CH*MIG"
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}
SCHEDULE=[
  {"maxKw":22.0,"chfPerKwh":0.38},
  {"maxKw":64.0,"chfPerKwh":0.48},
  {"maxKw":200.0,"chfPerKwh":0.55},
  {"maxKw":400.0,"chfPerKwh":0.59},
]

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
def tariff(power):
    if power is None:return None
    for row in SCHEDULE:
        if power <= row["maxKw"]+1e-9:return row["chfPerKwh"]
    return None

nat=getj(NATIONAL)
records=[]
for d in walk(nat):
    eid=d.get("EvseID") if isinstance(d,dict) else None
    if isinstance(eid,str) and eid.startswith(PREFIX+"*E"):
        records.append(d)
by={d["EvseID"]:d for d in records}
out=[]; unresolved=[]
for eid,d in sorted(by.items()):
    powers=[]
    for f in d.get("ChargingFacilities") or []:
        try:powers.append(float(f.get("power")))
        except Exception:pass
    p=max(powers) if powers else None
    rate=tariff(p)
    row={"evseId":eid,"chargingStationId":d.get("ChargingStationId"),"maxPowerKw":p,
         "currency":"CHF","pricePerKwh":rate,"startFee":0.0,"pricePerMinute":0.0,
         "source":"Migrol official M-Charge national public tariff schedule"}
    out.append(row)
    if rate is None: unresolved.append({"evseId":eid,"maxPowerKw":p,"reason":"power_not_mapped_to_official_schedule"})
now=datetime.now(timezone.utc).isoformat()
status="complete" if out and not unresolved else "partial"
payload={"schemaVersion":1,"country":"CH","cpo":"Migrol / M-Charge","operatorId":PREFIX,"generatedAt":now,
 "source":{"national":NATIONAL,"pricing":PRICE_SOURCE},
 "tariffSchedule":SCHEDULE,
 "counts":{"nationalEvseCount":len(out),"pricedEvseCount":len(out)-len(unresolved),"unresolvedEvseCount":len(unresolved)},
 "policy":"Per-EVSE tariff derived only from that EVSE's own national-feed charging power and Migrol's official nationwide M-Charge power-tier tariff. No cross-station extrapolation.",
 "unresolved":unresolved,"evses":out}
final={"schemaVersion":1,"country":"CH","cpo":"Migrol / M-Charge","operatorId":PREFIX,"status":status,"updatedAt":now,
 "nationalEvseCount":len(out),"pricedEvseCount":len(out)-len(unresolved),"unresolvedEvseCount":len(unresolved),
 "method":"Official Swiss national OICP EVSE power + Migrol official nationwide M-Charge power-tier tariff",
 "policy":payload["policy"],"productionSource":"data/switzerland/migrol-official-direct-tariffs.json"}
Path("data/switzerland").mkdir(parents=True,exist_ok=True);Path("docs").mkdir(exist_ok=True)
Path("data/switzerland/migrol-official-direct-tariffs.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
Path("docs/switzerland-migrol-finalization-2026-09-28.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
