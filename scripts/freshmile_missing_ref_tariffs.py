#!/usr/bin/env python3
"""Resolve the tiny Freshmile direct-CPO remainder that lacks an exact location_ref.

The normal national tariff collector uses station names of the form
``Freshmile France/<location_ref>``. A few IRVE rows do not expose that ref.
For those rows only, this script performs a geographic Freshmile location lookup
and accepts a result solely when an EVSE ``custom_ref`` exactly matches the
IRVE/OCPI EVSE suffix. Nearest-location matching is never sufficient.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import freshmile_direct_tariffs_v2 as tariffs

BASE = "https://prod-driver-api.freshmile.com/charge/api/v2"
UA = "Tesla-Charge-Companion-Freshmile-Missing-Ref/1.0 (+public-GET-only)"
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
        request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(2_000_000)
                return {"url": url, "status": response.status, "json": json.loads(raw.decode("utf-8", errors="replace"))}
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
            last = {"url": url, "status": None, "json": None, "error": f"{type(exc).__name__}: {exc}"}
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
    wanted = tariffs.target_ref_candidates(evse_id)
    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()
    for location in location_list(payload):
        for evse in location.get("evses") or []:
            if not isinstance(evse, dict):
                continue
            custom = tariffs.norm_token(evse.get("custom_ref"))
            if custom not in wanted:
                continue
            key = (str(location.get("id") or location.get("ref") or ""), str(evse.get("id") or custom))
            if key in seen:
                continue
            seen.add(key)
            matches.append((location, evse))
    return matches


def read(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    inventory = read(args.input)
    missing = [s for s in inventory.get("stations") or [] if tariffs.station_location_ref(s) is None]
    results = []
    stats = {"stationsMissingLocationRef": len(missing), "requests": 0, "http200": 0, "resolvedStations": 0, "resolvedChargePoints": 0, "ambiguousChargePoints": 0, "unresolvedChargePoints": 0, "tariffFound": 0, "tariffSourceValidated": 0, "tccRankable": 0}

    for station in missing:
        coords = station.get("coordinates") or {}
        lat = coords.get("latitude")
        lon = coords.get("longitude")
        station_out = {"stationId": station.get("stationId"), "name": station.get("name"), "address": station.get("address"), "coordinates": coords, "chargePoints": []}
        if lat is None or lon is None:
            for point in station.get("chargePoints") or []:
                station_out["chargePoints"].append({"evseId": point.get("evseId"), "status": "missing_coordinates", "tariffs": []})
                stats["unresolvedChargePoints"] += 1
            results.append(station_out)
            continue

        response = request_geo(float(lat), float(lon))
        stats["requests"] += 1
        if response.get("status") == 200:
            stats["http200"] += 1
        station_resolved = False
        for point in station.get("chargePoints") or []:
            matches = exact_matches(response.get("json"), str(point.get("evseId") or ""))
            point_out = {"evseId": point.get("evseId"), "matchCount": len(matches), "status": None, "locationId": None, "locationRef": None, "freshmileCustomRef": None, "tariffs": []}
            if len(matches) == 1:
                location, evse = matches[0]
                point_out["status"] = "exact_custom_ref_match"
                point_out["locationId"] = location.get("id")
                point_out["locationRef"] = location.get("ref")
                point_out["freshmileCustomRef"] = evse.get("custom_ref")
                stats["resolvedChargePoints"] += 1
                station_resolved = True
                seen = set()
                for connector in evse.get("connectors") or []:
                    if not isinstance(connector, dict):
                        continue
                    tariff = tariffs.tariff_from_connector(connector)
                    if tariff is None:
                        continue
                    identity = (tariff.get("tariffId"), (tariff.get("connector") or {}).get("standard"), (tariff.get("connector") or {}).get("powerKw"))
                    if identity in seen:
                        continue
                    seen.add(identity)
                    point_out["tariffs"].append(tariff)
                    stats["tariffFound"] += 1
                    if tariff.get("sourceValidated"):
                        stats["tariffSourceValidated"] += 1
                    if tariff.get("tccRankable"):
                        stats["tccRankable"] += 1
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
        "schemaVersion": "1.0.0",
        "method": "public Freshmile geographic lookup + exact EVSE custom_ref match",
        "policy": {"nearestLocationIsSufficient": False, "exactEvseCustomRefRequired": True, "publishToTccStableAllowed": False},
        "stats": stats,
        "stations": results,
    }
    tariffs.write_gzip_json(args.output, payload)
    print(json.dumps({"output": str(args.output), "stats": stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
