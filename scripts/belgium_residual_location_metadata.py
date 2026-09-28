#!/usr/bin/env python3
import gzip,json
from pathlib import Path

TARGETS={
 "Gabriels-5","IONITY-3440","Shell Recharge-5334","Shell Recharge-5333",
 "Sowalwatt-287024","Sowalwatt-284059","Sowalwatt-306690","Sowalwatt-285357",
 "Sowalwatt-307081","Sowalwatt-286638","Sowalwatt-306691",
 "VIR-320268","VIR-339576",
 "TotalEnergies-RECT-EVER","TotalEnergies-RECT-WETT","TotalEnergies-RECT-HULS"
}
root=Path("data/belgium/pages")
outdir=Path("reports/belgium"); outdir.mkdir(parents=True,exist_ok=True)
rows=[]

def safe_scalar_subset(d):
    keep={}
    allow_tokens=("access","public","private","opening","hour","restriction","parking","address","city","postcode","country","name","brand","operator","type","status")
    for k,v in d.items():
        lk=k.lower()
        if not any(t in lk for t in allow_tokens): continue
        if isinstance(v,(str,int,float,bool)) or v is None:
            keep[k]=v
        elif isinstance(v,list) and len(v)<=30 and all(isinstance(x,(str,int,float,bool,type(None))) for x in v):
            keep[k]=v
        elif isinstance(v,dict):
            small={}
            for kk,vv in v.items():
                if isinstance(vv,(str,int,float,bool)) or vv is None:
                    small[kk]=vv
            if small: keep[k]=small
    return keep

for fp in sorted(root.glob("nap-belgium-*.json.gz")):
    with gzip.open(fp,"rt",encoding="utf-8") as f:
        can=json.load(f)
    for loc in can.get("locations") or []:
        if loc.get("id") not in TARGETS: continue
        rows.append({
          "page":fp.name,
          "locationId":loc.get("id"),
          "operator":loc.get("operator"),
          "brand":loc.get("brand"),
          "city":loc.get("city"),
          "postcode":loc.get("postcode"),
          "latitude":loc.get("latitude"),
          "longitude":loc.get("longitude"),
          "locationMetadata":safe_scalar_subset(loc),
          "stationMetadata":[
             {"id":st.get("id"),"metadata":safe_scalar_subset(st)}
             for st in (loc.get("stations") or [])
          ]
        })
payload={"count":len(rows),"locations":rows}
(outdir/"belgium-residual-location-metadata-2026-09-28.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"count":len(rows),"ids":[x["locationId"] for x in rows]},indent=2))
