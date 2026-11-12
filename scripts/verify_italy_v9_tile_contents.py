#!/usr/bin/env python3
"""Verify Italy V9 experimental tile bytes, station membership and geographic grouping."""
import argparse
import collections
import gzip
import hashlib
import json
import math
from pathlib import Path


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw)), hashlib.sha256(raw).hexdigest()


def verify(root):
    manifest = json.loads((root / "manifest.json").read_text())
    errors = []
    all_stations, all_digest = read(root / manifest["allFile"])
    if all_digest != manifest.get("allSha256"):
        errors.append("all.json.gz sha256 mismatch")
    national = collections.Counter(str(s[0] or "") for s in all_stations)
    tiled = collections.Counter()
    for tile in manifest.get("tiles", []):
        rows, digest = read(root / tile["file"])
        if digest != tile.get("sha256") or len(rows) != tile.get("count"):
            errors.append("tile hash/count mismatch: " + tile["file"])
        for station in rows:
            key = str(station[0] or "")
            tiled[key] += 1
            coords = station[3:5]
            if len(coords) != 2 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in coords):
                errors.append("missing or invalid coordinate for " + key)
                continue
            expected = f"tile_{math.floor(coords[0])}_{math.floor(coords[1])}.json.gz"
            if tile["file"] != expected:
                errors.append("station belongs to other geo tile: " + key)
    if "" in national or any(count != 1 for count in national.values()):
        errors.append("duplicate or missing stationKey in national inventory")
    if national != tiled:
        errors.append("national/tile station membership is not bijective")
    if any(not isinstance(s, list) or len(s) < 12 or not isinstance(s[8], list) for s in all_stations):
        errors.append("V9 compact row layout invalid")
    if len(all_stations) != manifest.get("stationCount"):
        errors.append("national station count differs from manifest")
    return {"country":"IT","stations":len(all_stations),"tiles":len(manifest.get("tiles", [])),
            "stationMembershipExact":national == tiled,"errors":errors,
            "runtimePayloadParityVerified":False,"readyForProductionSwitch":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dir",type=Path,required=True)
    p.add_argument("--report",type=Path)
    args=p.parse_args()
    result=verify(args.dir)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    if result["errors"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()
