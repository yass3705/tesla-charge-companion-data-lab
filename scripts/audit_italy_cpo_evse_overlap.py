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
    """Recursively discover IDs; matching is diagnostic, never tariff attribution."""
    roots = ({k: {"type": type(v).__name__,
                  "count": len(v) if isinstance(v, (dict, list)) else None}
              for k, v in value.items()} if isinstance(value, dict)
             else {"$root": {"type": type(value).__name__,
                              "count": len(value) if isinstance(value, list) else None}})
    aliases = {"evseid", "evseuid", "evse_id", "evse_uid", "evse_id_normalized", "sourceevseid"}
    # Generic 'uid' is deliberately excluded: it may identify a station, connector, or offer.
    exact = set()
    field_counts = {}
    object_count = 0
    sample_keys = set()
    stack = [value]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, dict):
            object_count += 1
            if object_count <= 100:
                sample_keys.update(str(k) for k in node)
            for key, item in node.items():
                normalized_key = str(key).replace("-", "_").lower()
                if normalized_key in aliases and isinstance(item, (str, int)):
                    identifier = str(item).strip()
                    if identifier:
                        exact.add(identifier)
                        field_counts[key] = field_counts.get(key, 0) + 1
                if isinstance(item, (list, dict)):
                    stack.append(item)
    matched = exact & known
    return {"root": roots, "sampleKeys": sorted(sample_keys),
            "objectsInspected": object_count,
            "identityFields": field_counts,
            "directEvseIdentifiers": len(exact),
            "exactMatchedPUNEvse": len(matched),
            "notInPUN": len(exact - known),
            "exactMatchRateAmongIdentified": round(len(matched) / len(exact), 6) if exact else None,
            "status": "recursive-exact-identity-discovery-not-tariff-certified",
            "caution": "Exact ID overlap does not establish CPO direct-price or power attribution"}

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
