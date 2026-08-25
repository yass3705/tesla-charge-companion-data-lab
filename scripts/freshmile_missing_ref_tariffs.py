#!/usr/bin/env python3
"""Recover Freshmile stations that cannot be resolved by their IRVE location ref.

Normal collection uses ``Freshmile France/<location_ref>``. Some IRVE records
lack that ref and some refs are stale. For those cases only, this script issues
a geographic Freshmile lookup and accepts a result solely when the returned EVSE
``custom_ref`` exactly matches the IRVE/OCPI EVSE id suffix. GPS proximity alone
is never sufficient.

Without ``--scan`` the script produces a small diagnostic report for stations
with no location ref. With ``--scan`` it enriches every unresolved EVSE in an
already merged national scan, covering both missing and stale location refs.
"""
from __future__ import annotations

import argparse
import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import freshmile_direct_tariffs as base
import freshmile_direct_tariffs_v2 as semantics  # patches base parser

BASE = "https://prod-driver-api.freshmile.com/charge/api/v2"
UA = "Tesla-Charge-Companion-Freshmile-Recovery/2.0 (+public-GET-only)"
DEFAULT_INPUT = Path("data/national/freshmile_direct_stations_france.json.gz")
DEFAULT_OUTPUT = Path("reports/freshmile/missing_ref_tariffs.json.gz")


