#!/usr/bin/env python3
"""Validate a complete REVE V9 bundle before replacing the last good copy."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verified_gzip(path, digest):
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f"SHA256 mismatch: {path}")
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def validate(root):
    station_dir = root / "spain-static"
    offer_dir = root / "spain-reve-offers"
    station_manifest = load_json(station_dir / "manifest.json")
    offer_manifest = load_json(offer_dir / "manifest.json")
    if station_manifest.get("country") != "ES" or offer_manifest.get("country") != "ES":
        raise ValueError("REVE bundle must contain Spain station and offer manifests")
    if station_manifest.get("generatedAt") != offer_manifest.get("generatedAt"):
        raise ValueError("Station and offer manifests belong to different generations")
    stations = verified_gzip(
        station_dir / station_manifest["allFile"], station_manifest["allSha256"]
    )
    if len(stations) != station_manifest["stationCount"]:
        raise ValueError("Station count differs from all.json.gz")
    for directory, manifest, total_key in (
        (station_dir, station_manifest, "stationCount"),
        (offer_dir, offer_manifest, "offerCount"),
    ):
        total = 0
        for tile in manifest["tiles"]:
            payload = verified_gzip(directory / tile["file"], tile["sha256"])
            rows = payload if directory == station_dir else payload["directOffers"]
            if len(rows) != tile["count"]:
                raise ValueError(f"Tile count mismatch: {tile['file']}")
            total += len(rows)
        if total != manifest[total_key]:
            raise ValueError(f"Manifest total mismatch: {directory}")
    return {
        "generatedAt": station_manifest["generatedAt"],
        "stations": station_manifest["stationCount"],
        "uniqueEvseIds": station_manifest["uniqueEvseIds"],
        "physicalEvseOccurrences": station_manifest["physicalEvseOccurrences"],
        "directOffers": offer_manifest["offerCount"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    candidate = validate(args.candidate)
    if args.baseline:
        baseline = validate(args.baseline)
        candidate["observedDelta"] = {field: candidate[field] - baseline[field]
                                      for field in ("stations", "uniqueEvseIds", "physicalEvseOccurrences", "directOffers")}
    print(json.dumps(candidate, sort_keys=True))


if __name__ == "__main__":
    main()
