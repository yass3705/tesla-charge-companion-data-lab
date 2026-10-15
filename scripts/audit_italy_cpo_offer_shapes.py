#!/usr/bin/env python3
"""Inventory exact ID, connector and tariff fields in Italian CPO input files.

Diagnostic only: no station matching, pricing inference or production publication.
"""
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FILES=[
"data/national/allego_direct_stations_italy_20260925.json.gz",
"data/national/atlante_direct_stations_italy_latest.json.gz",
"data/national/ewiva_pos_direct_italy_candidate.json.gz",
"data/national/freetox_direct_stations_italy.json.gz",
"data/national/ionity_direct_stations_italy.json.gz",
"data/national/neogy_alperia_italy_v9_candidate.json.gz",
"data/national/repower_italy_v9_candidate.json.gz",
]
def sample_record(data):
    if isinstance(data,list):return data[0] if data else None
    if isinstance(data,dict):
        for k in ("stations","evses","locations","offers","items","data","records"):
            v=data.get(k)
            if isinstance(v,list) and v:return v[0]
        return data
    return None

def main():
    results=[]
    for name in FILES:
        path=ROOT/name
        row={"file":name,"exists":path.is_file()}
        if path.is_file():
            try:
                obj=json.loads(gzip.decompress(path.read_bytes()))
                sample=sample_record(obj)
                row["topLevelType"]=type(obj).__name__
                row["topLevelKeys"]=list(obj.keys())[:40] if isinstance(obj,dict) else []
                row["topLevelLength"]=len(obj)
                row["sampleKeys"]=list(sample.keys())[:45] if isinstance(sample,dict) else []
                row["containsStructuredRecord"]=isinstance(sample,dict)
            except Exception as e:
                row["error"]=str(e)[:200]
        results.append(row)
    report={"schemaVersion":1,"country":"IT","generatedAt":datetime.now(timezone.utc).isoformat(),
            "mode":"schema-inventory-only","inputs":results,"exactEvseTariffMatchesVerified":False,
            "readyForProductionSwitch":False}
    out=ROOT/"reports/migration/italy-cpo-offer-shape-20261014.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2))
    if any(not r["exists"] or "error" in r for r in results):raise SystemExit(1)

if __name__=="__main__":main()
