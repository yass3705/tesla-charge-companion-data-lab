#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
MONTA="https://monta.imgix.net/roaming-data/monta-as-a-cpo-pricing.json"
OPS=["CH*CCI","CH*MIG","CH*SHE","CH*EPO","CH*IWB","CH*SCH","CH*AVI","CH*SOC","CH*LDL","CH*PLN","CH*AIL","CH*IOY","CH*AGR","CH*EWD","CH*EWO","CH*MMN","CH*EBS","CH*EDH","CH*EVT","CH*AMG","DE*EDH","CH*DIE","CH*HER"]
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

nat=getj(NATIONAL)
nat_by={op:set() for op in OPS}
for d in walk(nat):
    for k,v in d.items():
        if not isinstance(v,str) or "evse" not in k.lower(): continue
        for op in OPS:
            if v.startswith(op+"*E"):
                nat_by[op].add(v)

m=getj(MONTA)
rows=m.get("data",[]) if isinstance(m,dict) else m
by={}
for r in rows:
    if isinstance(r,dict) and r.get("evse_id"): by[r["evse_id"]]=r
out=[]
for op in OPS:
    n=nat_by[op]; matched=sorted(n & set(by))
    priced=[eid for eid in matched if any(by[eid].get(k) is not None for k in ("price_kw","price_min","price_start","price_idle"))]
    sample=[]
    for eid in matched[:5]:
        r=by[eid]
        sample.append({k:r.get(k) for k in ("evse_id","operator","address","max_kw","price_kw","price_min","price_start","price_idle","currency","ocpi_tariff_id")})
    out.append({
      "operatorId":op,"nationalEvseCount":len(n),"montaMatchedEvseCount":len(matched),"montaPricedEvseCount":len(priced),
      "coveragePct":round((len(priced)/len(n)*100),3) if n else 0,
      "missingCount":len(n)-len(matched),"sample":sample
    })
report={"generatedAt":datetime.now(timezone.utc).isoformat(),"source":MONTA,"operators":out}
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-monta-untreated-coverage-2026-09-28.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"operators":[{k:x[k] for k in ("operatorId","nationalEvseCount","montaMatchedEvseCount","montaPricedEvseCount","coveragePct","missingCount")} for x in out]},ensure_ascii=False,indent=2))
