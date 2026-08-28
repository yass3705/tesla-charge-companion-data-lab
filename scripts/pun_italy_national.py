#!/usr/bin/env python3
"""Build a normalized Italy-wide EV charging inventory from the official GSE PUN API.

PUN (Piattaforma Unica Nazionale) is used as the national geographic/technical
reference. The public API is accessed with unauthenticated Cognito guest
credentials and SigV4, matching the public PUN web application's access model.

Safety / modelling rules:
- EVSEs are deduplicated by the official ``evse_id``.
- Stations are grouped by PUN ``locationId`` (no fuzzy GPS grouping).
- Raw PUN status, real-time flag and publication status are preserved.
- AVAILABLE / CHARGING / RESERVED are treated as operational infrastructure;
  occupancy is retained separately so CHARGING is never treated as a fault.
- WAITING_VALIDATION_DATA remains publishable: PUN documentation says these are
  already-published points whose sensitive data changed and remain on the public
  map while GSE validates the update.
- PUN tariff values are preserved losslessly, but are NOT promoted to rankable
  TCC consumer prices until unit/consumer-price semantics are independently
  validated. This intentionally fails closed.
- Tesla Superchargers are not explicitly removed here; this is a source extract.
  Publication/fusion layers should apply TCC's dedicated Tesla-source precedence.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
from requests_aws4auth import AWS4Auth

AWS_REGION = "eu-south-1"
COGNITO_IDENTITY_POOL = "eu-south-1:e3b2ab05-2046-43dd-8ed0-c0f14c69d507"
COGNITO_ENDPOINT = f"https://cognito-identity.{AWS_REGION}.amazonaws.com/"
API_BASE = "https://api.pun.piattaformaunicanazionale.it"
MAP_SEARCH = "/v1/chargepoints/public/map/search"
GROUP = "/v1/chargepoints/group"
MAP_PAGE_SIZE = 1000
GROUP_BATCH_SIZE = 100
USER_AGENT = "tesla-charge-companion-data-lab/pun-italy-national-1.0"

# PUN public-map green statuses, per GSE PUN User Manual v5.0 (June 2025).
OPERATIONAL_STATUSES = {"AVAILABLE", "CHARGING", "RESERVED"}
EXPLICIT_NON_OPERATIONAL_STATUSES = {"OUTOFORDER", "INOPERATIVE", "BLOCKED", "REMOVED"}
OCCUPANCY_MAP = {
    "AVAILABLE": "available",
    "CHARGING": "occupied_charging",
    "RESERVED": "reserved",
    "OUTOFORDER": "unavailable",
    "INOPERATIVE": "unavailable",
    "BLOCKED": "unavailable",
    "REMOVED": "removed",
    "UNKNOWN": "unknown",
}

# Broad Italy bounding box, used only as a quality check (not as a source filter).
ITALY_LAT_MIN = 35.0
ITALY_LAT_MAX = 48.5
ITALY_LON_MIN = 5.0
ITALY_LON_MAX = 20.0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def batched(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def nonempty(value: Any) -> bool:
    return value not in (None, "", [], {})


def finite_float(value: Any) -> float | None:
    try:
        f = float(value)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def cognito_post(target: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        COGNITO_ENDPOINT,
        headers={
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": target,
            "User-Agent": USER_AGENT,
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def guest_auth() -> AWS4Auth:
    identity_id = cognito_post(
        "AWSCognitoIdentityService.GetId",
        {"IdentityPoolId": COGNITO_IDENTITY_POOL},
    )["IdentityId"]
    credentials = cognito_post(
        "AWSCognitoIdentityService.GetCredentialsForIdentity",
        {"IdentityId": identity_id},
    )["Credentials"]
    return AWS4Auth(
        credentials["AccessKeyId"],
        credentials["SecretKey"],
        AWS_REGION,
        "execute-api",
        session_token=credentials["SessionToken"],
    )


def api_post(
    auth: AWS4Auth,
    path: str,
    payload: Any,
    *,
    attempts: int = 5,
    timeout: int = 60,
) -> requests.Response:
    last: requests.Response | None = None
    for attempt in range(attempts):
        response = requests.post(
            API_BASE + path,
            auth=auth,
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            json=payload,
            timeout=timeout,
        )
        last = response
        if response.status_code not in {429, 500, 502, 503, 504}:
            return response
        time.sleep(min(8.0, 0.75 * (2**attempt)))
    assert last is not None
    return last


def enumerate_evse_ids(auth: AWS4Auth, max_evse: int | None = None) -> tuple[list[str], dict[str, Any]]:
    ids: list[str] = []
    page = 0
    total_elements = None
    total_pages = None
    map_status_counts: Counter[str] = Counter()

    while True:
        response = api_post(auth, MAP_SEARCH, {"page": page, "size": MAP_PAGE_SIZE})
        response.raise_for_status()
        payload = response.json()
        if page == 0:
            total_elements = payload.get("totalElements")
            total_pages = payload.get("totalPages")
        content = payload.get("content") or []
        for item in content:
            evse_id = str(item.get("evse_id") or "").strip()
            if evse_id:
                ids.append(evse_id)
                map_status_counts[str(item.get("status") or "UNKNOWN")] += 1
                if max_evse and len(ids) >= max_evse:
                    break
        if max_evse and len(ids) >= max_evse:
            break
        if payload.get("last", True) or not content:
            break
        page += 1

    raw_count = len(ids)
    unique_ids = list(dict.fromkeys(ids))
    meta = {
        "reportedTotalElements": total_elements,
        "reportedTotalPages": total_pages,
        "enumeratedIds": raw_count,
        "uniqueEnumeratedIds": len(unique_ids),
        "duplicateEnumerationCount": raw_count - len(unique_ids),
        "mapStatusCounts": dict(sorted(map_status_counts.items())),
    }
    return unique_ids, meta


def fetch_group(auth: AWS4Auth, ids: list[str]) -> list[dict[str, Any]]:
    response = api_post(auth, GROUP, ids)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError(f"Unexpected PUN group response type: {type(payload).__name__}")
    return [row for row in payload if isinstance(row, dict)]


def fetch_details(auth: AWS4Auth, ids: list[str], workers: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    batches = list(batched(ids, GROUP_BATCH_SIZE))
    records: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(fetch_group, auth, batch): batch for batch in batches}
        for idx, future in enumerate(as_completed(futures), 1):
            batch = futures[future]
            try:
                records.extend(future.result())
            except Exception as exc:  # report all failures; caller decides whether quality gate passes
                failed.append({
                    "firstEvseId": batch[0] if batch else None,
                    "batchSize": len(batch),
                    "error": f"{type(exc).__name__}: {exc}",
                })
            if idx % 100 == 0 or idx == len(batches):
                print(f"PUN detail progress: batches={idx}/{len(batches)} records={len(records)} failed={len(failed)}")

    return records, {
        "batchCount": len(batches),
        "failedBatchCount": len(failed),
        "failedBatches": failed[:100],
    }


def record_quality_score(row: dict[str, Any]) -> tuple[int, int, int, int]:
    location = row.get("location") if isinstance(row.get("location"), dict) else {}
    return (
        1 if row.get("publicationStatus") == "PUBLISHED" else 0,
        1 if row.get("realTime") is True else 0,
        len(row.get("connectors") or []),
        sum(1 for value in location.values() if nonempty(value)),
    )


def dedupe_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    duplicate_rows = 0
    conflicts = 0
    duplicate_ids: Counter[str] = Counter()

    for row in records:
        evse_id = str(row.get("evse_id") or "").strip()
        if not evse_id:
            continue
        if evse_id in by_id:
            duplicate_rows += 1
            duplicate_ids[evse_id] += 1
            previous = by_id[evse_id]
            fingerprint_fields = ("status", "realTime", "publicationStatus", "locationId", "businessName")
            if any(previous.get(k) != row.get(k) for k in fingerprint_fields):
                conflicts += 1
            if record_quality_score(row) > record_quality_score(previous):
                by_id[evse_id] = row
        else:
            by_id[evse_id] = row

    unique = [by_id[k] for k in sorted(by_id)]
    return unique, {
        "inputDetailRows": len(records),
        "uniqueEvseRows": len(unique),
        "duplicateDetailRows": duplicate_rows,
        "duplicateIds": len(duplicate_ids),
        "duplicateConflictRows": conflicts,
        "duplicateIdSample": sorted(duplicate_ids)[:50],
    }


def coordinates_from(row: dict[str, Any]) -> list[float] | None:
    location = row.get("location") if isinstance(row.get("location"), dict) else {}
    candidates = [location.get("coordinates"), row.get("coordinates")]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        lat = finite_float(candidate.get("latitude"))
        lon = finite_float(candidate.get("longitude"))
        if lat is None or lon is None:
            continue
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return [lat, lon]
    return None


def is_italy_coordinate(coords: list[float] | None) -> bool:
    return bool(
        coords
        and ITALY_LAT_MIN <= coords[0] <= ITALY_LAT_MAX
        and ITALY_LON_MIN <= coords[1] <= ITALY_LON_MAX
    )


def has_numeric_tariff(details: Any) -> bool:
    if not isinstance(details, dict):
        return False
    for band in ("acTariff", "dcTariff", "hpcTariff"):
        item = details.get(band)
        if not isinstance(item, dict):
            continue
        for component in ("energy", "parking", "activation", "time"):
            value = finite_float(item.get(component))
            if value is not None:
                return True
    return False


def max_connector_power_kw(connectors: list[dict[str, Any]]) -> float | None:
    powers = []
    for connector in connectors:
        watts = finite_float(connector.get("max_electric_power"))
        if watts is not None and watts >= 0:
            powers.append(watts / 1000.0)
    return max(powers) if powers else None


def normalize_connector(connector: dict[str, Any]) -> dict[str, Any]:
    watts = finite_float(connector.get("max_electric_power"))
    return {
        "connectorId": connector.get("id"),
        "standard": connector.get("standard"),
        "format": connector.get("format"),
        "powerType": connector.get("power_type"),
        "maxVoltageV": finite_float(connector.get("max_voltage")),
        "maxAmperageA": finite_float(connector.get("max_amperage")),
        "maxElectricPowerW": watts,
        "maxPowerKw": round(watts / 1000.0, 6) if watts is not None else None,
    }


def operational_state(source_status: str) -> str:
    if source_status in OPERATIONAL_STATUSES:
        return "operational"
    if source_status in EXPLICIT_NON_OPERATIONAL_STATUSES:
        return "non_operational"
    return "unknown"


def normalize_evse(row: dict[str, Any]) -> dict[str, Any]:
    location = row.get("location") if isinstance(row.get("location"), dict) else {}
    connectors_raw = [c for c in (row.get("connectors") or []) if isinstance(c, dict)]
    connectors = [normalize_connector(c) for c in connectors_raw]
    coords = coordinates_from(row)
    status = str(row.get("status") or "UNKNOWN").upper()
    tariff_details = row.get("punTariffsDetails") if isinstance(row.get("punTariffsDetails"), dict) else None
    numeric_tariff = has_numeric_tariff(tariff_details)

    return {
        "evseId": str(row.get("evse_id") or "").strip() or None,
        "stationId": str(row.get("locationId") or location.get("_id") or "").strip() or None,
        "operator": row.get("businessName"),
        "partyId": location.get("party_id"),
        "coordinates": coords,
        "coordinatesWithinItalyBounds": is_italy_coordinate(coords),
        "sourceStatus": status,
        "operationalState": operational_state(status),
        "occupancyState": OCCUPANCY_MAP.get(status, "unknown"),
        "realTime": bool(row.get("realTime")),
        "publicationStatus": row.get("publicationStatus"),
        "publicationVisible": row.get("publicationStatus") in {"PUBLISHED", "WAITING_VALIDATION_DATA"},
        "capabilities": list(row.get("capabilities") or []),
        "connectors": connectors,
        "connectorCount": len(connectors),
        "maxPowerKw": max_connector_power_kw(connectors_raw),
        "rawPunTariffsDetails": tariff_details,
        "punTariffBlockPresent": tariff_details is not None,
        "punTariffNumericValuePresent": numeric_tariff,
        "rankablePunDirectTariff": False,
        "rankablePunDirectTariffReason": "pun_tariff_unit_and_consumer_price_semantics_not_independently_validated" if numeric_tariff else "no_numeric_pun_tariff",
    }


def station_location_reference(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(rows, key=record_quality_score, reverse=True)
    for row in ranked:
        location = row.get("location")
        if isinstance(location, dict):
            return location
    return {}


def most_common_nonempty(values: Iterable[Any]) -> Any:
    vals = [value for value in values if nonempty(value)]
    if not vals:
        return None
    # Dict/list values are not expected here; stringify only for Counter safety.
    return Counter(str(v) for v in vals).most_common(1)[0][0]


def station_operational_state(evses: list[dict[str, Any]]) -> str:
    states = {str(evse.get("operationalState")) for evse in evses}
    if "operational" in states:
        return "operational"
    if states and states <= {"non_operational"}:
        return "non_operational"
    return "unknown"


def station_availability_summary(evses: list[dict[str, Any]]) -> str:
    statuses = {str(evse.get("sourceStatus")) for evse in evses}
    if "AVAILABLE" in statuses:
        return "available_now"
    if statuses & {"CHARGING", "RESERVED"}:
        return "operational_but_no_available_evse_seen"
    if statuses and statuses <= EXPLICIT_NON_OPERATIONAL_STATUSES:
        return "unavailable"
    return "unknown"


def build_stations(raw_records: list[dict[str, Any]], normalized_evses: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_by_id = {str(row.get("evse_id")): row for row in raw_records if row.get("evse_id")}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    missing_location_id = 0

    for evse in normalized_evses:
        station_id = str(evse.get("stationId") or "").strip()
        if station_id:
            key = "pun:" + station_id
        else:
            missing_location_id += 1
            coords = evse.get("coordinates") or []
            key = "fallback:" + "|".join([
                str(evse.get("operator") or ""),
                f"{coords[0]:.6f},{coords[1]:.6f}" if len(coords) >= 2 else str(evse.get("evseId") or ""),
            ])
        groups[key].append(evse)

    stations: list[dict[str, Any]] = []
    for station_key, evses in groups.items():
        raw_rows = [raw_by_id.get(str(evse.get("evseId"))) for evse in evses]
        raw_rows = [row for row in raw_rows if row]
        location = station_location_reference(raw_rows)
        coords = None
        for evse in evses:
            if evse.get("coordinates"):
                coords = evse["coordinates"]
                break
        operator = most_common_nonempty(evse.get("operator") for evse in evses)
        party_id = most_common_nonempty(evse.get("partyId") for evse in evses)
        address = location.get("address")
        city = location.get("city")
        display_name_parts = [str(operator or "PUN")]
        if nonempty(address):
            display_name_parts.append(str(address))
        elif nonempty(city):
            display_name_parts.append(str(city))

        station_id = str(evses[0].get("stationId") or "").strip() or None
        numeric_tariff_count = sum(1 for evse in evses if evse.get("punTariffNumericValuePresent"))
        realtime_count = sum(1 for evse in evses if evse.get("realTime"))
        publication_counts = Counter(str(evse.get("publicationStatus") or "UNKNOWN") for evse in evses)
        status_counts = Counter(str(evse.get("sourceStatus") or "UNKNOWN") for evse in evses)
        max_powers = [finite_float(evse.get("maxPowerKw")) for evse in evses]
        max_powers = [p for p in max_powers if p is not None]

        stations.append({
            "stationKey": station_key,
            "stationId": station_id,
            "name": " – ".join(display_name_parts),
            "operator": operator,
            "partyId": party_id,
            "address": address,
            "city": city,
            "postalCode": location.get("postal_code"),
            "region": location.get("region"),
            "province": location.get("state"),
            "country": "IT",
            "sourceCountry": location.get("country"),
            "coordinates": coords,
            "coordinatesWithinItalyBounds": is_italy_coordinate(coords),
            "parkingType": location.get("parking_type"),
            "facilities": list(location.get("facilities") or []),
            "openingTimes": location.get("opening_times"),
            "operationalState": station_operational_state(evses),
            "availabilitySummary": station_availability_summary(evses),
            "sourceStatusCounts": dict(sorted(status_counts.items())),
            "publicationStatusCounts": dict(sorted(publication_counts.items())),
            "evseCount": len(evses),
            "realTimeEvseCount": realtime_count,
            "realTimeCoveragePct": round(100 * realtime_count / len(evses), 2) if evses else 0.0,
            "maxPowerKw": max(max_powers) if max_powers else None,
            "punNumericTariffEvseCount": numeric_tariff_count,
            "rankablePunDirectTariff": False,
            "evses": sorted(evses, key=lambda x: str(x.get("evseId") or "")),
        })

    stations.sort(key=lambda s: (str(s.get("region") or ""), str(s.get("city") or ""), str(s.get("stationKey") or "")))
    return stations, {
        "stationCount": len(stations),
        "evseMissingLocationId": missing_location_id,
        "stationsUsingFallbackGrouping": sum(1 for station in stations if str(station.get("stationKey") or "").startswith("fallback:")),
    }


def build_quality_report(
    enumerate_meta: dict[str, Any],
    fetch_meta: dict[str, Any],
    dedupe_meta: dict[str, Any],
    evses: list[dict[str, Any]],
    stations: list[dict[str, Any]],
    station_meta: dict[str, Any],
) -> dict[str, Any]:
    status_counts = Counter(str(e.get("sourceStatus") or "UNKNOWN") for e in evses)
    operational_counts = Counter(str(e.get("operationalState") or "unknown") for e in evses)
    publication_counts = Counter(str(e.get("publicationStatus") or "UNKNOWN") for e in evses)
    operators = Counter(str(e.get("operator") or "UNKNOWN") for e in evses)
    realtime = sum(1 for e in evses if e.get("realTime"))
    coords = sum(1 for e in evses if e.get("coordinates"))
    coords_italy = sum(1 for e in evses if e.get("coordinatesWithinItalyBounds"))
    tariff_blocks = sum(1 for e in evses if e.get("punTariffBlockPresent"))
    numeric_tariffs = sum(1 for e in evses if e.get("punTariffNumericValuePresent"))
    published_or_waiting = sum(1 for e in evses if e.get("publicationVisible"))

    return {
        "generatedAt": now_iso(),
        "source": "GSE PUN",
        "country": "IT",
        "enumeration": enumerate_meta,
        "fetch": fetch_meta,
        "deduplication": dedupe_meta,
        "stations": station_meta,
        "coverage": {
            "uniqueEvseCount": len(evses),
            "stationCount": len(stations),
            "operatorCount": len([k for k in operators if k != "UNKNOWN"]),
            "realTimeEvseCount": realtime,
            "realTimeCoveragePct": round(100 * realtime / len(evses), 2) if evses else 0.0,
            "evseWithCoordinates": coords,
            "coordinateCoveragePct": round(100 * coords / len(evses), 2) if evses else 0.0,
            "evseWithinItalyBounds": coords_italy,
            "italyCoordinateCoveragePct": round(100 * coords_italy / len(evses), 2) if evses else 0.0,
            "publiclyVisiblePublicationStateEvseCount": published_or_waiting,
            "punTariffBlockEvseCount": tariff_blocks,
            "punTariffBlockCoveragePct": round(100 * tariff_blocks / len(evses), 2) if evses else 0.0,
            "numericPunTariffEvseCount": numeric_tariffs,
            "numericPunTariffCoveragePct": round(100 * numeric_tariffs / len(evses), 2) if evses else 0.0,
            "rankablePunDirectTariffEvseCount": 0,
        },
        "sourceStatusCounts": dict(sorted(status_counts.items())),
        "operationalStateCounts": dict(sorted(operational_counts.items())),
        "publicationStatusCounts": dict(sorted(publication_counts.items())),
        "topOperators": operators.most_common(50),
        "qualityGates": {
            "noFailedDetailBatches": fetch_meta.get("failedBatchCount") == 0,
            "uniqueEvseAbove50000": len(evses) >= 50000,
            "coordinateCoverageAbove99Pct": (coords / len(evses) >= 0.99) if evses else False,
            "stationGroupingMostlyLocationId": station_meta.get("stationsUsingFallbackGrouping", 0) <= max(10, int(len(stations) * 0.001)),
            "publicationStatesPreserved": True,
            "tariffsFailClosedUntilSemanticsValidated": True,
        },
    }


def write_outputs(payload: dict[str, Any], report: dict[str, Any], out_path: Path, report_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    out_path.write_bytes(gzip.compress(encoded, compresslevel=9, mtime=0))
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary_path = report_path.with_suffix(".md")
    coverage = report["coverage"]
    gates = report["qualityGates"]
    summary = f"""# Italy PUN national extract quality report

