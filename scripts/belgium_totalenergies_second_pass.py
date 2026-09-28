#!/usr/bin/env python3
from __future__ import annotations
import gzip, json
from collections import Counter, defaultdict
from pathlib import Path

PAGES=Path("data/belgium/pages")
OUT=Path("reports/belgium/totalenergies")
OUT.mkdir(parents=True, exist_ok=True)

priced=[]
missing=[]
site_count=0
for path in sorted(PAGES.glob("nap-belgium-*.json.gz")):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        page=json.load(f)
    for loc in page.get("locations") or []:
        if loc.get("operator")!="TotalEnergies":
            continue
        site_count+=1
        for st in loc.get("stations") or []:
            for evse in st.get("evses") or []:
                row={
                    "page":path.name,
                    "locationId":loc.get("id"),
                    "brand":loc.get("brand"),
                    "city":loc.get("city"),
                    "postcode":loc.get("postcode"),
                    "latitude":loc.get("latitude"),
                    "longitude":loc.get("longitude"),
                    "stationId":st.get("id"),
                    "evseId":evse.get("id"),
                    "externalIdentifiers":evse.get("externalIdentifiers") or [],
                    "currentType":evse.get("currentType"),
                    "powerW":evse.get("availableChargingPowerW") or [],
                    "connectors":evse.get("connectors") or [],
                    "prices":evse.get("prices") or [],
                    "status":evse.get("status"),
                }
                (priced if row["prices"] else missing).append(row)

def ext_prefix(ids):
    if not ids: return "NONE"
    s=ids[0].replace("*","-")
    parts=s.split("-")
    return "-".join(parts[:2]) if len(parts)>=2 else s[:12]

def max_power(row):
    vals=[x for x in row.get("powerW",[]) if isinstance(x,(int,float))]
    if vals: return max(vals)
    vals=[c.get("maxPowerW") for c in row.get("connectors",[]) if isinstance(c,dict) and isinstance(c.get("maxPowerW"),(int,float))]
    return max(vals) if vals else None

def bucket_power(w):
    if w is None:return "unknown"
    kw=w/1000
    if kw<=7.4:return "<=7.4kW"
    if kw<=22:return "<=22kW"
    if kw<=50:return "<=50kW"
    if kw<=150:return "<=150kW"
    if kw<=300:return "<=300kW"
    return ">300kW"

price_components=Counter()
price_families=Counter()
rate_ids=Counter()
priced_by_power=Counter()
missing_by_power=Counter()
priced_by_prefix=Counter()
missing_by_prefix=Counter()
missing_by_city=Counter()
missing_by_postcode=Counter()
missing_by_station=Counter()
priced_by_station=Counter()
currencies=Counter()
tax_flags=Counter()

for row in priced:
    priced_by_power[bucket_power(max_power(row))]+=1
    priced_by_prefix[ext_prefix(row["externalIdentifiers"])]+=1
    priced_by_station[row["stationId"]]+=1
    for p in row["prices"]:
        price_components[p.get("priceType") or "UNKNOWN"]+=1
        rate_ids[p.get("rateId") or "NONE"]+=1
        currencies[p.get("currency") or "NONE"]+=1
        tax_flags[str(p.get("taxIncluded"))]+=1
        fam=(p.get("ratePolicy"),p.get("currency"),p.get("priceType"),p.get("value"),p.get("taxIncluded"),p.get("taxRate"))
        price_families[str(fam)]+=1

for row in missing:
    missing_by_power[bucket_power(max_power(row))]+=1
    missing_by_prefix[ext_prefix(row["externalIdentifiers"])]+=1
    missing_by_city[row.get("city") or "UNKNOWN"]+=1
    missing_by_postcode[row.get("postcode") or "UNKNOWN"]+=1
    missing_by_station[row.get("stationId")]+=1

# Representative sample: deterministic diversity across power buckets and identifier prefixes.
sample=[]
seen=set()
for row in sorted(missing,key=lambda r:(bucket_power(max_power(r)),ext_prefix(r["externalIdentifiers"]),r.get("city") or "",r.get("stationId") or "",r.get("evseId") or "")):
    key=(bucket_power(max_power(row)),ext_prefix(row["externalIdentifiers"]))
    if key in seen: continue
    seen.add(key)
    sample.append(row)
    if len(sample)>=12: break

summary={
 "operator":"TotalEnergies","country":"BE","phase":"second-pass-profile",
 "sites":site_count,"evses":len(priced)+len(missing),"pricedEvses":len(priced),"missingPriceEvses":len(missing),
 "coveragePct":round(len(priced)/(len(priced)+len(missing))*100,2),
 "pricedByPower":dict(priced_by_power),"missingByPower":dict(missing_by_power),
 "pricedByPrefix":dict(priced_by_prefix),"missingByPrefix":dict(missing_by_prefix),
 "priceComponents":dict(price_components),"topPriceFamilies":[{"family":k,"count":v} for k,v in price_families.most_common(50)],
 "rateIds":[{"rateId":k,"count":v} for k,v in rate_ids.most_common(100)],
 "currencies":dict(currencies),"taxIncludedFlags":dict(tax_flags),
 "topMissingCities":[{"city":k,"count":v} for k,v in missing_by_city.most_common(100)],
 "topMissingPostcodes":[{"postcode":k,"count":v} for k,v in missing_by_postcode.most_common(100)],
 "stationCounts":{"pricedStations":len(priced_by_station),"missingStations":len(missing_by_station)},
 "representativeMissingSample":sample,
 "notes":[
   "Profile only; no tariff is inferred or copied to missing EVSEs.",
   "Representative sample is selected across power buckets and EVSE identifier prefixes for live status/API validation."
 ]
}
(OUT/"profile-2026-09-28.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(OUT/"missing-evses-2026-09-28.json").write_text(json.dumps({"count":len(missing),"items":missing},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({
 "sites":site_count,"evses":len(priced)+len(missing),"priced":len(priced),"missing":len(missing),
 "pricedByPower":dict(priced_by_power),"missingByPower":dict(missing_by_power),
 "pricedByPrefix":dict(priced_by_prefix),"missingByPrefix":dict(missing_by_prefix),
 "topPriceFamilies":summary["topPriceFamilies"][:15],
 "sample":[{"externalIdentifiers":x["externalIdentifiers"],"powerW":x["powerW"],"city":x["city"]} for x in sample]
},ensure_ascii=False,indent=2))
