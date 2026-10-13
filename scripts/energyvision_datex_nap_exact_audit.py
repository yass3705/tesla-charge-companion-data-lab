#!/usr/bin/env python3
"""Read-only Belgium NAP vs EnergyVision exact EVSE ID audit.

Never attach station-level EnergyVision prices during matching.
Report only aggregate counts; no proximity-only or CPO-only joins.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import re


def normal(value):
    return re.sub("[^A-Z0-9]", "", str(value or "").upper())


def plug(value):
    v = normal(value)
    if v in ("IEC62196T2", "TYPE2", "T2"):
        return "TYPE2"
    if v in ("IEC62196T2COMBO", "CCS", "CCS2", "COMBO2"):
        return "CCS"
    return "OTHER"


def distance_m(lat1, lng1, lat2, lng2):
    try:
        a,b,c,d=map(float,(lat1,lng1,lat2,lng2))
    except (ValueError, TypeError):
        return None
    radians=math.pi/180
    lat_delta=(c-a)*radians
    lng_delta=(d-b)*radians
    q=math.sin(lat_delta/2)**2 + math.cos(a*radians)*math.cos(c*radians)*math.sin(lng_delta/2)**2
    return 6371000*2*math.atan2(math.sqrt(q),math.sqrt(max(0,1-q)))


def nap_index(manifest_file: Path):
    manifest=json.loads(manifest_file.read_text())
    root=manifest_file.resolve().parents[2]  # data/belgium/manifest -> repository root
    records={}
    raw=defaultdict(set)
    normalized=defaultdict(set)
    for page in manifest["pages"]:
        path=root / page["canonicalPath"]
        if not path.is_file():
            raise FileNotFoundError(str(path))
        with gzip.open(path,"rt",encoding="utf-8") as f:
            doc=json.load(f)
        for loc in doc.get("locations",[]):
            for station in loc.get("stations",[]):
                for evse in station.get("evses",[]):
                    uid=(str(loc.get("id") or ""),str(station.get("id") or ""),str(evse.get("id") or ""))
                    if not uid[-1]:
                        continue
                    record={
                        "latitude":loc.get("latitude"),
                        "longitude":loc.get("longitude"),
                        "types":set(plug(c.get("type")) for c in evse.get("connectors",[])),
                        "powersW":set(),
                        "operator":str(station.get("operator") or loc.get("operator") or "UNKNOWN"),
                    }
                    for value in evse.get("availableChargingPowerW",[]):
                        try:record["powersW"].add(float(value))
                        except (TypeError,ValueError):pass
                    for conn in evse.get("connectors",[]):
                        try:record["powersW"].add(float(conn.get("maxPowerW")))
                        except (TypeError,ValueError):pass
                    records[uid]=record
                    ids=[evse.get("id")] + (evse.get("externalIdentifiers") or [])
                    ids+= [v for con in evse.get("connectors",[]) for v in con.get("externalIdentifiers",[])]
                    for ident in ids:
                        if not ident:continue
                        raw[str(ident)].add(uid)
                        normalized[normal(ident)].add(uid)
    return records,raw,normalized


def compare(source,records,raw_index,norm_index):
    counters=Counter()
    operators=Counter()
    hashes=[]
    seen_source_ids=set()
    for site in source["static"]["sites"]:
        for station in site["stations"]:
            for point in station["refillPoints"]:
                counters["energyvisionRefillPoints"]+=1
                source_id=point.get("sourceRefillPointId")
                if source_id in seen_source_ids:
                    counters["duplicateSourcePointId"]+=1
                    continue
                seen_source_ids.add(source_id)
                ids=[source_id]+[c.get("sourceExternalIdentifier") for c in point["connectors"]]
                ids=[v for v in ids if v]
                exact_set=set().union(*(raw_index.get(str(v),set()) for v in ids))
                unique_set=set().union(*(norm_index.get(normal(v),set()) for v in ids))
                candidates=exact_set if exact_set else unique_set
                if not candidates:
                    counters["identityUnmatched"]+=1
                    if len(hashes)<12:
                        hashes.append(hashlib.sha256(str(source_id).encode()).hexdigest()[:12])
                    continue
                if len(candidates)!=1:
                    counters["identityAmbiguous"]+=1
                    continue
                rec=records[next(iter(candidates))]
                counters["identityExact" if exact_set else "identityNormalizedUnique"]+=1
                operators[rec["operator"]]+=1
                source_types={plug(c.get("sourceConnectorType")) for c in point["connectors"]}
                if not (source_types & rec["types"]) or "OTHER" in source_types:
                    counters["connectorMismatch"]+=1
                    continue
                srcpower=[]
                for c in point["connectors"]:
                    try:srcpower.append(float(c["sourcePowerW"]))
                    except (ValueError,TypeError):pass
                if srcpower and rec["powersW"]:
                    valid=any(abs(a-b) <= (15000 if "CCS" in source_types else max(100,0.1*a))
                              for a in srcpower for b in rec["powersW"])
                    if not valid:
                        counters["powerMismatch"]+=1
                        continue
                else:
                    counters["powerUnverifiable"]+=1
                    continue
                distance=distance_m(site.get("latitude"),site.get("longitude"),rec["latitude"],rec["longitude"])
                if distance is None:
                    counters["geoUnverifiable"]+=1
                elif distance>10:
                    counters["geoBeyond10m"]+=1
                else:
                    counters["exactIdTypePowerGeo10m"]+=1
    return {
        "summary":dict(counters),
        "napMatchedOperators":dict(operators.most_common(30)),
        "unmatchedSampleHashedIds":hashes,
        "rateAssignmentMade":False,
        "reason":"Only exact/unique-normalized EVSE identity candidates were considered. No tariff or station was promoted.",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--staging",default="artifacts/energyvision-datex-stage.json.gz")
    p.add_argument("--nap-manifest",default="data/belgium/nap-belgium-manifest.json")
    p.add_argument("--output",default="reports/belgium/energyvision-nap-exact-overlap.json")
    args=p.parse_args()
    with gzip.open(args.staging,"rt",encoding="utf-8") as f: source=json.load(f)
    records,exact,norm=nap_index(Path(args.nap_manifest))
    result=compare(source,records,exact,norm)
    result.update({"country":"BE","provider":"EnergyVision",
                   "napUniqueEvses":len(records),"napPages":17,
                   "energyVisionStageSha256":hashlib.sha256(Path(args.staging).read_bytes()).hexdigest()})
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"napUniqueEvses":len(records),"source":result["summary"],
                      "rateAssignmentMade":False},ensure_ascii=False))
    assert result["summary"].get("energyvisionRefillPoints",0)>0
    return 0


if __name__=="__main__":
    raise SystemExit(main())
