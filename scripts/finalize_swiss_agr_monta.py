#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
MONTA="https://monta.imgix.net/roaming-data/monta-as-a-cpo-pricing.json"
PREFIX="CH*AGR"
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

nat=getj(NATIONAL); national=set()
for d in walk(nat):
    for k,v in d.items():
        if isinstance(v,str) and "evse" in k.lower() and v.startswith(PREFIX+"*E"): national.add(v)

m=getj(MONTA); rows=m.get("data",[]) if isinstance(m,dict) else m
by={r.get("evse_id"):r for r in rows if isinstance(r,dict) and str(r.get("evse_id","")).startswith(PREFIX+"*E")}
matched=sorted(national & set(by))
priced=[eid for eid in matched if any(by[eid].get(k) is not None for k in ("price_kw","price_min","price_start","price_idle"))]
missing=sorted(national-set(priced))
evses=[]
for eid in priced:
    r=by[eid]
    evses.append({"evseId":eid,"operator":r.get("operator"),"address":r.get("address"),"location":r.get("location"),
      "maxKw":r.get("max_kw"),"currency":str(r.get("currency") or "").upper() or None,
      "pricePerKwh":r.get("price_kw"),"pricePerMinute":r.get("price_min"),"startFee":r.get("price_start"),
      "idleFee":r.get("price_idle"),"ocpiTariffId":r.get("ocpi_tariff_id"),"source":"Monta public CPO pricing export"})
now=datetime.now(timezone.utc).isoformat()
status="complete" if national and len(priced)==len(national) else "partial"
payload={"schemaVersion":1,"country":"CH","cpo":"AGROLA","operatorId":PREFIX,"generatedAt":now,
 "sources":{"national":NATIONAL,"monta":MONTA},"counts":{"nationalEvseCount":len(national),"matchedPricedEvseCount":len(priced),"missingEvseCount":len(missing)},
 "missingEvseIds":missing,"evses":evses,"policy":"Current Swiss national CH*AGR scope is canonical. No extrapolation."}
final={"schemaVersion":1,"country":"CH","cpo":"AGROLA","operatorId":PREFIX,"status":status,"updatedAt":now,
 "nationalEvseCount":len(national),"pricedEvseCount":len(priced),"missingEvseCount":len(missing),
 "method":"Swiss national OICP CH*AGR scope reconciled against Monta public CPO pricing export",
 "policy":"No tariff extrapolation; only exact EVSE-ID matches are retained.","productionSource":"data/switzerland/agr-monta-direct-tariffs.json"}
Path("data/switzerland").mkdir(parents=True,exist_ok=True);Path("docs").mkdir(exist_ok=True)
Path("data/switzerland/agr-monta-direct-tariffs.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
Path("docs/switzerland-agr-finalization-2026-09-28.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
