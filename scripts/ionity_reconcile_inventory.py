#!/usr/bin/env python3
"""Reconcile a TCC/PUN IONITY inventory with live IONITY Direct connector prices."""
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path):
    raw = gzip.open(path, "rb").read() if path.suffix == ".gz" else path.read_bytes()
    return json.loads(raw.decode("utf-8"))


def distance_m(a_lat, a_lon, b_lat, b_lon):
    radius = 6_371_000.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def evse_number(evse_id: str) -> int | None:
    match = re.search(r"E\d+(\d{2})$", evse_id)
    return int(match.group(1)) if match else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pan-inventory", type=Path, required=True)
    parser.add_argument("--direct", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-distance-m", type=float, default=150.0)
    args = parser.parse_args()

    pan = load_json(args.pan_inventory)
    direct = load_json(args.direct)
    grouped = {}
    for station in pan["stations"]:
        key = (round(float(station["lat"]), 6), round(float(station["lon"]), 6))
        target = grouped.setdefault(key, {
            "stationIds": [], "names": [], "addresses": [], "lat": station["lat"], "lon": station["lon"], "evses": []
        })
        target["stationIds"].append(station["stationId"])
        target["names"].append(station["name"])
        target["addresses"].append(station["address"])
        target["evses"].extend(station["evses"])
    pan_stations = []
    for station in grouped.values():
        station["stationIds"] = sorted(set(station["stationIds"]))
        station["names"] = sorted(set(station["names"]))
        station["addresses"] = sorted(set(station["addresses"]))
        station["evses"] = sorted(set(station["evses"]))
        pan_stations.append(station)
    available = {location["uuid"]: location for location in direct["locations"]}
    matches = []
    unresolved_stations = []
    unresolved_evses = []
    resolved_evses = []

    for station in pan_stations:
        ranked = sorted(
            (
                distance_m(station["lat"], station["lon"], loc["latitude"], loc["longitude"]),
                loc["uuid"],
                loc,
            )
            for loc in available.values()
        )
        if not ranked or ranked[0][0] > args.max_distance_m:
            unresolved_stations.append({**station, "reason": "no live IONITY location within threshold"})
            unresolved_evses.extend(station["evses"])
            continue
        distance, uuid, location = ranked[0]
        del available[uuid]
        connectors_by_number = {}
        for connector in location["connectors"]:
            number = connector.get("number")
            if isinstance(number, int):
                connectors_by_number.setdefault(number, []).append(connector)

        station_rows = []
        station_unresolved = []
        used_connector_uuids = set()
        for evse_id in station["evses"]:
            number = evse_number(evse_id)
            candidates = connectors_by_number.get(number, []) if number is not None else []
            if len(candidates) != 1:
                station_unresolved.append({"evseId": evse_id, "number": number, "reason": f"connector candidates={len(candidates)}"})
                unresolved_evses.append(evse_id)
                continue
            connector = candidates[0]
            used_connector_uuids.add(connector["uuid"])
            row = {
                "evseId": evse_id,
                "connectorUuid": connector["uuid"],
                "number": connector["number"],
                "type": connector["type"],
                "powerKw": connector["powerKw"],
                "pricePerKwhEur": connector["pricePerKwhEur"],
            }
            station_rows.append(row)
            resolved_evses.append(row)

        api_only = [c for c in location["connectors"] if c["uuid"] not in used_connector_uuids]
        matches.append({
            "panStationIds": station["stationIds"],
            "panNames": station["names"],
            "ionityLocationUuid": uuid,
            "ionityName": location["name"],
            "distanceMeters": round(distance, 3),
            "panEvseCount": len(station["evses"]),
            "liveConnectorCount": len(location["connectors"]),
            "resolvedEvses": station_rows,
            "unresolvedEvses": station_unresolved,
            "apiOnlyConnectors": api_only,
        })

    price_counts = {}
    for row in resolved_evses:
        key = f"{row['pricePerKwhEur']:.2f}"
        price_counts[key] = price_counts.get(key, 0) + 1
    api_only_connectors = [c for m in matches for c in m["apiOnlyConnectors"]]
    api_only_connectors += [c for loc in available.values() for c in loc["connectors"]]
    result = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "country": "IT",
        "operator": "IONITY",
        "partyId": "IOY",
        "policy": {
            "cpoIdentifier": "IONITY_CPO",
            "tariffFamily": "IONITY DIRECT",
            "stationMatch": f"nearest coordinates <= {args.max_distance_m:g} m, one-to-one",
            "connectorMatch": "exact connector number to final two digits of IT*IOY EVSE",
            "failClosed": True,
        },
        "sources": {
            "panInventory": str(args.pan_inventory),
            "directSnapshot": str(args.direct),
            "directEndpoints": direct["source"],
            "panInventoryAsOf": "2026-08-30T11:14:39.750794Z",
        },
        "counts": {
            "panStationRows": len(pan["stations"]),
            "panLocations": len(pan_stations),
            "panEvses": len(pan["evses"]),
            "liveLocations": len(direct["locations"]),
            "liveConnectors": direct["counts"]["countryConnectorCount"],
            "matchedStations": len(matches),
            "resolvedPanEvses": len(resolved_evses),
            "unresolvedPanStations": len(unresolved_stations),
            "unresolvedPanEvses": len(unresolved_evses),
            "apiOnlyLocations": len(available),
            "apiOnlyConnectors": len(api_only_connectors),
            "resolvedPriceCounts": dict(sorted(price_counts.items())),
        },
        "matches": matches,
        "unresolvedPanStations": unresolved_stations,
        "unresolvedPanEvses": sorted(unresolved_evses),
        "apiOnlyLocations": list(available.values()),
        "apiOnlyConnectors": api_only_connectors,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
