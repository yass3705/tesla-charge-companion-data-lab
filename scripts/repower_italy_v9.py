#!/usr/bin/env python3
"""Build an exact-EVSE Repower direct-payment candidate for Italy V9.

The public Recharge Around Android client exposes Repower's official API host
and anonymous OAuth flow.  This builder extracts that public client
configuration from an authentic, pinned APK, requests only the Repower Charging
Net inventory, then obtains connector-level price components from each official
location detail.

Publication is deliberately fail-closed:

* only exact PUN EVSE identifiers are emitted;
* connector UUID or deterministic external-ID matches must be unique;
* a site fallback requires an identical normalized address, at most 25 metres,
  compatible connector characteristics, one unmatched PUN EVSE and one
  official claimant;
* paid connectors require exactly one supported EUR/kWh energy component;
* free charging requires the official free flag and no price components;
* unsupported fees, missing prices and ambiguous matches remain unresolved.

No registered account, payment method or private user token is used.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import html
import json
import math
import re
import threading
import time
import unicodedata
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode, urlparse

import requests

try:
    from androguard.core.apk import APK
except ImportError as exc:  # pragma: no cover - exercised by the workflow setup
    raise SystemExit("androguard 4.1.4 is required to inspect the official APK") from exc


APP_PACKAGE = "com.repower.rechargearound"
APP_VERSION = "3.7.6"
APP_VERSION_CODE = "3399"
APK_SHA256 = "76aae9f56efad48b885b059773415816c774e72d17bd7b2c1781beeac73900d9"
APK_CERT_MD5 = "b71b42f8c94fdf58927ec0eccee8e4d3"
BASE_HOST = "api-chargearound.repower.com"
APP_STORE_URL = "https://play.google.com/store/apps/details?id=com.repower.rechargearound"
REPOWER_APP_URL = "https://www.repower.com/it/e-mobility/recharge-around"
REPOWER_NETWORK_URL = (
    "https://www.repower.com/it/e-mobility/network-di-ricarica/repower-charging-net"
)
NETWORK_ID = "4d523120-f7c9-ec11-8103-005056b948ae"
OPERATOR = "Repower Vendita Italia SpA"
API_OPERATOR = "REV"
API_USER_AGENT = f"Recharge Around/{APP_VERSION} (Android)"
DETAIL_WORKERS = 20
MAX_MATCH_DISTANCE_M = 75.0
STRICT_SITE_MATCH_DISTANCE_M = 25.0


def load_gz(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError("expected object Italy consolidation payload")
    return value


def save_gz(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def apk_resource_strings(apk: APK) -> dict[str, str]:
    resources = apk.get_android_resources()
    if resources is None:
        raise RuntimeError("APK has no Android resources")
    raw = resources.get_string_resources(APP_PACKAGE, "\x00\x00")
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    values: dict[str, str] = {}
    for name, value in re.findall(r'<string name="([^"]+)">(.*?)</string>', text, flags=re.S):
        values[name] = html.unescape(value)
    return values


def inspect_apk(path: Path) -> dict[str, Any]:
    raw_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if raw_sha != APK_SHA256:
        raise RuntimeError(f"unexpected APK sha256 {raw_sha}")
    apk = APK(str(path))
    if apk.get_package() != APP_PACKAGE:
        raise RuntimeError(f"unexpected APK package {apk.get_package()}")
    if apk.get_androidversion_name() != APP_VERSION:
        raise RuntimeError(f"unexpected APK version {apk.get_androidversion_name()}")
    if str(apk.get_androidversion_code()) != APP_VERSION_CODE:
        raise RuntimeError(f"unexpected APK version code {apk.get_androidversion_code()}")
    certificates = apk.get_certificates()
    if len(certificates) != 1:
        raise RuntimeError(f"expected one APK signing certificate, got {len(certificates)}")
    cert_der = certificates[0].dump()
    cert_md5 = hashlib.md5(cert_der).hexdigest()  # nosec: identity fingerprint, not crypto use
    if cert_md5 != APK_CERT_MD5:
        raise RuntimeError(f"unexpected APK certificate fingerprint {cert_md5}")
    strings = apk_resource_strings(apk)
    required = {"base_url", "base_url_auth", "client_id", "client_secret"}
    missing = sorted(required - strings.keys())
    if missing:
        raise RuntimeError(f"APK is missing required resources {missing}")
    base_url = strings["base_url"].rstrip("/")
    auth_url = strings["base_url_auth"].rstrip("/")
    if urlparse(base_url).scheme != "https" or urlparse(base_url).hostname != BASE_HOST:
        raise RuntimeError(f"unexpected API base URL host {urlparse(base_url).hostname}")
    if urlparse(auth_url).scheme != "https" or urlparse(auth_url).hostname != BASE_HOST:
        raise RuntimeError(f"unexpected auth URL host {urlparse(auth_url).hostname}")
    return {
        "apk": apk,
        "resources": strings,
        "baseUrl": base_url,
        "authUrl": auth_url,
        "apkSha256": raw_sha,
        "certificateMd5": cert_md5,
        "certificateSha256": hashlib.sha256(cert_der).hexdigest(),
        "signedV1": apk.is_signed_v1(),
        "signedV2": apk.is_signed_v2(),
        "signedV3": apk.is_signed_v3(),
    }


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, str] | None = None,
    data: dict[str, str] | None = None,
    attempts: int = 4,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = session.request(
                method,
                url,
                headers=headers,
                params=params,
                data=data,
                timeout=(15, 50),
            )
            if response.status_code in {429, 500, 502, 503, 504} and attempt + 1 < attempts:
                time.sleep(min(6.0, 0.75 * (2**attempt)))
                continue
            response.raise_for_status()
            value = response.json()
            if not isinstance(value, dict):
                raise RuntimeError(f"expected JSON object from {urlparse(url).path}")
            return value
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(min(6.0, 0.75 * (2**attempt)))
                continue
    raise RuntimeError(f"official Repower API request failed for {urlparse(url).path}: {last_error}")


def anonymous_token(apk_info: dict[str, Any]) -> tuple[str, int]:
    resources = apk_info["resources"]
    payload = {
        "grant_type": "anonymous",
        "client_id": resources["client_id"],
        "client_secret": resources["client_secret"],
        "mobile_code": str(uuid.uuid4()),
        "scope": "offline_access",
        "app_version": APP_VERSION,
        "platform": "android",
    }
    with requests.Session() as session:
        value = request_json(
            session,
            "POST",
            apk_info["authUrl"] + "/connect/token",
            headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": API_USER_AGENT},
            data=payload,
        )
    token = value.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("official anonymous OAuth response omitted access_token")
    return token, int(value.get("expires_in") or 0)


def api_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": "bearer " + token,
        "Content-Type": "application/json",
        "User-Agent": API_USER_AGENT,
    }


def fetch_locations(apk_info: dict[str, Any], token: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with requests.Session() as session:
        value = request_json(
            session,
            "GET",
            apk_info["baseUrl"] + "/api/location",
            headers=api_headers(token),
            params={"country": "IT", "nw_list": NETWORK_ID},
        )
    if value.get("success") is not True or value.get("code") != "SUCCESS":
        raise RuntimeError(f"Repower location query failed: {value.get('code')} {value.get('reason')}")
    data = value.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("locations"), list):
        raise RuntimeError("Repower location response has an unexpected shape")
    locations = data["locations"]
    if data.get("limit_exceeded") is True:
        raise RuntimeError("Repower location response was truncated")
    if int(data.get("count") or -1) != len(locations):
        raise RuntimeError("Repower location count does not match payload")
    if int(data.get("total_count") or -1) != len(locations):
        raise RuntimeError("Repower total location count does not match payload")
    if len({str(row.get("id")) for row in locations}) != len(locations):
        raise RuntimeError("Repower location identifiers are not unique")
    if any(row.get("operator") != API_OPERATOR for row in locations):
        raise RuntimeError("Repower network filter returned another operator")
    if any(row.get("country") != "IT" for row in locations):
        raise RuntimeError("Repower network filter returned a non-Italian location")
    return locations, value


def fetch_details(
    apk_info: dict[str, Any], token: str, locations: list[dict[str, Any]], workers: int
) -> list[dict[str, Any]]:
    local = threading.local()
    headers = api_headers(token)

    def one(location: dict[str, Any]) -> dict[str, Any]:
        if not hasattr(local, "session"):
            local.session = requests.Session()
        location_id = str(location["id"])
        value = request_json(
            local.session,
            "GET",
            apk_info["baseUrl"] + "/api/location/" + location_id,
            headers=headers,
            params={"culture": "it"},
        )
        if value.get("success") is not True or value.get("code") != "SUCCESS":
            raise RuntimeError(f"Repower detail {location_id} failed: {value.get('code')}")
        detail = value.get("data")
        if not isinstance(detail, dict) or str(detail.get("id")) != location_id:
            raise RuntimeError(f"Repower detail {location_id} has an unexpected identity")
        detail["_sourceTimestamp"] = value.get("timestamp")
        return detail

    results: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(one, row): str(row["id"]) for row in locations}
        total = len(futures)
        finished = 0
        for future in concurrent.futures.as_completed(futures):
            location_id = futures[future]
            results[location_id] = future.result()
            finished += 1
            if finished % 100 == 0 or finished == total:
                print(f"Fetched {finished}/{total} official Repower details", flush=True)
    return [results[str(row["id"])] for row in locations]


def iter_pun_evses(consolidated: dict[str, Any]) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    for station in consolidated.get("stations") or []:
        if not isinstance(station, dict):
            continue
        for evse in station.get("evses") or []:
            if isinstance(evse, dict):
                yield station, evse


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000.0 * 2.0 * math.asin(min(1.0, math.sqrt(h)))


def coordinates(value: Any) -> tuple[float, float] | None:
    if isinstance(value, dict):
        raw = (value.get("latitude"), value.get("longitude"))
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        raw = (value[0], value[1])
    else:
        return None
    try:
        result = (float(raw[0]), float(raw[1]))
    except (TypeError, ValueError):
        return None
    return result if all(math.isfinite(x) for x in result) else None


def normalized_standard(value: Any) -> str:
    text = str(value or "").upper().replace("CHADMO", "CHADEMO")
    return re.sub(r"[^A-Z0-9]", "", text)


def normalized_address(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = text.encode("ascii", errors="ignore").decode("ascii").casefold()
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text))


def current_kind(value: Any) -> str | None:
    text = str(value or "").upper()
    if text.startswith("AC"):
        return "AC"
    if text.startswith("DC"):
        return "DC"
    return None


def official_id_candidates(connector_name: str) -> set[str]:
    prefix = "IT*REV*"
    if not connector_name.startswith(prefix) or "*" not in connector_name[len(prefix) :]:
        return set()
    body = connector_name[len(prefix) :]
    evse_body = body.rsplit("*", 1)[0]
    result = {"ITREP" + evse_body, "IT*REV" + evse_body}
    if "*" in evse_body:
        result.add("IT*REV" + evse_body.rsplit("*", 1)[0])
    return result


def compatible_match(
    row: dict[str, Any],
    connector: dict[str, Any],
    detail_coord: tuple[float, float] | None,
    method: str,
    max_distance_m: float,
) -> tuple[float | None, str | None]:
    pun_evse = row["evse"]
    pun_coord = coordinates(pun_evse.get("coordinates"))
    if detail_coord is None or pun_coord is None:
        return None, "missing_coordinates"
    distance = haversine_m(detail_coord, pun_coord)
    if distance > max_distance_m:
        return None, "coordinate_distance"
    api_kind = current_kind(connector.get("power_type"))
    pun_kinds = {
        current_kind(item.get("powerType"))
        for item in pun_evse.get("connectors") or []
        if isinstance(item, dict)
    }
    if api_kind is None or api_kind not in pun_kinds:
        return None, "current_type_mismatch"
    api_standard = normalized_standard(connector.get("standard"))
    pun_standards = {
        normalized_standard(item.get("standard"))
        for item in pun_evse.get("connectors") or []
        if isinstance(item, dict)
    }
    if method != "connector_uuid" and api_standard and api_standard not in pun_standards:
        return None, "connector_standard_mismatch"
    return distance, None


def component_tariff(
    detail: dict[str, Any], connector: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None, list[dict[str, Any]]]:
    components = connector.get("price_components") or []
    if not isinstance(components, list):
        return None, "price_components_not_array", []
    if detail.get("free_charge") is True:
        if components:
            return None, "free_location_has_price_components", components
        if connector.get("needs_payment") is True:
            return None, "free_location_requires_payment", components
        return {
            "pricingType": "free",
            "energyEurPerKwh": 0.0,
            "currency": "EUR",
            "paymentMethod": "one_shot",
            "rankable": True,
            "source": REPOWER_APP_URL,
        }, None, components
    if connector.get("one_shot_enable") is not True:
        return None, "one_shot_not_enabled", components
    if connector.get("needs_payment") is not True:
        return None, "paid_location_does_not_require_payment", components
    if len(components) != 1:
        return None, "expected_exactly_one_price_component", components
    component = components[0]
    if not isinstance(component, dict):
        return None, "price_component_not_object", components
    if str(component.get("name") or "").strip().casefold() != "energia":
        return None, "unsupported_price_component_name", components
    if str(component.get("unit_of_price") or "").replace(" ", "").casefold() != "€/kwh":
        return None, "unsupported_price_component_unit", components
    if component.get("tags") not in (None, []):
        return None, "conditional_price_component_tags", components
    try:
        rate = float(component.get("value"))
    except (TypeError, ValueError):
        return None, "invalid_energy_rate", components
    if not math.isfinite(rate) or rate <= 0:
        return None, "invalid_energy_rate", components
    tariff: dict[str, Any] = {
        "pricingType": "flat",
        "energyEurPerKwh": rate,
        "currency": "EUR",
        "paymentMethod": "one_shot",
        "rankable": True,
        "source": REPOWER_APP_URL,
    }
    valid_from = component.get("valid_from")
    if isinstance(valid_from, str) and valid_from:
        tariff["validFrom"] = valid_from
    return tariff, None, components


def build_candidate(
    consolidated: dict[str, Any], details: list[dict[str, Any]], source_meta: dict[str, Any]
) -> dict[str, Any]:
    pun_rows: list[dict[str, Any]] = []
    by_evse_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_connector_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_station_id: dict[str, dict[str, Any]] = {}
    pun_station_ids: set[str] = set()
    total_pun_evses = 0
    for station, evse in iter_pun_evses(consolidated):
        total_pun_evses += 1
        if evse.get("operator") != OPERATOR:
            continue
        row = {"station": station, "evse": evse}
        pun_rows.append(row)
        station_id = str(evse.get("stationId"))
        pun_station_ids.add(station_id)
        by_evse_id[str(evse.get("evseId"))].append(row)
        station_group = by_station_id.setdefault(station_id, {"station": station, "rows": []})
        station_group["rows"].append(row)
        for connector in evse.get("connectors") or []:
            if isinstance(connector, dict) and connector.get("connectorId") is not None:
                by_connector_id[str(connector["connectorId"])].append(row)

    connector_records: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    detail_location_ids: set[str] = set()
    official_connector_names: set[str] = set()
    official_connector_count = 0
    official_free_connector_count = 0
    for detail in details:
        location_id = str(detail.get("id"))
        detail_location_ids.add(location_id)
        for evse in detail.get("evses") or []:
            if not isinstance(evse, dict):
                continue
            for connector in evse.get("connectors") or []:
                if not isinstance(connector, dict):
                    continue
                official_connector_count += 1
                if detail.get("free_charge") is True:
                    official_free_connector_count += 1
                connector_id = str(connector.get("id") or "")
                connector_name = str(connector.get("name") or "")
                if not connector_name or connector_name in official_connector_names:
                    unresolved.append({
                        "officialLocationId": location_id,
                        "officialConnectorId": connector_id,
                        "officialConnectorName": connector_name or None,
                        "reason": "missing_or_duplicate_official_connector_name",
                    })
                    continue
                official_connector_names.add(connector_name)
                connector_records.append({
                    "key": (location_id, connector_id),
                    "detail": detail,
                    "detailCoord": coordinates(detail.get("coordinates")),
                    "locationId": location_id,
                    "connectorId": connector_id,
                    "connectorName": connector_name,
                    "connector": connector,
                })

    identity_matches: dict[
        tuple[str, str], list[tuple[dict[str, Any], str, float, dict[str, Any] | None]]
    ] = {}
    identity_candidate_present: set[tuple[str, str]] = set()
    identity_rejections: dict[tuple[str, str], Counter[str]] = {}
    exact_identity_pun_ids: set[str] = set()
    for record in connector_records:
        connector = record["connector"]
        connector_id = record["connectorId"]
        connector_name = record["connectorName"]
        candidate_rows: dict[str, tuple[dict[str, Any], str]] = {}
        for row in by_connector_id.get(connector_id, []):
            candidate_rows[str(row["evse"].get("evseId"))] = (row, "connector_uuid")
        for candidate_id in official_id_candidates(connector_name):
            for row in by_evse_id.get(candidate_id, []):
                evse_id = str(row["evse"].get("evseId"))
                candidate_rows.setdefault(evse_id, (row, "external_id"))
        if candidate_rows:
            identity_candidate_present.add(record["key"])
        rejected_reasons: Counter[str] = Counter()
        accepted: list[tuple[dict[str, Any], str, float, dict[str, Any] | None]] = []
        for row, method in candidate_rows.values():
            distance, blocker = compatible_match(
                row, connector, record["detailCoord"], method, MAX_MATCH_DISTANCE_M
            )
            if blocker is not None:
                rejected_reasons[blocker] += 1
                continue
            assert distance is not None
            accepted.append((row, method, distance, None))
            exact_identity_pun_ids.add(str(row["evse"].get("evseId")))
        identity_matches[record["key"]] = accepted
        identity_rejections[record["key"]] = rejected_reasons

    strict_site_proposals: dict[
        str,
        list[
            tuple[
                tuple[str, str],
                tuple[dict[str, Any], str, float, dict[str, Any] | None],
            ]
        ],
    ] = defaultdict(list)
    site_rejections: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for record in connector_records:
        key = record["key"]
        if identity_matches[key]:
            continue
        if key in identity_candidate_present:
            site_rejections[key]["strict_site_blocked_by_identity_candidate"] += 1
            continue
        official_address = normalized_address(record["detail"].get("street"))
        if not official_address:
            site_rejections[key]["strict_site_missing_official_address"] += 1
            continue
        station_matches: list[tuple[str, dict[str, Any], list[tuple[dict[str, Any], float]]]] = []
        for station_id, group in by_station_id.items():
            station = group["station"]
            if normalized_address(station.get("address")) != official_address:
                continue
            compatible_rows: list[tuple[dict[str, Any], float]] = []
            for row in group["rows"]:
                distance, blocker = compatible_match(
                    row,
                    record["connector"],
                    record["detailCoord"],
                    "station_address_connector",
                    STRICT_SITE_MATCH_DISTANCE_M,
                )
                if blocker is None:
                    assert distance is not None
                    compatible_rows.append((row, distance))
            if compatible_rows:
                station_matches.append((station_id, station, compatible_rows))
        if len(station_matches) != 1:
            site_rejections[key][
                f"strict_site_station_candidate_count_{len(station_matches)}"
            ] += 1
            continue
        station_id, station, compatible_rows = station_matches[0]
        if len(compatible_rows) != 1:
            site_rejections[key][
                f"strict_site_evse_candidate_count_{len(compatible_rows)}"
            ] += 1
            continue
        row, distance = compatible_rows[0]
        target_evse_id = str(row["evse"].get("evseId"))
        if target_evse_id in exact_identity_pun_ids:
            site_rejections[key]["strict_site_target_has_exact_identity"] += 1
            continue
        evidence = {
            "officialStreet": record["detail"].get("street"),
            "punAddress": station.get("address"),
            "normalizedAddress": official_address,
            "addressExact": True,
            "maxDistanceMeters": STRICT_SITE_MATCH_DISTANCE_M,
            "punStationCandidateCount": 1,
            "punEvseCandidateCount": 1,
            "targetHadExactIdentity": False,
        }
        strict_site_proposals[target_evse_id].append(
            (key, (row, "station_address_connector", distance, evidence))
        )

    strict_site_matches: dict[
        tuple[str, str], tuple[dict[str, Any], str, float, dict[str, Any] | None]
    ] = {}
    strict_site_collision_targets = 0
    for target_evse_id, proposals in strict_site_proposals.items():
        if len(proposals) == 1:
            key, match = proposals[0]
            strict_site_matches[key] = match
            continue
        strict_site_collision_targets += 1
        for key, _ in proposals:
            site_rejections[key][
                f"strict_site_official_claimant_count_{len(proposals)}"
            ] += 1

    entries_by_evse: dict[str, dict[str, Any]] = {}
    match_method_counts: Counter[str] = Counter()
    rate_counts: Counter[str] = Counter()
    for record in connector_records:
        key = record["key"]
        detail = record["detail"]
        connector = record["connector"]
        location_id = record["locationId"]
        connector_id = record["connectorId"]
        connector_name = record["connectorName"]
        accepted = identity_matches[key]
        if not accepted and key in strict_site_matches:
            accepted = [strict_site_matches[key]]
        tariff, tariff_blocker, raw_components = component_tariff(detail, connector)
        if not accepted:
            rejected_reasons = identity_rejections[key].copy()
            rejected_reasons.update(site_rejections[key])
            unresolved.append({
                "officialLocationId": location_id,
                "officialConnectorId": connector_id,
                "officialConnectorName": connector_name,
                "reason": "no_safe_pun_match",
                "matchRejections": dict(sorted(rejected_reasons.items())),
                "tariffBlocker": tariff_blocker,
            })
            continue
        if tariff is None:
            unresolved.append({
                "officialLocationId": location_id,
                "officialConnectorId": connector_id,
                "officialConnectorName": connector_name,
                "reason": tariff_blocker,
                "matchedPunEvseIds": sorted(
                    str(row["evse"].get("evseId")) for row, _, _, _ in accepted
                ),
                "priceComponents": raw_components,
            })
            continue

        for row, method, distance, match_evidence in accepted:
            pun_evse = row["evse"]
            evse_id = str(pun_evse.get("evseId"))
            connector_evidence = {
                "id": connector_id,
                "name": connector_name,
                "powerKw": connector.get("power"),
                "powerType": connector.get("power_type"),
                "standard": connector.get("standard"),
            }
            entry = {
                "evseId": evse_id,
                "stationId": str(pun_evse.get("stationId")),
                "operator": OPERATOR,
                "officialLocationId": location_id,
                "officialIdentifier": detail.get("identifier"),
                "officialConnectorId": connector_id,
                "officialConnectorName": connector_name,
                "officialConnectors": [connector_evidence],
                "matchMethod": method,
                "distanceMeters": round(distance, 3),
                "powerKw": connector.get("power"),
                "powerType": connector.get("power_type"),
                "standard": connector.get("standard"),
                "freeCharge": detail.get("free_charge") is True,
                "directTariff": tariff,
            }
            if match_evidence is not None:
                entry["matchEvidence"] = match_evidence
            existing = entries_by_evse.get(evse_id)
            if existing is not None:
                same_price = existing["directTariff"] == entry["directTariff"]
                same_location = existing["officialLocationId"] == entry["officialLocationId"]
                if not (same_price and same_location):
                    raise RuntimeError(f"conflicting Repower evidence for exact EVSE {evse_id}")
                if connector_id not in {item["id"] for item in existing["officialConnectors"]}:
                    existing["officialConnectors"].append(connector_evidence)
                    existing["officialConnectors"].sort(
                        key=lambda item: (item["name"], item["id"])
                    )
                continue
            entries_by_evse[evse_id] = entry
            match_method_counts[method] += 1
            rate_counts[f"{float(tariff['energyEurPerKwh']):.6f}"] += 1

    entries = sorted(entries_by_evse.values(), key=lambda row: row["evseId"])
    published_ids = {row["evseId"] for row in entries}
    pun_ids = set(by_evse_id)
    unresolved_reasons = Counter(str(row.get("reason")) for row in unresolved)
    counts = {
        "punStations": len(consolidated.get("stations") or []),
        "punEvse": total_pun_evses,
        "repowerPunStations": len(pun_station_ids),
        "repowerPunEvse": len(pun_rows),
        "officialLocations": len(details),
        "officialConnectors": official_connector_count,
        "officialFreeConnectors": official_free_connector_count,
        "rankableDirectEvse": len(entries),
        "rankableFreeEvse": sum(row["freeCharge"] for row in entries),
        "uncoveredRepowerPunEvse": len(pun_ids - published_ids),
        "unresolvedOfficialConnectors": len(unresolved),
        "strictSiteFallbackProposedConnectors": sum(
            len(rows) for rows in strict_site_proposals.values()
        ),
        "strictSiteFallbackAcceptedConnectors": len(strict_site_matches),
        "strictSiteFallbackCollisionTargets": strict_site_collision_targets,
        "matchMethodCounts": dict(sorted(match_method_counts.items())),
        "energyRateCounts": dict(sorted(rate_counts.items())),
        "unresolvedReasonCounts": dict(sorted(unresolved_reasons.items())),
    }
    safety_gates = {
        "officialApkPinned": source_meta["apkSha256"] == APK_SHA256,
        "officialApkCertificateVerified": source_meta["certificateMd5"] == APK_CERT_MD5,
        "officialApiHostExact": source_meta["apiHost"] == BASE_HOST,
        "officialNetworkFilterExact": source_meta["networkId"] == NETWORK_ID,
        "officialInventoryComplete": len(detail_location_ids) == len(details),
        "officialConnectorNamesUnique": len(official_connector_names) == official_connector_count,
        "punSnapshotExact": counts["punStations"] == 29696 and counts["punEvse"] == 75025,
        "repowerPunScopeExact": counts["repowerPunStations"] == 982 and counts["repowerPunEvse"] == 1155,
        "publishedIdsExactPunOnly": published_ids <= pun_ids,
        "publishedIdsUnique": len(entries) == len(published_ids),
        "rankableTariffsSupportedOnly": all(row["directTariff"].get("rankable") is True for row in entries),
        "freeTariffsOfficialOnly": all(
            row["directTariff"]["energyEurPerKwh"] != 0 or row["freeCharge"] for row in entries
        ),
        "strictSiteFallbackTargetsUnique": len(strict_site_matches)
        == len(
            {
                str(match[0]["evse"].get("evseId"))
                for match in strict_site_matches.values()
            }
        ),
        "strictSiteFallbackUncoveredByExactIdentity": all(
            str(match[0]["evse"].get("evseId")) not in exact_identity_pun_ids
            for match in strict_site_matches.values()
        ),
        "strictSiteFallbackEvidenceExact": all(
            match[1] == "station_address_connector"
            and match[2] <= STRICT_SITE_MATCH_DISTANCE_M
            and match[3] is not None
            and match[3].get("addressExact") is True
            and match[3].get("punStationCandidateCount") == 1
            and match[3].get("punEvseCandidateCount") == 1
            for match in strict_site_matches.values()
        ),
    }
    return {
        "schemaVersion": 1,
        "dataset": "repower-italy-v9-direct-candidate",
        "generatedAt": source_meta["generatedAt"],
        "country": "IT",
        "operator": OPERATOR,
        "sources": {
            "repowerApp": REPOWER_APP_URL,
            "repowerChargingNet": REPOWER_NETWORK_URL,
            "officialApiBase": "https://api-chargearound.repower.com/rest/api/location",
            "googlePlay": APP_STORE_URL,
        },
        "sourceSnapshot": source_meta,
        "policy": {
            "directChannel": "Recharge Around one-shot payment",
            "exactPunIdentifiersOnly": True,
            "strictSiteFallback": (
                "identical normalized street address, <=25m, compatible current/standard, "
                "one PUN station, one PUN EVSE, no exact-identity target, one official claimant"
            ),
            "ambiguousSiteMatchesExcluded": True,
            "freeChargeRequiresOfficialFlag": True,
            "unsupportedPriceComponentsFailClosed": True,
            "roamingOffersExcluded": True,
            "registeredAccountNotUsed": True,
        },
        "counts": counts,
        "safetyGates": safety_gates,
        "entries": entries,
        "unresolved": sorted(
            unresolved,
            key=lambda row: (
                str(row.get("officialConnectorName") or ""),
                str(row.get("officialConnectorId") or ""),
            ),
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--consolidated", required=True)
    parser.add_argument("--apk", required=True)
    parser.add_argument("--out", default="data/national/repower_italy_v9_candidate.json.gz")
    parser.add_argument("--report", default="data/reports/repower_italy_v9_report.json")
    parser.add_argument(
        "--official-snapshot",
        default="data/national/repower_italy_official_snapshot.json.gz",
    )
    parser.add_argument("--reuse-official-snapshot", action="store_true")
    parser.add_argument("--workers", type=int, default=DETAIL_WORKERS)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 32:
        raise SystemExit("--workers must be between 1 and 32")

    consolidated = load_gz(Path(args.consolidated))
    apk_info = inspect_apk(Path(args.apk))
    snapshot_path = Path(args.official_snapshot)
    if args.reuse_official_snapshot:
        official_snapshot = load_gz(snapshot_path)
        details = official_snapshot["details"]
        source_meta = official_snapshot["sourceSnapshot"]
    else:
        token, expires_in = anonymous_token(apk_info)
        locations, location_response = fetch_locations(apk_info, token)
        details = fetch_details(apk_info, token, locations, args.workers)
        source_timestamps = [
            str(row.get("_sourceTimestamp")) for row in details if row.get("_sourceTimestamp")
        ]
        source_meta = {
            "generatedAt": max(source_timestamps) if source_timestamps else utc_now(),
            "locationTimestamp": location_response.get("timestamp"),
            "appVersion": APP_VERSION,
            "appVersionCode": APP_VERSION_CODE,
            "apkSha256": apk_info["apkSha256"],
            "certificateMd5": apk_info["certificateMd5"],
            "certificateSha256": apk_info["certificateSha256"],
            "signedV1V2V3": bool(
                apk_info["signedV1"] and apk_info["signedV2"] and apk_info["signedV3"]
            ),
            "apiHost": urlparse(apk_info["baseUrl"]).hostname,
            "anonymousOAuthExpiresInSeconds": expires_in,
            "networkId": NETWORK_ID,
        }
        for row in details:
            row.pop("_sourceTimestamp", None)
        save_gz(
            snapshot_path,
            {
                "schemaVersion": 1,
                "dataset": "repower-italy-official-snapshot",
                "sourceSnapshot": source_meta,
                "details": details,
            },
        )
    candidate = build_candidate(consolidated, details, source_meta)
    if not all(candidate["safetyGates"].values()):
        failed = [key for key, value in candidate["safetyGates"].items() if not value]
        raise RuntimeError(f"Repower safety gates failed: {failed}")
    report = {
        "schemaVersion": 1,
        "dataset": candidate["dataset"],
        "generatedAt": candidate["generatedAt"],
        "country": candidate["country"],
        "operator": candidate["operator"],
        "sources": candidate["sources"],
        "sourceSnapshot": candidate["sourceSnapshot"],
        "policy": candidate["policy"],
        "counts": candidate["counts"],
        "safetyGates": candidate["safetyGates"],
        "unresolved": candidate["unresolved"],
    }
    save_gz(Path(args.out), candidate)
    save_json(Path(args.report), report)
    print(json.dumps(candidate["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
