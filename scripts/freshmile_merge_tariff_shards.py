#!/usr/bin/env python3
"""Merge deterministic Freshmile tariff shards into one national artifact."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any

import freshmile_direct_tariffs as base

SUM_KEYS = (
    "requests",
    "http200",
    "locationMatched",
    "evseMatched",
    "tariffFound",
    "tariffValidated",
    "tariffUnparsed",
    "missingLocationRef",
)


def read(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise RuntimeError(f"{path}: expected JSON object")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    paths = sorted(args.input_dir.rglob("*.json.gz"))
    if not paths:
        raise SystemExit(f"no shard files under {args.input_dir}")

    shards = [read(path) for path in paths]
    partitions = [s.get("partition") or {} for s in shards]
    shard_counts = {int(p.get("shardCount", -1)) for p in partitions}
    if len(shard_counts) != 1:
        raise RuntimeError(f"inconsistent shard counts: {sorted(shard_counts)}")
    shard_count = next(iter(shard_counts))
    indexes = sorted(int(p.get("shardIndex", -1)) for p in partitions)
    if indexes != list(range(shard_count)):
        raise RuntimeError(f"missing/duplicate shard indexes: got {indexes}, expected 0..{shard_count - 1}")

    first = shards[0]
    expected_stations = int((first.get("stats") or {}).get("stationsInInventory", 0))
    expected_points = int((first.get("stats") or {}).get("chargePointsInInventory", 0))
    if expected_stations <= 0 or expected_points <= 0:
        raise RuntimeError("invalid national inventory counts in shard metadata")

    station_by_index: dict[int, dict[str, Any]] = {}
    station_ids: set[str] = set()
    for shard in shards:
        stats = shard.get("stats") or {}
        if int(stats.get("stationsInInventory", -1)) != expected_stations:
            raise RuntimeError("station inventory count differs across shards")
        if int(stats.get("chargePointsInInventory", -1)) != expected_points:
            raise RuntimeError("charge-point inventory count differs across shards")
        for station in shard.get("stations") or []:
            idx = int(station.get("inventoryIndex", -1))
            sid = str(station.get("stationId") or "")
            if idx < 0 or idx in station_by_index:
                raise RuntimeError(f"duplicate/invalid inventory index {idx}")
            if not sid or sid in station_ids:
                raise RuntimeError(f"duplicate/invalid station id {sid!r}")
            station_by_index[idx] = station
            station_ids.add(sid)

    if sorted(station_by_index) != list(range(expected_stations)):
        missing = sorted(set(range(expected_stations)) - set(station_by_index))
        raise RuntimeError(f"national shard coverage incomplete; missing indexes={missing[:20]}")

    stations = [station_by_index[i] for i in range(expected_stations)]
    for station in stations:
        station.pop("inventoryIndex", None)

    totals = {
        "stationsInInventory": expected_stations,
        "chargePointsInInventory": expected_points,
        "stationsSelected": expected_stations,
    }
    for key in SUM_KEYS:
        totals[key] = sum(int((s.get("stats") or {}).get(key, 0)) for s in shards)

    payload = {
        "schemaVersion": "1.2.0",
        "dataset": "freshmile-direct-cpo-tariffs-france",
        "generatedAt": base.now_iso(),
        "completeNationalScan": True,
        "partitionedNationalScan": True,
        "partitioning": {
            "strategy": "inventory_index_modulo",
            "shardCount": shard_count,
            "allShardsPresent": True,
        },
        "method": first.get("method"),
        "sourceInventoryGeneratedAt": first.get("sourceInventoryGeneratedAt"),
        "scope": first.get("scope"),
        "regionalNetworkAudit": first.get("regionalNetworkAudit"),
        "policy": first.get("policy"),
        "coverage": first.get("coverage"),
        "stats": totals,
        "quality": {
            "http200RatePct": round(100 * totals["http200"] / max(1, totals["requests"]), 4),
            "exactLocationMatchRatePct": round(100 * totals["locationMatched"] / max(1, totals["requests"]), 4),
            "evseMatchRatePct": round(100 * totals["evseMatched"] / max(1, expected_points), 4),
        },
        "stations": stations,
    }
    base.write_gzip_json(args.output, payload)
    print(json.dumps({
        "output": str(args.output),
        "partitioning": payload["partitioning"],
        "stats": totals,
        "quality": payload["quality"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
