#!/usr/bin/env python3
import json, sys, urllib.request, urllib.parse, time
from html.parser import HTMLParser

src, out = sys.argv[1:3]
with open(src, encoding="utf-8") as fh:
    data=json.load(fh)

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

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]
    def handle_data(self,d):
        d=" ".join(d.split())
        if d: self.parts.append(d)

rows=records(data)
matched=[]
for r in rows:
    ev=str(r.get("evse_id") or r.get("evse") or r.get("evseId") or r.get("id") or "")
    op=str(r.get("operator") or r.get("operator_name") or r.get("operatorName") or r.get("name") or "")
    if ev.upper().startswith("FR*PAN") or "anyos" in op.lower():
        matched.append(r)

norm=[]
for r in matched:
    norm.append({
      "evse_id":r.get("evse_id") or r.get("evse") or r.get("evseId"),
      "operator":r.get("operator") or r.get("operator_name") or r.get("operatorName"),
      "country":r.get("country"),
      "address":r.get("address"),
      "location":r.get("location"),
      "max_kw":r.get("max_kw") or r.get("kw") or r.get("power"),
      "price_kw":r.get("price_kw") if "price_kw" in r else r.get("price_per_kwh"),
      "price_min":r.get("price_min") if "price_min" in r else r.get("price_per_min"),
      "price_start":r.get("price_start") if "price_start" in r else r.get("start_fee"),
      "price_idle":r.get("price_idle") if "price_idle" in r else r.get("parking_fee"),
      "currency":r.get("currency"),
      "ocpi_tariff_id":r.get("ocpi_tariff_id") or r.get("ocpi_tariff") or r.get("tariff_id")
    })

direct=[]
for i,r in enumerate(norm):
    ev=r["evse_id"]
    url="https://app.monta.app/d/"+urllib.parse.quote(ev, safe="*")
    item={"evse_id":ev,"url":url}
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=20) as resp:
            body=resp.read().decode("utf-8","replace")
            p=TextExtractor(); p.feed(body); txt=" | ".join(p.parts)
            low=txt.lower()
            item.update({
              "status":resp.status,
              "final_url":resp.geturl(),
              "private_charge_point":"private charge point" in low,
              "public_price_text_present": any(token in low for token in ["€/kwh","eur/kwh","per kwh","price"]),
              "visible_text":txt[:1500]
            })
    except Exception as e:
        item["error"]=repr(e)
    direct.append(item)
    time.sleep(0.03)

private=sum(1 for x in direct if x.get("private_charge_point"))
public=sum(1 for x in direct if x.get("status")==200 and not x.get("private_charge_point"))
errors=sum(1 for x in direct if x.get("error"))

res={
 "source":"https://app.monta.app/roaming/monta-as-a-cpo-pricing/export/json",
 "source_record_count":len(rows),
 "matched_record_count":len(norm),
 "unique_evses":len({r["evse_id"] for r in norm if r["evse_id"]}),
 "unique_sites":len({r["address"] for r in norm if r["address"]}),
 "unique_tariff_ids":len({r["ocpi_tariff_id"] for r in norm if r["ocpi_tariff_id"]}),
 "pricing_records":norm,
 "direct_deeplink_summary":{"checked":len(direct),"private":private,"non_private_http200":public,"errors":errors},
 "direct_deeplinks":direct
}
with open(out,"w",encoding="utf-8") as fh:
    json.dump(res,fh,ensure_ascii=False,indent=2)
print(json.dumps({k:res[k] for k in ("source_record_count","matched_record_count","unique_evses","unique_sites","unique_tariff_ids")}))
print(json.dumps(res["direct_deeplink_summary"]))
