#!/usr/bin/env python3
"""Produce immutable experimental V9-shaped Italy static tiles from PUN stations.

Never publish or claim runtime equivalence before separate EVSE/offer parity.
"""
import argparse
import gzip
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


def encode(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_gz(path, obj):
    data = gzip.compress(encode(obj), compresslevel=9, mtime=0)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def coordinates(station):
    c = station.get("coordinates") or []
    if not isinstance(c, (list, tuple)) or len(c) < 2:
        raise ValueError("missing station coordinates")
    lat, lon = float(c[0]), float(c[1])
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise ValueError("invalid station coordinates")
    return lat, lon


def build(payload, destination):
    if payload.get("country") != "IT" or payload.get("dataset") != "pun-national-italy":
        raise ValueError("not an Italy PUN dataset")
    stations = payload.get("stations") or []
    if len(stations) < 29696:
        raise ValueError("station regression against pinned Stable")
    destination.mkdir(parents=True, exist_ok=True)
    tiled = defaultdict(list)
    for station in stations:
        lat, lon = coordinates(station)
        tiled[(math.floor(lat), math.floor(lon))].append(station)
    all_sha = write_gz(destination/"all.json.gz", stations)
    tiles = []
    for (lat_tile, lon_tile), entries in sorted(tiled.items()):
        name = f"tile_{lat_tile}_{lon_tile}.json.gz"
        sha = write_gz(destination/name, entries)
        cs = [coordinates(s) for s in entries]
        tiles.append({"file":name,"count":len(entries),"minLat":min(c[0] for c in cs),"maxLat":max(c[0] for c in cs),"minLon":min(c[1] for c in cs),"maxLon":max(c[1] for c in cs),"sha256":sha})
    manifest = {"schemaVersion":4,"country":"IT","source":"PUN experimental candidate — not V9 parity certified",
                "allFile":"all.json.gz","allSha256":all_sha,"stationCount":len(stations),"tiles":tiles}
    (destination/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    return manifest


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    a=p.parse_args()
    raw=a.input.read_bytes()
    payload=json.loads(gzip.decompress(raw) if str(a.input).endswith(".gz") else raw)
    print(json.dumps({"stations":build(payload,a.out_dir)["stationCount"],"out":str(a.out_dir)}))


if __name__=="__main__":
    main()
