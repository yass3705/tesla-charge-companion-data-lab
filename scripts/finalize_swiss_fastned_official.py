#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone
NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
PRICING="https://www.fastnedcharging.com/en/charging/tariffs"
OWNER="CH*FASTNED"
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}
req=urllib.request.Request(NATIONAL,headers=UA)
with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
j=json.loads(raw.decode())
evs={}
def walk(x,owner=None):
 if isinstance(x,dict):
  if isinstance(x.get("OperatorID"),str):owner=x["OperatorID"]
  eid=x.get("EvseID")
  if owner==OWNER and isinstance(eid,str):evs[eid]=x
  for v in x.values():walk(v,owner)
 elif isinstance(x,list):
  for v in x:walk(v,owner)
walk(j)
rows=[]
for eid,d in sorted(evs.items()):
 rows.append({"evseId":eid,"chargingStationId":d.get("ChargingStationId"),"address":d.get("Address"),"geo":d.get("GeoCoordinates"),
              "standardPricePerKwh":0.75,"goldPricePerKwh":0.53,"currency":"CHF",
              "appDiscount":"10% off standard price via Fastned app when eligible; exact derived amount intentionally not rounded/stored as a quoted tariff",
              "source":PRICING})
now=datetime.now(timezone.utc).isoformat()
policy="Fastned's current official Switzerland tariff page publishes a countrywide standard price of CHF 0.75/kWh and Gold price CHF 0.53/kWh. Applied only to EVSEs whose national-feed OperatorID is CH*FASTNED."
payload={"schemaVersion":1,"country":"CH","cpo":"Fastned","operatorId":OWNER,"generatedAt":now,
 "sources":{"national":NATIONAL,"officialPricing":PRICING},
 "tariffs":{"standard":{"pricePerKwh":0.75,"currency":"CHF"},"gold":{"pricePerKwh":0.53,"currency":"CHF"},"appDiscountPercent":10},
 "counts":{"nationalEvseCount":len(rows),"pricedEvseCount":len(rows),"unresolvedEvseCount":0},"policy":policy,"evses":rows}
final={"schemaVersion":1,"country":"CH","cpo":"Fastned","operatorId":OWNER,"status":"complete" if rows else "partial","updatedAt":now,
 "nationalEvseCount":len(rows),"pricedEvseCount":len(rows),"unresolvedEvseCount":0,
 "method":"Current Swiss national CH*FASTNED owner scope + Fastned official Switzerland nationwide tariff",
 "policy":policy,"productionSource":"data/switzerland/fastned-official-direct-tariffs.json"}
Path("data/switzerland").mkdir(parents=True,exist_ok=True);Path("docs").mkdir(exist_ok=True)
Path("data/switzerland/fastned-official-direct-tariffs.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
Path("docs/switzerland-fastned-finalization-2026-09-28.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
