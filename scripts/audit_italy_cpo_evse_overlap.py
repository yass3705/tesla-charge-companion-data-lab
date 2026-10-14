#!/usr/bin/env python3
"""Read-only inventory of Italy CPO direct offers against the PUN national EVSE set.

Discovery-only: records schemas and identifier overlap, never creates prices.
"""
import argparse
import gzip
import json
from pathlib import Path

SOURCES = [
 "allego_direct_stations_italy_20260925.json.gz",
 "atlante_direct_stations_italy_latest.json.gz",
 "ewiva_pos_direct_italy_candidate.json.gz",
 "freetox_direct_stations_italy.json.gz",
 "ionity_direct_stations_italy.json.gz",
 "neogy_alperia_italy_v9_candidate.json.gz",
 "repower_italy_v9_candidate.json.gz",
]

def read(path):
    raw=path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix==".gz" else raw)

def summarize(value, known):
    if isinstance(value, dict):
        roots={key: {"type":type(v).__name__, "count":len(v) if isinstance(v,(dict,list)) else None} for key,v in value.items()}
        collections=[(k,v) for k,v in value.items() if isinstance(v,list) and v and isinstance(v[0],dict)]
        rows=collections[0][1] if collections else []
        label=collections[0][0] if collections else None
    elif isinstance(value,list):
        roots={"$root":{"type":"list","count":len(value)}};rows=value if value and isinstance(value[0],dict) else [];label="$root"
    else:
        roots={"$root":{"type":type(value).__name__}};rows=[];label=None
    keys=sorted({key for row in rows[:100] for key in row.keys()})
    exact=set()
    fields=("evseId","evse_id","evseID","evseUid","evse_uid","uid")
    for row in rows:
        for field in fields:
            v=row.get(field)
            if isinstance(v,str) and v.strip(): exact.add(v.strip())
    return {"root":roots,"sampleCollection":label,"sampleKeys":keys,
            "rowsAtSampleCollection":len(rows),"directEvseIdentifiers":len(exact),
            "exactMatchedPUNEvse":len(exact&known),
            "notInPUN":len(exact-known),
            "status":"schema-discovery-only-not-tariff-certified"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--pun",type=Path,required=True)
    p.add_argument("--source-dir",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    pun=read(a.pun)
    known={str(x.get("evseId")).strip() for x in pun.get("evses",[]) if x.get("evseId")}
    report={"country":"IT","punEvseCount":len(known),"sources":{},"tariffParityCertified":False,"readyForProductionSwitch":False}
    for name in SOURCES:
        path=a.source_dir/name
        if not path.exists():
            report["sources"][name]={"error":"source missing"}
            continue
        try: report["sources"][name]=summarize(read(path),known)
        except Exception as error: report["sources"][name]={"error":str(error)}
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    if any("error" in s for s in report["sources"].values()): raise SystemExit(1)

if __name__=="__main__":main()