def request_geo(lat: float, lon: float, attempts: int = 3) -> dict[str, Any]:
    query = urllib.parse.urlencode({
        "order_by[latitude]": lat,
        "order_by[longitude]": lon,
    })
    url = f"{BASE}/locations?{query}"
    last: dict[str, Any] = {"url": url, "status": None, "json": None}
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(2_000_000)
                return {
                    "url": url,
                    "status": response.status,
                    "json": json.loads(raw.decode("utf-8", errors="replace")),
                }
        except urllib.error.HTTPError as exc:
            raw = exc.read(128_000)
            try:
                parsed = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception:
                parsed = None
            last = {"url": url, "status": exc.code, "json": parsed}
            if exc.code not in {429, 500, 502, 503, 504}:
                return last
        except Exception as exc:
            last = {
                "url": url,
                "status": None,
                "json": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        if attempt + 1 < attempts:
            time.sleep(0.75 * (attempt + 1))
    return last


def location_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [item for item in payload["data"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def exact_matches(payload: Any, evse_id: str) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    wanted = base.target_ref_candidates(evse_id)
    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()
    for location in location_list(payload):
        for evse in location.get("evses") or []:
            if not isinstance(evse, dict):
                continue
            custom = base.norm_token(evse.get("custom_ref"))
            if custom not in wanted:
                continue
            key = (
                str(location.get("id") or location.get("ref") or ""),
                str(evse.get("id") or custom),
            )
            if key in seen:
                continue
            seen.add(key)
            matches.append((location, evse))
    return matches


def tariffs_for_evse(evse: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen = set()
    for connector in evse.get("connectors") or []:
        if not isinstance(connector, dict):
            continue
        tariff = semantics.tariff_from_connector(connector)
        if tariff is None:
            continue
        identity = (
            tariff.get("tariffId"),
            (tariff.get("connector") or {}).get("standard"),
            (tariff.get("connector") or {}).get("powerKw"),
        )
        if identity in seen:
            continue
        seen.add(identity)
        output.append(tariff)
    return output


def read(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise RuntimeError(f"{path}: expected JSON object")
    return data


def coords_for(station: dict[str, Any]) -> tuple[float | None, float | None]:
    coords = station.get("coordinates") or {}
    lat = coords.get("latitude")
    lon = coords.get("longitude")
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None


def diagnostic_missing_refs(inventory: dict[str, Any], output: Path) -> None:
    missing = [
        station for station in inventory.get("stations") or []
        if base.station_location_ref(station) is None
    ]
    results = []
    stats = {
        "stationsMissingLocationRef": len(missing),
        "requests": 0,
        "http200": 0,
        "resolvedStations": 0,
        "resolvedChargePoints": 0,
        "ambiguousChargePoints": 0,
        "unresolvedChargePoints": 0,
        "tariffFound": 0,
        "tariffSourceValidated": 0,
        "tccRankable": 0,
    }

    for station in missing:
        lat, lon = coords_for(station)
        station_out = {
            "stationId": station.get("stationId"),
            "name": station.get("name"),
            "address": station.get("address"),
            "coordinates": station.get("coordinates"),
            "chargePoints": [],
        }
        if lat is None or lon is None:
            for point in station.get("chargePoints") or []:
                station_out["chargePoints"].append({
                    "evseId": point.get("evseId"),
                    "status": "missing_coordinates",
                    "tariffs": [],
                })
                stats["unresolvedChargePoints"] += 1
            results.append(station_out)
            continue

        response = request_geo(lat, lon)
        stats["requests"] += 1
        if response.get("status") == 200:
            stats["http200"] += 1
        station_resolved = False
        for point in station.get("chargePoints") or []:
            matches = exact_matches(response.get("json"), str(point.get("evseId") or ""))
            point_out = {
                "evseId": point.get("evseId"),
                "matchCount": len(matches),
                "status": None,
                "locationId": None,
                "locationRef": None,
                "freshmileCustomRef": None,
                "tariffs": [],
            }
            if len(matches) == 1:
                location, evse = matches[0]
                point_out.update({
                    "status": "exact_custom_ref_match",
                    "locationId": location.get("id"),
                    "locationRef": location.get("ref"),
                    "freshmileCustomRef": evse.get("custom_ref"),
                    "tariffs": tariffs_for_evse(evse),
                })
                stats["resolvedChargePoints"] += 1
                station_resolved = True
                stats["tariffFound"] += len(point_out["tariffs"])
                stats["tariffSourceValidated"] += sum(bool(t.get("sourceValidated")) for t in point_out["tariffs"])
                stats["tccRankable"] += sum(bool(t.get("tccRankable")) for t in point_out["tariffs"])
            elif len(matches) > 1:
                point_out["status"] = "ambiguous_exact_custom_ref"
                stats["ambiguousChargePoints"] += 1
            else:
                point_out["status"] = "no_exact_custom_ref_match"
                stats["unresolvedChargePoints"] += 1
            station_out["chargePoints"].append(point_out)
        if station_resolved:
            stats["resolvedStations"] += 1
        results.append(station_out)

    payload = {
        "schemaVersion": "2.0.0",
        "method": "public Freshmile geographic lookup + exact EVSE custom_ref match",
        "policy": {
            "nearestLocationIsSufficient": False,
            "exactEvseCustomRefRequired": True,
            "publishToTccStableAllowed": False,
        },
        "stats": stats,
        "stations": results,
    }
    base.write_gzip_json(output, payload)
    print(json.dumps({"output": str(output), "stats": stats}, ensure_ascii=False, indent=2))


def enrich_scan(inventory: dict[str, Any], scan: dict[str, Any], output: Path) -> None:
    inventory_by_id = {
        str(station.get("stationId") or ""): station
        for station in inventory.get("stations") or []
    }
    recovery = {
        "stationsAttempted": 0,
        "http200": 0,
        "stationsWithRecoveredPoints": 0,
        "chargePointsRecovered": 0,
        "ambiguousChargePoints": 0,
        "unresolvedChargePointsAfterRecovery": 0,
    }

    for station_out in scan.get("stations") or []:
        sid = str(station_out.get("stationId") or "")
        source_station = inventory_by_id.get(sid, station_out)
        points = station_out.get("chargePoints") or []
        if station_out.get("locationId") is not None and all(bool(point.get("matched")) for point in points):
            continue

        lat, lon = coords_for(source_station)
        if lat is None or lon is None:
            continue
        response = request_geo(lat, lon)
        recovery["stationsAttempted"] += 1
        if response.get("status") == 200:
            recovery["http200"] += 1

        recovered_here = 0
        resolved_locations: list[dict[str, Any]] = []
        for point in points:
            if point.get("matched"):
                continue
            matches = exact_matches(response.get("json"), str(point.get("evseId") or ""))
            if len(matches) == 1:
                location, evse = matches[0]
                point.update({
                    "matched": True,
                    "freshmileEvseId": evse.get("id"),
                    "freshmileCustomRef": evse.get("custom_ref"),
                    "status": evse.get("status"),
                    "tariffs": tariffs_for_evse(evse),
                    "matchMethod": "geo_exact_evse_custom_ref",
                    "resolvedLocationId": location.get("id"),
                    "resolvedLocationRef": location.get("ref"),
                })
                recovered_here += 1
                resolved_locations.append(location)
            elif len(matches) > 1:
                point["recoveryStatus"] = "ambiguous_exact_custom_ref"
                recovery["ambiguousChargePoints"] += 1
            else:
                point["recoveryStatus"] = "no_exact_custom_ref_match"

        if recovered_here:
            recovery["stationsWithRecoveredPoints"] += 1
            recovery["chargePointsRecovered"] += recovered_here
            unique_locations = {
                (str(loc.get("id") or ""), str(loc.get("ref") or "")): loc
                for loc in resolved_locations
            }
            if station_out.get("locationId") is None and len(unique_locations) == 1:
                location = next(iter(unique_locations.values()))
                station_out["locationId"] = location.get("id")
                station_out["locationName"] = location.get("name")
                station_out["resolvedLocationRef"] = location.get("ref")
                station_out["locationResolution"] = "geo_exact_evse_custom_ref"

    all_points = [
        point
        for station in scan.get("stations") or []
        for point in station.get("chargePoints") or []
    ]
    all_tariffs = [
        tariff
        for point in all_points
        for tariff in point.get("tariffs") or []
    ]
    recovery["unresolvedChargePointsAfterRecovery"] = sum(not bool(point.get("matched")) for point in all_points)

    scan["schemaVersion"] = "2.0.0"
    scan["recoveryApplied"] = True
    scan["recovery"] = recovery
    policy = scan.setdefault("policy", {})
    policy["geoFallbackAllowedOnlyWithExactEvseCustomRef"] = True
    policy["nearestStationSubstitutionAllowed"] = False

    stats = scan.setdefault("stats", {})
    stats["evseMatchedFinal"] = sum(bool(point.get("matched")) for point in all_points)
    stats["tariffFoundFinal"] = len(all_tariffs)
    stats["tariffValidatedFinal"] = sum(bool(t.get("sourceValidated")) for t in all_tariffs)
    stats["tariffUnparsedFinal"] = sum(
        (t.get("components") or {}).get("status") == "unparsed"
        for t in all_tariffs
    )
    stats["tccRankableFinal"] = sum(bool(t.get("tccRankable")) for t in all_tariffs)

    quality = scan.setdefault("quality", {})
    total_points = int(stats.get("chargePointsInInventory", len(all_points)))
    quality["finalEvseMatchRatePct"] = round(100 * stats["evseMatchedFinal"] / max(1, total_points), 4)
    quality["sourceValidatedTariffRatePct"] = round(100 * stats["tariffValidatedFinal"] / max(1, stats["tariffFoundFinal"]), 4)

    base.write_gzip_json(output, scan)
    print(json.dumps({
        "output": str(output),
        "recovery": recovery,
        "finalStats": {
            "evseMatchedFinal": stats["evseMatchedFinal"],
            "tariffFoundFinal": stats["tariffFoundFinal"],
            "tariffValidatedFinal": stats["tariffValidatedFinal"],
            "tariffUnparsedFinal": stats["tariffUnparsedFinal"],
            "tccRankableFinal": stats["tccRankableFinal"],
        },
        "quality": quality,
    }, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--scan", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    inventory = read(args.input)
    if args.scan is None:
        diagnostic_missing_refs(inventory, args.output)
    else:
        enrich_scan(inventory, read(args.scan), args.output)


if __name__ == "__main__":
    main()
