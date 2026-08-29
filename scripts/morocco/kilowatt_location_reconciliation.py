#!/usr/bin/env python3
"""Offline, read-only reconciliation of Kilowatt public station records.

This script does not call Kilowatt or any backend. It only reads the already
sanitized public inventory committed in this repository and measures how many
physical-location clusters result from conservative geographic thresholds.
The goal is diagnostic: understand the difference between 43 production
station records and the website headline of 38 locations without forcing a
merge rule into production.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

SRC = Path("reports/morocco/kilowatt/latest-public-station-inventory.json")
OUT = Path("artifacts/morocco-kilowatt-location-reconciliation/summary.json")
THRESHOLDS_M = [10, 20, 30, 50, 75, 100, 150, 200, 300]


def haversine_m(a: dict, b: dict) -> float:
    lat1, lon1 = math.radians(float(a["latitude"])), math.radians(float(a["longitude"]))
    lat2, lon2 = math.radians(float(b["latitude"])), math.radians(float(b["longitude"]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


def cluster(stations: list[dict], threshold_m: float) -> list[list[int]]:
    parent = list(range(len(stations)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(stations)):
        for j in range(i + 1, len(stations)):
            if haversine_m(stations[i], stations[j]) <= threshold_m:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(stations)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def safe_station(s: dict) -> dict:
    return {
        "id": s.get("id"),
        "name": s.get("name"),
        "address": s.get("address"),
        "city": s.get("city"),
        "latitude": s.get("latitude"),
        "longitude": s.get("longitude"),
    }


def main() -> None:
    data = json.loads(SRC.read_text())
    stations = [
        s for s in data.get("stations", [])
        if s.get("production_candidate") is True
        and isinstance(s.get("latitude"), (int, float))
        and isinstance(s.get("longitude"), (int, float))
    ]
    website_claim = data.get("summary", {}).get("website_location_claim")

    results = []
    exact_match_thresholds = []
    for threshold in THRESHOLDS_M:
        groups = cluster(stations, threshold)
        multi = []
        for g in groups:
            if len(g) > 1:
                members = [stations[i] for i in g]
                max_pair_distance = 0.0
                for x in range(len(members)):
                    for y in range(x + 1, len(members)):
                        max_pair_distance = max(max_pair_distance, haversine_m(members[x], members[y]))
                multi.append({
                    "size": len(g),
                    "max_pair_distance_m": round(max_pair_distance, 1),
                    "members": [safe_station(x) for x in members],
                })
        item = {
            "threshold_m": threshold,
            "cluster_count": len(groups),
            "multi_record_cluster_count": len(multi),
            "records_absorbed_by_clustering": len(stations) - len(groups),
            "matches_website_location_claim": website_claim is not None and len(groups) == website_claim,
            "multi_record_clusters": multi,
        }
        results.append(item)
        if item["matches_website_location_claim"]:
            exact_match_thresholds.append(threshold)

    report = {
        "schema_version": 1,
        "source_report": str(SRC),
        "policy": {
            "offline_only": True,
            "backend_requests_made": False,
            "sanitized_public_station_fields_only": True,
            "diagnostic_only": True,
            "no_production_merges_applied": True,
        },
        "modeling": {
            "cpo_operator": "Kilowatt",
            "site_brand": "station-specific; not inferred",
            "app_source_access_network": "Kilowatt public web map",
            "tariff_channel": "unchanged/unresolved unless native station evidence exists",
            "status_source": "Kilowatt public web map",
        },
        "summary": {
            "production_station_records": len(stations),
            "website_location_claim": website_claim,
            "thresholds_tested_m": THRESHOLDS_M,
            "exact_match_thresholds_m": exact_match_thresholds,
            "interpretation": "A threshold match is diagnostic evidence only. Do not merge station records for TCC unless the grouping is corroborated by client-side/location identifiers or native app evidence.",
        },
        "threshold_results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
