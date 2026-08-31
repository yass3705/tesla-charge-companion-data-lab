#!/usr/bin/env python3
"""Bounded national-scale Go Electric / NextCharge tariff attribution probe.

This probe deliberately avoids the NextCharge browser UI. It scales the method
already proven by the exact-match research using only anonymous public map read
endpoints. The public web app happens to expose those reads as POST requests;
this script hard-whitelists only `stationsGrid` and `stationConnectors` and never
calls any charge, payment, reservation, account or session mutation endpoint.

A direct-CPO tariff may be attributed only when a returned NextCharge
`uidConnector` exactly equals the numeric suffix of a PUN `ITGESE...` EVSE id.
Coordinates are used only to discover nearby candidate station ids. Publication
remains disabled regardless of batch coverage.
"""
from __future__ import annotations

import gzip
import io
import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOURCE = "https://raw.githubusercontent.com/yass3705/tesla-charge-companion-stable/refactor/unified-data-engine-v9/data/v9/italy-static/all.json.gz"
TARGET_OPERATOR = "Go Electric Stations SRLS"
GRID_ENDPOINT = "https://nextcharge.app/apps/map/apis/stationsGrid"
CONNECTORS_ENDPOINT = "https://nextcharge.app/apps/map/apis/stationConnectors"
READ_ENDPOINTS = {GRID_ENDPOINT, CONNECTORS_ENDPOINT}
REFERER = "https://nextcharge.app/map?nextcharge=only&userCountry=IT"
OWNER = "ITGES"
APP_VERSION = "6.1.4"
BBOX_DEGREES = 0.012
MAX_MATCH_DISTANCE_M = 1200.0
MAX_CANDIDATES_PER_TARGET = 8
MAX_RESPONSE_BYTES = 8_000_000
DEFAULT_LIMIT = 24
TARGET_CLASSES = ("AC_22_or_less", "DC_23_60", "DC_61_150", "HPC_over_150")
UA = "TeslaChargeCompanion-DataLab/1.0 (+bounded anonymous read-only Italy V9 validation)"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def headers() -> dict[str, str]:
    return {
        "User-Agent": UA,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "client-type": "webapp",
        "Origin": "https://nextcharge.app",
        "Referer": REFERER,
        "X-Requested-With": "XMLHttpRequest",
    }


