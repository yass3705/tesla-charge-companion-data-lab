#!/usr/bin/env python3
"""Fail-closed Italy runtime parity gate for a rebuilt national static manifest.

Inputs are read-only. Does not alter Production, PUN or tariff feeds.
"""
import argparse
import json
from pathlib import Path

REFERENCE_STATIONS = 29696
REFERENCE_TILES = 72
REFERENCE_ALL_SHA256 = "8cbeeb5daa8f4945dc7d872525991993895af5db6aaf813770c7edb726f5f752"


def verify_manifest(manifest):
    problems = []
    if manifest.get("schemaVersion") != 4:
        problems.append("manifest schema must be V9 static-tile version 4")
    if manifest.get("country") != "IT":
        problems.append("country must be IT")
    if manifest.get("allFile") != "all.json.gz":
        problems.append("allFile must remain all.json.gz")
    if not manifest.get("allSha256"):
        problems.append("national all-file SHA is missing")
    count = manifest.get("stationCount")
    if not isinstance(count, int) or count < REFERENCE_STATIONS:
        problems.append(f"station regression: {count} vs pinned Stable {REFERENCE_STATIONS}")
    tiles = manifest.get("tiles")
    if not isinstance(tiles, list) or not tiles:
        problems.append("static tiles missing")
    else:
        tile_names = [t.get("file") for t in tiles]
        if len(set(tile_names)) != len(tile_names):
            problems.append("duplicate tile names")
        if not all(t.get("sha256") and isinstance(t.get("count"), int) for t in tiles):
            problems.append("tile SHA/count missing")
        if isinstance(count, int) and sum(t.get("count", 0) for t in tiles) != count:
            problems.append("tile station-count total differs from manifest")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True, type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    manifest = json.loads(args.candidate.read_text())
    problems = verify_manifest(manifest)
    result = {
      "country": "IT",
      "baselineStableStations": REFERENCE_STATIONS,
      "baselineStableTiles": REFERENCE_TILES,
      "baselineStableAllSha256": REFERENCE_ALL_SHA256,
      "candidateStations": manifest.get("stationCount"),
      "candidateTiles": len(manifest.get("tiles", [])),
      "manifestShapePass": not problems,
      "problems": problems,
      "evseTariffParityVerified": False,
      "readyForProductionSwitch": False
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
