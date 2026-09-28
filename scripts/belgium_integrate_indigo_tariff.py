#!/usr/bin/env python3
import json
from pathlib import Path

SRC=Path("data/belgium/additional/canonical/indigo-belgium-canonical-2026-09-29.json")
OUT=Path("data/operator_direct/indigo_belgium_official_2026-09-29.json")
REP=Path("reports/belgium/belgium-indigo-tariff-integration-2026-09-29.json")
SOURCE_URL="https://blog.indigoneo.be/fr/points-de-recharge-pour-vehicules-electriques/"

d=json.loads(SRC.read_text())
entries=[]
for site in d.get("items") or []:
    for rp in site.get("refillPoints") or []:
        eid=rp.get("externalIdentifier")
        if not eid: continue
        entries.append({
          "externalIdentifier":eid,
          "siteName":site.get("name"),
          "city":site.get("city"),
          "postcode":site.get("postcode"),
          "tariffComponents":[
            {"priceType":"pricePerKWh","price":0.55,"currency":"EUR","taxIncluded":True},
            {"priceType":"pricePerMinute","price":0.013,"currency":"EUR","taxIncluded":True,"appliesDuring":"active charging session"},
            {"priceType":"flatFee","price":0.79,"currency":"EUR","taxIncluded":True,"appliesPer":"charging session"}
          ],
          "ratePolicy":"public",
          "source":{"publisher":"INDIGO Neo Belgium","url":SOURCE_URL,"retrieved":"2026-09-29"}
        })
payload={
 "country":"BE","operator":"INDIGO","asOf":"2026-09-29",
 "scope":"public charging tariff in INDIGO Belgium car parks",
 "count":len(entries),"entries":entries,
 "rules":[
   "Apply only to EVSEs from the official INDIGO Belgium DATEX II inventory.",
   "Preserve all three published tariff components separately.",
   "All published amounts are VAT included.",
   "Do not substitute INDIGO Recharge card/subscription discounts for the public tariff."
 ]
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
REP.parent.mkdir(parents=True,exist_ok=True)
REP.write_text(json.dumps({
 "country":"BE","operator":"INDIGO","sites":d.get("sites"),"evses":d.get("evses"),
 "pricedEvses":len(entries),"coveragePct":round(len(entries)/(d.get("evses") or 1)*100,2),
 "tariff":{"perKWh":0.55,"perMinute":0.013,"perSession":0.79,"currency":"EUR","taxIncluded":True},
 "source":SOURCE_URL
},ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"sites":d.get("sites"),"evses":d.get("evses"),"pricedEvses":len(entries)},indent=2))
