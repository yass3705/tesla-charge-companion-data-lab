#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
PRICE_SOURCE="https://www.evpass.ch/fr_ch/laden/preise.html"
SHELL_SOURCE="https://www.shell.ch/fr_ch/a-propos-de-nous/2023/shell-reprend-evpass-et-devient-le-plus-grand-reseau-de-recharge-de-suisse.html"
OPERATOR_SOURCE="https://github.com/SFOE/ichtankestrom_Documentation/blob/main/List%20of%20Charging%20Point%20Operators.md"
PREFIX="CH*SHE"
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}

def getj(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=90) as r:
        raw=r.read()
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
    if isinstance(eid,str) and eid.startswith(PREFIX+"*E"):
        by[eid]=d

rows=[]; unresolved=[]
for eid,d in sorted(by.items()):
    powers=[]
    for f in d.get("ChargingFacilities") or []:
        try:
            p=float(f.get("power"))
            if p>0: powers.append(p)
        except Exception:
            pass
    p=max(powers) if powers else None
    if p is None:
        price=None; tier=None; session=None
    elif p <= 22.0 + 1e-9:
        price=0.65; tier="<=22kW"; session=1.50
    elif p <= 80.0 + 1e-9:
        price=0.79; tier=">22kW_and_<=80kW"; session=0.0
    else:
        price=0.89; tier=">80kW"; session=0.0
    row={
      "evseId":eid,
      "chargingStationId":d.get("ChargingStationId"),
      "maxPowerKw":p,
      "currency":"CHF",
      "pricePerKwh":price,
      "sessionFee":session,
      "tariffTier":tier,
      "parkingAndPenaltyFees":"excluded_from_base_tariff; station-specific if applicable",
      "source":"evpass official Switzerland public charging tariff"
    }
    rows.append(row)
    if price is None:
        unresolved.append({"evseId":eid,"reason":"power_missing_in_current_national_feed"})

now=datetime.now(timezone.utc).isoformat()
status="complete" if rows and not unresolved else "partial"
policy=(
 "Apply the current evpass Switzerland public charging tariff only to the current national CH*SHE "
 "owner scope, identified by the Swiss CPO registry as Shell Recharge. Tier selection uses each "
 "EVSE's own national-feed maximum power only. <=22kW: CHF 1.50/session + CHF 0.65/kWh; "
 "<=80kW above 22kW: CHF 0.79/kWh; >80kW: CHF 0.89/kWh. Parking and penalty fees are not "
 "invented because evpass states they are excluded and may be station-specific. No roaming tariff "
 "and no cross-station extrapolation."
)
payload={
 "schemaVersion":1,"country":"CH","cpo":"Shell Recharge / evpass","operatorId":PREFIX,
 "generatedAt":now,
 "sources":{"national":NATIONAL,"pricing":PRICE_SOURCE,"shellEvpassRelationship":SHELL_SOURCE,"operatorRegistry":OPERATOR_SOURCE},
 "tariffSchedule":{
   "<=22kW":{"sessionFeeCHF":1.50,"pricePerKwhCHF":0.65},
   ">22kW_and_<=80kW":{"pricePerKwhCHF":0.79},
   ">80kW":{"pricePerKwhCHF":0.89},
   "parkingPenalty":"excluded; station-specific if applicable"
 },
 "counts":{"nationalEvseCount":len(rows),"pricedEvseCount":len(rows)-len(unresolved),"unresolvedEvseCount":len(unresolved)},
 "policy":policy,"unresolved":unresolved,"evses":rows
}
final={
 "schemaVersion":1,"country":"CH","cpo":"Shell Recharge / evpass","operatorId":PREFIX,
 "status":status,"updatedAt":now,"nationalEvseCount":len(rows),
 "pricedEvseCount":len(rows)-len(unresolved),"unresolvedEvseCount":len(unresolved),
 "method":"Current Swiss national CH*SHE owner scope + evpass official Switzerland public tariff tiers by exact EVSE power",
 "policy":policy,"productionSource":"data/switzerland/shell-evpass-official-direct-tariffs.json"
}
Path("data/switzerland").mkdir(parents=True,exist_ok=True)
Path("docs").mkdir(exist_ok=True)
Path("data/switzerland/shell-evpass-official-direct-tariffs.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
Path("docs/switzerland-shell-finalization-2026-09-28.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
