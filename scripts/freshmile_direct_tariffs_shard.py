#!/usr/bin/env python3
"""Collect one deterministic shard of the Freshmile direct tariff inventory.

The semantic parser from freshmile_direct_tariffs_v2 is imported first so it
patches the strict base collector. Each station belongs to exactly one modulo
shard. Shards are merged only after every station id is accounted for once.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import freshmile_direct_tariffs_v2  # noqa: F401 - patches base tariff parser
import freshmile_direct_tariffs as base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=base.DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--sleep-ms", type=int, default=75)
    args = parser.parse_args()

    if args.shard_count < 1:
        raise SystemExit("--shard-count must be >= 1")
    if not 0 <= args.shard_index < args.shard_count:
        raise SystemExit("--shard-index must be between 0 and shard-count-1")

    inventory = base.read_gzip_json(args.input)
    stations = list(inventory.get("stations") or [])
    selected = [station for i, station in enumerate(stations) if i % args.shard_count == args.shard_index]

    totals: dict[str, int] = {
        "stationsInInventory": len(stations),
        "chargePointsInInventory": sum(len(s.get("chargePoints") or []) for s in stations),
        "stationsSelected": len(selected),
        "requests": 0,
        "http200": 0,
        "locationMatched": 0,
        "evseMatched": 0,
        "tariffFound": 0,
        "tariffValidated": 0,
        "tariffUnparsed": 0,
        "missingLocationRef": 0,
    }

    results: list[dict[str, Any]] = []
    for index, station in enumerate(selected, 1):
        result, stats = base.process_station(station, args.sleep_ms)
        result["inventoryIndex"] = (index - 1) * args.shard_count + args.shard_index
        results.append(result)
        for key, value in stats.items():
            totals[key] += value
        if index % 25 == 0 or index == len(selected):
            print(json.dumps({
                "shard": args.shard_index,
                "progress": index,
                "selected": len(selected),
                "stats": totals,
            }, ensure_ascii=False))

    direct_ref_count = sum(1 for station in stations if base.station_location_ref(station))
    direct_ref_evse_count = sum(
        len(station.get("chargePoints") or [])
        for station in stations
        if base.station_location_ref(station)
    )

    payload = {
        "schemaVersion": "1.1.0",
        "dataset": "freshmile-direct-cpo-tariffs-france-shard",
        "generatedAt": base.now_iso(),
        "completeNationalScan": False,
        "partitionedNationalScan": True,
        "partition": {
            "strategy": "inventory_index_modulo",
            "shardCount": args.shard_count,
            "shardIndex": args.shard_index,
        },
        "method": "Freshmile public driver API exact location ref + strict EVSE custom_ref join",
        "sourceInventoryGeneratedAt": inventory.get("generatedAt"),
        "scope": inventory.get("scope"),
        "regionalNetworkAudit": inventory.get("regionalNetworkAudit"),
        "policy": {
            "nearbyStationSubstitutionAllowed": False,
            "regionalNetworksIncluded": False,
            "preferentialTariffRankableByDefault": False,
            "provisionAndAuthorizationAreChargingFees": False,
            "unparsedDescriptionRankable": False,
            "publishToTccStableAllowed": False,
        },
        "coverage": {
            "stationsWithExactFreshmileLocationRef": direct_ref_count,
            "chargePointsCoveredByExactFreshmileLocationRef": direct_ref_evse_count,
            "stationCoveragePct": round(100 * direct_ref_count / len(stations), 4) if stations else 0,
            "chargePointCoveragePct": round(100 * direct_ref_evse_count / totals["chargePointsInInventory"], 4) if totals["chargePointsInInventory"] else 0,
        },
        "stats": totals,
        "stations": results,
    }
    base.write_gzip_json(args.output, payload)
    print(json.dumps({"output": str(args.output), "partition": payload["partition"], "stats": totals}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