def public_read_post(endpoint: str, form: dict[str, Any], request_log: list[dict]) -> tuple[int | None, Any, int, str | None]:
    if endpoint not in READ_ENDPOINTS:
        raise RuntimeError(f"endpoint not allowed: {endpoint}")
    if endpoint == GRID_ENDPOINT:
        if str(form.get("owner")) != OWNER or str(form.get("includeNextcharge")) != "only" or str(form.get("userCountry")) != "IT":
            raise RuntimeError("stationsGrid payload outside bounded Go Electric scope")
    elif endpoint == CONNECTORS_ENDPOINT:
        if not str(form.get("idStation") or "").strip() or str(form.get("reservable")) != "0":
            raise RuntimeError("stationConnectors payload outside read-only scope")

    encoded = urllib.parse.urlencode(form).encode("utf-8")
    request_log.append({
        "method": "POST",
        "endpoint": endpoint,
        "readOnly": True,
        "form": {k: v for k, v in form.items() if k not in {"latSW", "latNE", "lonSW", "lonNE"}},
    })
    req = urllib.request.Request(endpoint, data=encoded, method="POST", headers=headers())
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise RuntimeError("response exceeds bounded safety limit")
            try:
                payload: Any = json.loads(raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace"))
            except Exception as exc:
                return response.status, None, len(raw), f"json_decode:{type(exc).__name__}"
            return response.status, payload, len(raw), None
    except urllib.error.HTTPError as exc:
        raw = exc.read(MAX_RESPONSE_BYTES + 1)
        try:
            payload = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            payload = None
        return exc.code, payload, len(raw), f"HTTPError:{exc.code}"
    except Exception as exc:
        return None, None, 0, f"{type(exc).__name__}:{exc}"


def load_catalogue() -> list[list]:
    req = urllib.request.Request(SOURCE, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as response:
        raw = response.read()
    return json.loads(gzip.GzipFile(fileobj=io.BytesIO(raw)).read().decode("utf-8"))


def power_bucket(kw: float) -> str:
    if kw <= 22:
        return "AC_22_or_less"
    if kw <= 60:
        return "DC_23_60"
    if kw <= 150:
        return "DC_61_150"
    return "HPC_over_150"


def parse_go_electric(rows: list[list]) -> list[dict]:
    stations: list[dict] = []
    for row in rows:
        if len(row) < 12:
            continue
        if str(row[5]).strip() != TARGET_OPERATOR and str(row[11]).strip() != TARGET_OPERATOR:
            continue
        station_id, name, address, lat, lon, operator, _, _, configs, generated_at, status, _ = row[:12]
        evses: list[dict] = []
        for config in configs or []:
            if not isinstance(config, list) or len(config) < 4:
                continue
            try:
                kw = float(config[3])
            except (TypeError, ValueError):
                kw = 0.0
            evses.append({"evseId": str(config[0]), "kind": str(config[2]), "maxPowerKw": kw})
        try:
            flat, flon = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        station_max = max((x["maxPowerKw"] for x in evses), default=0.0)
        if not evses or station_max <= 0:
            continue
        stations.append({
            "stationId": str(station_id),
            "name": str(name),
            "address": str(address),
            "lat": flat,
            "lon": flon,
            "operator": str(operator),
            "status": str(status),
            "generatedAt": generated_at,
            "stationMaxPowerKw": station_max,
            "powerClass": power_bucket(station_max),
            "evses": evses,
        })
    return stations


def evenly_spread(rows: list[dict], count: int) -> list[dict]:
    if count <= 0 or not rows:
        return []
    ordered = sorted(rows, key=lambda x: (x["lat"], x["lon"], x["stationId"]))
    if len(ordered) <= count:
        return ordered
    if count == 1:
        return [ordered[len(ordered) // 2]]
    indices = [round(i * (len(ordered) - 1) / (count - 1)) for i in range(count)]
    return [ordered[i] for i in dict.fromkeys(indices)]


def choose_targets(stations: list[dict], limit: int) -> list[dict]:
    limit = max(4, min(limit, 24))
    groups: dict[str, list[dict]] = defaultdict(list)
    for station in stations:
        if station["status"].upper() == "OPERATIONAL":
            groups[station["powerClass"]].append(station)
    per_class = limit // len(TARGET_CLASSES)
    extra = limit % len(TARGET_CLASSES)
    selected: list[dict] = []
    for index, cls in enumerate(TARGET_CLASSES):
        selected.extend(evenly_spread(groups.get(cls, []), per_class + (1 if index < extra else 0)))
    return selected[:limit]


def as_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def station_candidates(payload: Any) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()

    def walk(node: Any, depth: int = 0) -> None:
        if depth > 8 or len(found) >= 500:
            return
        if isinstance(node, dict):
            station_id = str(node.get("idStation") or node.get("stationId") or node.get("station_id") or "").strip()
            lat = as_number(node.get("latitude", node.get("lat")))
            lon = as_number(node.get("longitude", node.get("lng", node.get("lon"))))
            if station_id and lat is not None and lon is not None and station_id not in seen:
                seen.add(station_id)
                found.append({"idStation": station_id, "lat": lat, "lon": lon})
            for value in node.values():
                walk(value, depth + 1)
        elif isinstance(node, list):
            for value in node[:2000]:
                walk(value, depth + 1)

    walk(payload)
    return found


def normalize_connectors(payload: Any) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    return data if isinstance(data, list) else []


def evse_suffix(evse_id: str) -> str:
    return evse_id.removeprefix("ITGESE")


def power_compatible(expected_kw: float, returned_kw: Any) -> bool | None:
    actual = as_number(returned_kw)
    if actual is None or expected_kw <= 0:
        return None
    return abs(actual - expected_kw) <= max(5.0, expected_kw * 0.12)


def tariff_summary(connector: dict) -> dict:
    tariff = connector.get("tariff") if isinstance(connector.get("tariff"), dict) else {}
    charge = tariff.get("charge") if isinstance(tariff.get("charge"), dict) else {}
    prices = charge.get("prices") if isinstance(charge.get("prices"), dict) else {}
    return {
        "currency": tariff.get("currency"),
        "prices": prices,
        "paymentRequired": charge.get("paymentRequired"),
        "preAuth": charge.get("preAuth"),
        "restrictions": charge.get("restrictions"),
    }


def probe_target(target: dict, request_log: list[dict]) -> dict:
    lat, lon = target["lat"], target["lon"]
    grid_form = {
        "lonSW": lon - BBOX_DEGREES,
        "lonNE": lon + BBOX_DEGREES,
        "latSW": lat - BBOX_DEGREES,
        "latNE": lat + BBOX_DEGREES,
        "filterIsReady": "true",
        "includeNextcharge": "only",
        "favorites": "0",
        "userCountry": "IT",
        "owner": OWNER,
        "osType": "desktop",
        "appVersion": APP_VERSION,
        "idGroupProvider": "",
    }
    grid_status, grid_payload, grid_bytes, grid_error = public_read_post(GRID_ENDPOINT, grid_form, request_log)
    candidates = station_candidates(grid_payload) if grid_status == 200 else []
    ranked: list[dict] = []
    for candidate in candidates:
        distance = haversine_m(lat, lon, candidate["lat"], candidate["lon"])
        if distance <= MAX_MATCH_DISTANCE_M:
            ranked.append({**candidate, "distanceM": round(distance, 1)})
    ranked.sort(key=lambda x: (x["distanceM"], x["idStation"]))
    ranked = ranked[:MAX_CANDIDATES_PER_TARGET]

    expected_by_suffix = {evse_suffix(x["evseId"]): x for x in target["evses"]}
    candidate_results: list[dict] = []
    for candidate in ranked:
        connector_form = {
            "idStation": candidate["idStation"],
            "reservable": "0",
            "limit": "30",
            "offset": "0",
            "osType": "desktop",
            "appVersion": APP_VERSION,
        }
        status, payload, response_bytes, error = public_read_post(CONNECTORS_ENDPOINT, connector_form, request_log)
        connectors = normalize_connectors(payload)
        exact: list[dict] = []
        for connector in connectors:
            uid = str(connector.get("uidConnector") or "")
            expected = expected_by_suffix.get(uid)
            if not expected:
                continue
            exact.append({
                "punEvseId": expected["evseId"],
                "uidConnector": uid,
                "expectedPowerKw": expected["maxPowerKw"],
                "powerMax": connector.get("powerMax"),
                "powerCompatible": power_compatible(expected["maxPowerKw"], connector.get("powerMax")),
                "status": connector.get("status"),
                "current": connector.get("current"),
                "standard": connector.get("standard"),
                "tariff": tariff_summary(connector),
            })
        candidate_results.append({
            **candidate,
            "httpStatus": status,
            "responseBytes": response_bytes,
            "error": error,
            "connectorCount": len(connectors),
            "exactMatches": exact,
        })

    exact_candidates = [x for x in candidate_results if x["exactMatches"]]
    unique_exact = len(exact_candidates) == 1
    chosen = exact_candidates[0] if unique_exact else None
    matched_suffixes = {x["uidConnector"] for x in (chosen or {}).get("exactMatches", [])}
    expected_suffixes = set(expected_by_suffix)
    return {
        "pun": target,
        "gridHttpStatus": grid_status,
        "gridResponseBytes": grid_bytes,
        "gridError": grid_error,
        "candidateCountWithinThreshold": len(ranked),
        "candidates": candidate_results,
        "exactCandidateCount": len(exact_candidates),
        "uniqueExactStationMatch": unique_exact,
        "matchedNextChargeStationId": chosen.get("idStation") if chosen else None,
        "matchedDistanceM": chosen.get("distanceM") if chosen else None,
        "exactConnectorMatches": (chosen or {}).get("exactMatches", []),
        "expectedPunEvseSuffixes": sorted(expected_suffixes),
        "unmatchedPunEvseSuffixes": sorted(expected_suffixes - matched_suffixes),
        "attributionAllowedForStation": bool(chosen),
    }


def main() -> None:
    requested_limit = int(os.environ.get("GO_ELECTRIC_BATCH_LIMIT", str(DEFAULT_LIMIT)))
    catalogue = parse_go_electric(load_catalogue())
    targets = choose_targets(catalogue, requested_limit)
    if len(targets) < 4:
        raise SystemExit(f"insufficient bounded targets: {len(targets)}")

    request_log: list[dict] = []
    results = [probe_target(target, request_log) for target in targets]
    exact_stations = [x for x in results if x.get("uniqueExactStationMatch")]
    exact_connectors = [c for x in exact_stations for c in x.get("exactConnectorMatches", [])]
    tariffed = [c for c in exact_connectors if (c.get("tariff") or {}).get("prices")]
    power_checked = [c for c in exact_connectors if c.get("powerCompatible") is not None]
    power_compatible_count = sum(c.get("powerCompatible") is True for c in power_checked)

    classes = defaultdict(lambda: {"targets": 0, "exactStations": 0, "exactConnectors": 0, "tariffedConnectors": 0})
    for result in results:
        cls = result["pun"]["powerClass"]
        classes[cls]["targets"] += 1
        if result.get("uniqueExactStationMatch"):
            classes[cls]["exactStations"] += 1
            classes[cls]["exactConnectors"] += len(result.get("exactConnectorMatches", []))
            classes[cls]["tariffedConnectors"] += sum(bool((c.get("tariff") or {}).get("prices")) for c in result.get("exactConnectorMatches", []))

    report = {
        "schemaVersion": 2,
        "generatedAt": now_iso(),
        "source": SOURCE,
        "targetOperator": TARGET_OPERATOR,
        "catalogue": {
            "goElectricStationCount": len(catalogue),
            "goElectricEvseCount": sum(len(x["evses"]) for x in catalogue),
        },
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "browserUiUsed": False,
            "boundedNationalProbe": True,
            "nationalScrape": False,
            "batchLimit": min(max(requested_limit, 4), 24),
            "allowedReadPostEndpoints": sorted(READ_ENDPOINTS),
            "exactPunEvseSuffixRequiredForAttribution": True,
            "coordinateOnlyAttributionAllowed": False,
            "chargingActionsAllowed": False,
            "paymentActionsAllowed": False,
            "reservationActionsAllowed": False,
            "accountActionsAllowed": False,
            "sessionMutationAllowed": False,
            "officialGoElectricB2CChannel": "https://nextcharge.app",
            "directCpoPublicationAllowed": False,
            "publicationReason": "bounded_batch_only_no_full_national_qa",
        },
        "summary": {
            "targetStations": len(targets),
            "queriedStations": len(results),
            "gridSuccessStations": sum(x.get("gridHttpStatus") == 200 for x in results),
            "exactMatchedStations": len(exact_stations),
            "exactStationMatchRate": round(len(exact_stations) / len(results), 4) if results else 0.0,
            "targetPunEvses": sum(len(x["pun"]["evses"]) for x in results),
            "exactConnectorMatches": len(exact_connectors),
            "tariffedExactConnectors": len(tariffed),
            "tariffCoverageOnExactConnectors": round(len(tariffed) / len(exact_connectors), 4) if exact_connectors else 0.0,
            "powerCheckedExactConnectors": len(power_checked),
            "powerCompatibleExactConnectors": power_compatible_count,
            "classBreakdown": dict(classes),
        },
        "targets": results,
        "requestAudit": {
            "requestCount": len(request_log),
            "endpoints": sorted({x["endpoint"] for x in request_log}),
            "allRequestsDeclaredReadOnly": all(x.get("readOnly") is True for x in request_log),
        },
    }
    out = Path("artifacts/go_electric_nextcharge_national_batch_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "catalogue": report["catalogue"],
        "summary": report["summary"],
        "requestAudit": report["requestAudit"],
        "publicationAllowed": report["policy"]["directCpoPublicationAllowed"],
        "matchedStations": [
            {
                "punStationId": x["pun"]["stationId"],
                "class": x["pun"]["powerClass"],
                "nextChargeStationId": x.get("matchedNextChargeStationId"),
                "distanceM": x.get("matchedDistanceM"),
                "exactConnectors": len(x.get("exactConnectorMatches", [])),
                "tariffed": sum(bool((c.get("tariff") or {}).get("prices")) for c in x.get("exactConnectorMatches", [])),
            }
            for x in exact_stations
        ],
    }, ensure_ascii=False, indent=2))

    if not exact_stations:
        raise SystemExit("bounded batch produced no exact PUN EVSE / NextCharge connector identity match")


if __name__ == "__main__":
    main()
