#!/usr/bin/env python3
import gzip,json
from pathlib import Path

TARGETS={"Gabriels","Shell Recharge","IONITY","Sowalwatt","recticel","VIR"}
root=Path("data/belgium/pages")
outdir=Path("reports/belgium"); outdir.mkdir(parents=True,exist_ok=True)
out={k:[] for k in TARGETS}

for fp in sorted(root.glob("nap-belgium-*.json.gz")):
    with gzip.open(fp,"rt",encoding="utf-8") as f:
        can=json.load(f)
    for loc in can.get("locations") or []:
        op=str(loc.get("operator") or "")
        if op not in TARGETS: continue
        for st in loc.get("stations") or []:
            for ev in st.get("evses") or []:
                if ev.get("prices"): continue
                out[op].append({
                    "page":fp.name,
                    "locationId":loc.get("id"),
                    "brand":loc.get("brand"),
                    "operator":op,
                    "address":loc.get("address"),
                    "city":loc.get("city"),
                    "postcode":loc.get("postcode"),
                    "latitude":loc.get("latitude"),
                    "longitude":loc.get("longitude"),
                    "stationId":st.get("id"),
                    "evseId":ev.get("id"),
                    "externalIdentifiers":ev.get("externalIdentifiers") or [],
                    "status":ev.get("status"),
                    "currentType":ev.get("currentType"),
                    "powerW":ev.get("availableChargingPowerW") or [],
                    "connectors":ev.get("connectors") or [],
                })

payload={"targets":{op:{"count":len(rows),"items":rows} for op,rows in sorted(out.items())}}
(outdir/"belgium-residual-unpriced-detail-v2-2026-09-28.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({op:len(rows) for op,rows in sorted(out.items())},indent=2))
