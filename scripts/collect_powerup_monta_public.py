#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
MONTA="https://monta.imgix.net/roaming-data/monta-as-a-cpo-pricing.json"
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}

def get_json(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=90) as r:
        raw=r.read()
    if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))

def walk(obj):
    if isinstance(obj,dict):
        yield obj
        for v in obj.values(): yield from walk(v)
    elif isinstance(obj,list):
        for v in obj: yield from walk(v)

nat=get_json(NATIONAL)
national_ids=set()
for d in walk(nat):
    for k,v in d.items():
        if isinstance(v,str) and "evse" in k.lower() and v.startswith("CH*POW*E"):
            national_ids.add(v)

monta=get_json(MONTA)
rows=monta.get("data",[]) if isinstance(monta,dict) else monta
power=[r for r in rows if isinstance(r,dict) and str(r.get("evse_id","")).startswith("CH*POW*E")]
by_id={r["evse_id"]:r for r in power if r.get("evse_id")}
monta_ids=set(by_id)
common=sorted(national_ids & monta_ids)
missing=sorted(national_ids-monta_ids)
extra=sorted(monta_ids-national_ids)

normalized=[]
for eid in common:
    r=by_id[eid]
    normalized.append({
        "evseId":eid,
        "operator":r.get("operator"),
        "address":r.get("address"),
        "location":r.get("location"),
        "maxKw":r.get("max_kw"),
        "currency":str(r.get("currency") or "").upper() or None,
        "pricePerKwh":r.get("price_kw"),
        "pricePerMinute":r.get("price_min"),
        "startFee":r.get("price_start"),
        "idleFee":r.get("price_idle"),
        "ocpiTariffId":r.get("ocpi_tariff_id"),
        "source":"Monta public CPO pricing export"
    })

resolved=[x for x in normalized if x["pricePerKwh"] is not None or x["pricePerMinute"] is not None or x["startFee"] is not None or x["idleFee"] is not None]
status="complete" if len(common)==len(national_ids) and len(resolved)==len(national_ids) else "partial"
payload={
 "schemaVersion":1,"country":"CH","cpo":"PowerUp by AGROLA","operatorId":"CH*POW",
 "generatedAt":datetime.now(timezone.utc).isoformat(),
 "sources":{"national":NATIONAL,"monta":MONTA},
 "counts":{"nationalEvseCount":len(national_ids),"montaPowerUpRowCount":len(power),"montaUniqueEvseCount":len(monta_ids),"currentMatchedEvseCount":len(common),"currentPricedEvseCount":len(resolved),"currentMissingInMontaCount":len(missing),"montaExtraVsNationalCount":len(extra)},
 "policy":"Current Swiss national CH*POW scope is canonical. Monta-only extras are not promoted. No tariff extrapolation.",
 "missingCurrentEvseIds":missing,"montaExtraEvseIds":extra,"evses":normalized
}
final={
 "schemaVersion":1,"country":"CH","cpo":"PowerUp by AGROLA","operatorId":"CH*POW","status":status,
 "updatedAt":payload["generatedAt"],**payload["counts"],
 "method":"Swiss national OICP CH*POW scope reconciled against Monta public CPO pricing export",
 "policy":payload["policy"],
 "productionSource":"data/switzerland/powerup-monta-direct-tariffs.json"
}
Path("data/switzerland").mkdir(parents=True,exist_ok=True);Path("docs").mkdir(exist_ok=True)
Path("data/switzerland/powerup-monta-direct-tariffs.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
Path("docs/switzerland-powerup-finalization-2026-09-28.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