- Unique EVSE: **{coverage['uniqueEvseCount']:,}**
- Stations (PUN `locationId` grouping): **{coverage['stationCount']:,}**
- CPO/operators: **{coverage['operatorCount']:,}**
- Real-time EVSE: **{coverage['realTimeEvseCount']:,} ({coverage['realTimeCoveragePct']:.2f}%)**
- Coordinates: **{coverage['evseWithCoordinates']:,} ({coverage['coordinateCoveragePct']:.2f}%)**
- PUN tariff block: **{coverage['punTariffBlockEvseCount']:,} ({coverage['punTariffBlockCoveragePct']:.2f}%)**
- PUN tariff with at least one numeric component: **{coverage['numericPunTariffEvseCount']:,} ({coverage['numericPunTariffCoveragePct']:.2f}%)**
- Rankable PUN direct tariffs: **0** (fail-closed pending independent unit/consumer-price validation)
- Failed detail batches: **{report['fetch']['failedBatchCount']}**
- Duplicate detail rows removed: **{report['deduplication']['duplicateDetailRows']}**

## Quality gates

""" + "\n".join(f"- {key}: **{'PASS' if value else 'FAIL'}**" for key, value in gates.items()) + "\n"
    summary_path.write_text(summary, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/national/pun_italy_national.json.gz")
    parser.add_argument("--report", default="data/reports/pun_italy_national_report.json")
    parser.add_argument("--max-evse", type=int, default=None, help="Optional smoke-test cap")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--allow-quality-gate-failures", action="store_true")
    args = parser.parse_args()

    generated_at = now_iso()
    auth = guest_auth()
    ids, enumerate_meta = enumerate_evse_ids(auth, args.max_evse)
    print(json.dumps({"enumeration": enumerate_meta}, ensure_ascii=False))
    records, fetch_meta = fetch_details(auth, ids, args.workers)
    unique_raw, dedupe_meta = dedupe_records(records)
    evses = [normalize_evse(row) for row in unique_raw]
    stations, station_meta = build_stations(unique_raw, evses)
    report = build_quality_report(enumerate_meta, fetch_meta, dedupe_meta, evses, stations, station_meta)

    # Stable semantic fingerprint excluding volatile timestamp and full station payload.
    fingerprint_material = {
        "sourceStatusCounts": report["sourceStatusCounts"],
        "publicationStatusCounts": report["publicationStatusCounts"],
        "coverage": report["coverage"],
        "stationCount": station_meta["stationCount"],
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "pun-national-italy",
        "generatedAt": generated_at,
        "country": "IT",
        "source": {
            "authority": "GSE / MASE - Piattaforma Unica Nazionale (PUN)",
            "apiBase": API_BASE,
            "enumerationEndpoint": MAP_SEARCH,
            "detailEndpoint": GROUP,
            "access": "public Cognito guest + AWS SigV4",
            "relevantFingerprintSha256": fingerprint,
        },
        "scope": {
            "nationalReferenceInventory": True,
            "officialGeographyAndTechnicalData": True,
            "rawRealtimeStatusIncluded": True,
            "rawPunTariffsPreserved": True,
            "punTariffsRankable": False,
            "teslaSourcePrecedenceApplied": False,
            "note": "Use this dataset as Italy's national source layer. Direct CPO and eMSP tariff fusion is a separate publication step.",
        },
        "statusPolicy": {
            "operationalStatuses": sorted(OPERATIONAL_STATUSES),
            "explicitNonOperationalStatuses": sorted(EXPLICIT_NON_OPERATIONAL_STATUSES),
            "unknownStatus": "UNKNOWN",
            "occupancyPreservedSeparately": True,
        },
        "publicationPolicy": {
            "PUBLISHED": "validated_and_public",
            "WAITING_VALIDATION_DATA": "already_public_sensitive_update_waiting_gse_validation_keep_visible",
        },
        "tariffPolicy": {
            "rawField": "rawPunTariffsDetails",
            "bands": ["acTariff", "dcTariff", "hpcTariff"],
            "components": ["energy", "parking", "activation", "time"],
            "rankable": False,
            "reason": "PUN public API values are retained, but their exact units and consumer-price semantics are not independently validated by the official documentation used for this extractor.",
        },
        "counts": report["coverage"],
        "qualityGates": report["qualityGates"],
        "stations": stations,
        "evses": evses,
    }

    out_path = Path(args.out)
    report_path = Path(args.report)
    write_outputs(payload, report, out_path, report_path)
    print(json.dumps(report["coverage"], ensure_ascii=False, indent=2))
    print(json.dumps(report["qualityGates"], ensure_ascii=False, indent=2))

    failed = [name for name, passed in report["qualityGates"].items() if not passed]
    if failed and not args.allow_quality_gate_failures:
        raise SystemExit("Quality gate failures: " + ", ".join(failed))


if __name__ == "__main__":
    main()
