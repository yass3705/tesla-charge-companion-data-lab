#!/usr/bin/env python3
import json, sys, urllib.request, urllib.parse
src, out = sys.argv[1:3]
with open(src, encoding="utf-8") as f:
    data=json.load(f)

def records(x):
    if isinstance(x,list):
        return [v for v in x if isinstance(v,dict)]
    if isinstance(x,dict):
        for key in ("data","records","items","charge_points","chargePoints","pricing"):
            v=x.get(key)
            if isinstance(v,list):
                return [row for row in v if isinstance(row,dict)]
        for v in x.values():
            if isinstance(v,list) and v and isinstance(v[0],dict):
                return [row for row in v if isinstance(row,dict)]
    return []

rows=records(data)
matched=[]
for r in rows:
    ev=str(r.get("evse_id") or r.get("evse") or r.get("evseId") or r.get("id") or "")
    op=str(r.get("operator") or r.get("operator_name") or r.get("operatorName") or r.get("name") or "")
    if ev.upper().startswith("FR*PAN") or "anyos" in op.lower():
        matched.append(r)

evses=sorted({str(r.get("evse_id") or r.get("evse") or r.get("evseId") or "") for r in matched if (r.get("evse_id") or r.get("evse") or r.get("evseId"))})
sites=sorted({str(r.get("address") or "") for r in matched if r.get("address")})
tariffs=sorted({str(r.get("ocpi_tariff_id") or r.get("ocpi_tariff") or r.get("tariff_id") or "") for r in matched if (r.get("ocpi_tariff_id") or r.get("ocpi_tariff") or r.get("tariff_id"))})

sample_evse="FR*PAN*E5678518"
sample_url="https://app.monta.app/d/"+urllib.parse.quote(sample_evse, safe="*")
req=urllib.request.Request(sample_url, headers={"User-Agent":"Mozilla/5.0"})
sample={"evse":sample_evse,"url":sample_url}
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body=resp.read().decode("utf-8","replace")
        sample.update({
          "status":resp.status,
          "final_url":resp.geturl(),
          "body_length":len(body),
          "contains_export_price_0_275":("0.275" in body),
          "contains_private_charger":("Private charger" in body),
          "body_prefix":body[:120000]
        })
except Exception as e:
    sample["error"]=repr(e)

res={
 "source":"https://app.monta.app/roaming/monta-as-a-cpo-pricing/export/json",
 "source_record_count":len(rows),
 "matched_record_count":len(matched),
 "unique_evses":len(evses),
 "unique_sites":len(sites),
 "unique_tariff_ids":len(tariffs),
 "records":matched,
 "direct_deeplink_sample":sample
}
with open(out,"w",encoding="utf-8") as f:
    json.dump(res,f,ensure_ascii=False,indent=2)
print(json.dumps({k:res[k] for k in ("source_record_count","matched_record_count","unique_evses","unique_sites","unique_tariff_ids")}))
print(json.dumps({k:sample.get(k) for k in ("evse","status","final_url","body_length","contains_export_price_0_275","contains_private_charger","error")}))
