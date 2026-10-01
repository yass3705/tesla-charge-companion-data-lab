#!/usr/bin/env python3
import json, sys
src, out = sys.argv[1:3]
with open(src, encoding="utf-8") as f:
    data=json.load(f)

def records(x):
    if isinstance(x,list):
        for v in x:
            if isinstance(v,dict): yield v
    elif isinstance(x,dict):
        for key in ("data","records","items","charge_points","chargePoints","pricing"):
            v=x.get(key)
            if isinstance(v,list):
                for row in v:
                    if isinstance(row,dict): yield row
                return
        for v in x.values():
            if isinstance(v,list) and v and isinstance(v[0],dict):
                for row in v: yield row

rows=list(records(data))
def val(row,*keys):
    for k in keys:
        if k in row and row[k] is not None: return row[k]
    return None

matched=[]
for r in rows:
    ev=str(val(r,"evse","evse_id","evseId","id") or "")
    op=str(val(r,"operator","operator_name","operatorName","name") or "")
    blob=json.dumps(r, ensure_ascii=False).lower()
    if ev.upper().startswith("FR*PAN") or "anyos" in op.lower() or '"fr*pan' in blob or "anyos" in blob:
        matched.append(r)

def scalar(row, names):
    for n in names:
        v=row.get(n)
        if isinstance(v,(str,int,float,bool)) or v is None:
            if n in row: return v
    return None

norm=[]
for r in matched:
    norm.append({
      "evse": scalar(r,["evse","evse_id","evseId","id"]),
      "operator": scalar(r,["operator","operator_name","operatorName","name"]),
      "country": scalar(r,["country","country_name","countryName"]),
      "address": scalar(r,["address","location","site"]),
      "kw": scalar(r,["kw","kW","power","max_power"]),
      "price_per_kwh": scalar(r,["price_per_kwh","pricePerKwh","price_kwh","priceKwh"]),
      "price_per_min": scalar(r,["price_per_min","pricePerMin","price_min"]),
      "start_fee": scalar(r,["start_fee","startFee"]),
      "parking_fee": scalar(r,["parking_fee","parkingFee"]),
      "currency": scalar(r,["currency"]),
      "tariff_id": scalar(r,["ocpi_tariff","ocpiTariff","tariff_id","tariffId"]),
      "raw": r
    })

evses=sorted({str(x["evse"]) for x in norm if x["evse"]})
sites=sorted({str(x["address"]) for x in norm if x["address"]})
tariffs=sorted({str(x["tariff_id"]) for x in norm if x["tariff_id"]})
combos={}
for x in norm:
    key=(x["price_per_kwh"],x["price_per_min"],x["start_fee"],x["parking_fee"],x["currency"],x["tariff_id"])
    combos[str(key)]=combos.get(str(key),0)+1
res={
 "source":"https://app.monta.app/roaming/monta-as-a-cpo-pricing/export/json",
 "source_record_count":len(rows),
 "matched_record_count":len(norm),
 "unique_evses":len(evses),
 "unique_sites":len(sites),
 "unique_tariff_ids":len(tariffs),
 "evses":evses,
 "sites":sites,
 "tariff_ids":tariffs,
 "tariff_combinations":combos,
 "records":norm
}
with open(out,"w",encoding="utf-8") as f:
    json.dump(res,f,ensure_ascii=False,indent=2)
print(json.dumps({k:res[k] for k in ("source_record_count","matched_record_count","unique_evses","unique_sites","unique_tariff_ids")}))

# synchronize trigger: 2026-10-01

# run trigger after workflow is on main
