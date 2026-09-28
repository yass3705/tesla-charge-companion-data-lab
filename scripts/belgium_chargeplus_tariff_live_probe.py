#!/usr/bin/env python3
from __future__ import annotations
import gzip,json,urllib.parse,urllib.request,urllib.error
from pathlib import Path

BASES=[
 "https://public.mycardprd.alzp.tgscloud.net/chargeplus-bff/v1/pois/tariff",
 "https://api.mycardprd.alzp.tgscloud.net/chargeplus-bff/v2/pois/tariff",
]
PAGES=Path("data/belgium/pages")
OUT=Path("reports/belgium/totalenergies")
OUT.mkdir(parents=True,exist_ok=True)

priced=[]; missing=[]
for path in sorted(PAGES.glob("nap-belgium-*.json.gz")):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        page=json.load(f)
    for loc in page.get("locations") or []:
        if loc.get("operator")!="TotalEnergies": continue
        for st in loc.get("stations") or []:
            for ev in st.get("evses") or []:
                cons=ev.get("connectors") or []
                ext=(cons[0].get("externalIdentifiers") if cons and isinstance(cons[0],dict) else None) or ev.get("externalIdentifiers") or []
                row={
                  "locationId":loc.get("id"),"stationId":st.get("id"),"evseId":ev.get("id"),
                  "externalId":ext[0] if ext else None,"city":loc.get("city"),"powerW":ev.get("availableChargingPowerW") or [],
                  "prices":ev.get("prices") or []
                }
                (priced if row["prices"] else missing).append(row)

# deterministic small sample with diversity
ps=priced[:3]
ms=[]
seen=set()
for x in missing:
    pw=max(x["powerW"]) if x["powerW"] else None
    bucket="ac" if pw and pw<=22000 else "fast" if pw and pw<=120000 else "hpc"
    if bucket in seen: continue
    seen.add(bucket); ms.append(x)
    if len(ms)>=3: break
sample=[("priced",x) for x in ps]+[("missing",x) for x in ms]

def variants(row):
    vals=[]
    for v in (row.get("externalId"),row.get("evseId"),row.get("stationId"),row.get("locationId")):
        if v and v not in vals: vals.append(v)
    ext=row.get("externalId")
    if ext:
        for v in (ext.replace("*",""),ext.upper(),ext.lower()):
            if v not in vals: vals.append(v)
    return vals

def call(base,cid):
    q=urllib.parse.urlencode({"connectorId":cid})
    url=base+"?"+q
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"tesla-charge-companion-data-lab/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            body=r.read().decode("utf-8","replace")
            return {"url":url,"status":r.status,"contentType":r.headers.get("content-type"),"body":body[:12000]}
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace")
        return {"url":url,"status":e.code,"contentType":e.headers.get("content-type"),"body":body[:12000]}
    except Exception as e:
        return {"url":url,"status":0,"error":type(e).__name__+": "+str(e)}

results=[]
for kind,row in sample:
    entry={"kind":kind,"row":row,"tests":[]}
    for base in BASES:
        for cid in variants(row):
            entry["tests"].append({"base":base,"connectorId":cid,**call(base,cid)})
    results.append(entry)

summary={}
for e in results:
    for t in e["tests"]:
        summary[str(t.get("status"))]=summary.get(str(t.get("status")),0)+1

payload={
 "purpose":"Validate Charge+ POI tariff contract against Belgian TotalEnergies connectors",
 "sampleCount":len(sample),"statusSummary":summary,"results":results,
 "notes":["Read-only GET probe.","No tariff is written to canonical data by this workflow."]
}
(OUT/"chargeplus-tariff-live-probe-2026-09-28.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"statusSummary":summary,"sample":[{"kind":k,"externalId":r.get("externalId"),"evseId":r.get("evseId")} for k,r in sample]},ensure_ascii=False,indent=2))
