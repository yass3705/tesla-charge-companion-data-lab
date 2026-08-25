#!/usr/bin/env python3
"""Restore IRVE EVSE placeholders that an unresolved Freshmile station lost.

The exact-ref collector historically returned an empty ``chargePoints`` list
when the station location ref was missing or stale. That made the downstream
geo+custom_ref recovery unable to see those EVSEs. This repair step restores
only the IRVE identity/power/kind metadata, always as unmatched and with no
tariff. The recovery step may then promote a point only after an exact Freshmile
EVSE ``custom_ref`` match.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any

import freshmile_direct_tariffs as base


def read(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise RuntimeError(f"{path}: expected JSON object")
    return data


def point_placeholder(point: dict[str, Any]) -> dict[str, Any]:
    return {
        "evseId": point.get("evseId"),
        "powerKw": point.get("powerKw"),
        "kind": point.get("kind"),
        "matched": False,
        "freshmileEvseId": None,
        "freshmileCustomRef": None,
        "status": None,
        "tariffs": [],
        "recoveryStatus": "restored_from_irve_for_exact_recovery",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--scan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    inventory = read(args.inventory)
    scan = read(args.scan)
    scan_by_id = {
        str(station.get("stationId") or ""): station
        for station in scan.get("stations") or []
    }

    restored_stations = 0
    restored_points = 0
    duplicate_source_ids: list[str] = []

    for source_station in inventory.get("stations") or []:
        sid = str(source_station.get("stationId") or "")
        target = scan_by_id.get(sid)
        if target is None:
            raise RuntimeError(f"scan missing station {sid}")

        target_points = target.setdefault("chargePoints", [])
        existing_ids = {
            str(point.get("evseId") or "")
            for point in target_points
            if point.get("evseId")
        }
        station_restored = 0
        seen_source: set[str] = set()
        for source_point in source_station.get("chargePoints") or []:
            evse_id = str(source_point.get("evseId") or "")
            if not evse_id:
                raise RuntimeError(f"station {sid} has source EVSE without evseId")
            if evse_id in seen_source:
                duplicate_source_ids.append(evse_id)
                continue
            seen_source.add(evse_id)
            if evse_id in existing_ids:
                continue
            target_points.append(point_placeholder(source_point))
            existing_ids.add(evse_id)
            station_restored += 1

        if station_restored:
            restored_stations += 1
            restored_points += station_restored
            target["irveEvsePlaceholdersRestored"] = station_restored

    if duplicate_source_ids:
        raise RuntimeError(f"duplicate source EVSE ids detected: {duplicate_source_ids[:20]}")

    total_inventory_points = sum(
        len(station.get("chargePoints") or [])
        for station in inventory.get("stations") or []
    )
    total_scan_points = sum(
        len(station.get("chargePoints") or [])
        for station in scan.get("stations") or []
    )
    if total_scan_points != total_inventory_points:
        raise RuntimeError(
            f"point preservation mismatch: scan={total_scan_points}, inventory={total_inventory_points}"
        )

    scan["irveEvsePreservation"] = {
        "applied": True,
        "restoredStationCount": restored_stations,
        "restoredChargePointCount": restored_points,
        "finalChargePointCount": total_scan_points,
        "inventoryChargePointCount": total_inventory_points,
        "restoredPointsAreRankable": False,
    }
    base.write_gzip_json(args.output, scan)
    print(json.dumps({
        "output": str(args.output),
        "irveEvsePreservation": scan["irveEvsePreservation"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
