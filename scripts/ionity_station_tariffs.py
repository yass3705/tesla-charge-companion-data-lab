#!/usr/bin/env python3
"""Build the France IONITY Direct station/connector tariff map.

The source is the read-only backend used by the public IONITY app.  The build is
fail-closed: only locations whose CPO identifier is exactly ``IONITY_CPO`` and
whose hydrated country is France are retained.  Subscriber/personalized prices
are deliberately ignored; only the public ``IONITY DIRECT`` ad-hoc price is
published for TCC.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_URL = "https://adhoc-bff.ionity.cloud/api"
STATIC_URL = f"{BASE_URL}/v1/location/static"
DETAIL_URL = f"{BASE_URL}/v3/location/{{uuid}}"
CANONICAL_CPO = "IONITY_CPO"
APP_FEATURE_VERSION = "v2.428.0"
DEFAULT_OUT = Path("data/national/ionity_direct_stations_france.json.gz")
HEADERS = {
    "User-Agent": "IONITY/2.428.0 (Android; TeslaChargeCompanion data validation)",
    "Accept": "application/json",
    "x-adhoc-platform": "ANDROID_V2",
    "x-adhoc-app-feature-version": APP_FEATURE_VERSION,
    "x-adhoc-device-country": "FR",
    "x-adhoc-device-language": "fr",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request_json(url: str, attempts: int = 4) -> Any:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers=HEADERS, method="GET")
            with urllib.request.urlopen(req, timeout=35) as response:
                if int(getattr(response, "status", 200)) != 200:
                    raise RuntimeError(f"unexpected HTTP status for {url}")
                return json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(0.75 * (2**attempt))
    raise RuntimeError(f"IONITY request failed after {attempts} attempts: {url}: {last}")


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def connector_kind(connector_type: str) -> str:
    return "AC" if connector_type.strip().lower() in {"type 2", "type2"} else "DC"


def parse_direct_connector(raw: dict[str, Any]) -> dict[str, Any] | None:
    price = raw.get("adhocPrice") or {}
    amount = finite_number(price.get("amount"))
    watts = finite_number(raw.get("maxPower"))
    if (
        str(price.get("name") or "").strip().upper() != "IONITY DIRECT"
        or str(price.get("unit") or "").strip().lower() != "kwh"
        or str(price.get("currency") or "").strip().upper() != "EUR"
        or amount is None
        or amount <= 0
        or watts is None
        or watts <= 0
    ):
        return None
    connector_type = str(raw.get("type") or "").strip()
    return {
        "uuid": str(raw.get("uuid") or "").strip(),
        "number": raw.get("number"),
        "physicalReference": str(raw.get("physicalReference") or "").strip(),
        "type": connector_type,
        "kind": connector_kind(connector_type),
        "powerKw": round(watts / 1000.0, 3),
        "pricePerKwhEur": round(amount, 6),
    }


def normalize_location(static: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any] | None:
    if static.get("cpoIdentifier") != CANONICAL_CPO or detail.get("cpoIdentifier") != CANONICAL_CPO:
        return None
    if str(detail.get("country") or "").strip().upper() != "FR":
        return None
    if str(static.get("uuid") or "") != str(detail.get("uuid") or ""):
        raise ValueError(f"IONITY location UUID mismatch: {static.get('uuid')} / {detail.get('uuid')}")

    latitude = finite_number(detail.get("latitude"))
    longitude = finite_number(detail.get("longitude"))
    if latitude is None or longitude is None:
        raise ValueError(f"IONITY France location has invalid coordinates: {detail.get('uuid')}")

    raw_connectors = detail.get("connectors") or []
    connectors = [parsed for item in raw_connectors if (parsed := parse_direct_connector(item))]
    if not connectors:
        raise ValueError(f"IONITY France location has no usable Direct price: {detail.get('uuid')}")

    missing = len(raw_connectors) - len(connectors)
    return {
        "uuid": str(detail["uuid"]),
        "locationId": str(static.get("locationId") or ""),
        "cpoIdentifier": CANONICAL_CPO,
        "name": str(detail.get("name") or static.get("name") or "").strip(),
        "address": str(detail.get("address") or "").strip(),
        "postalCode": str(detail.get("postalCode") or "").strip(),
        "city": str(detail.get("city") or "").strip(),
        "country": "FR",
        "latitude": latitude,
        "longitude": longitude,
        "connectors": sorted(connectors, key=lambda x: (x["kind"], x["powerKw"], x["number"] or 0, x["uuid"])),
        "connectorCount": len(raw_connectors),
        "pricedConnectorCount": len(connectors),
        "unpricedConnectorCount": missing,
    }


def hydrate_location(static: dict[str, Any]) -> dict[str, Any] | None:
    uuid = str(static.get("uuid") or "").strip()
    if not uuid:
        raise ValueError("IONITY static location without UUID")
    return normalize_location(static, request_json(DETAIL_URL.format(uuid=uuid)))


def build(static_payload: dict[str, Any], detail_payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    static_locations = static_payload.get("locations") or []
    operated = [item for item in static_locations if item.get("cpoIdentifier") == CANONICAL_CPO]
    locations = []
    for static in operated:
        uuid = str(static.get("uuid") or "")
        detail = detail_payloads.get(uuid)
        if detail is None:
            raise ValueError(f"missing hydrated IONITY location: {uuid}")
        normalized = normalize_location(static, detail)
        if normalized:
            locations.append(normalized)
    return make_payload(static_locations, operated, locations)


def make_payload(static_locations: list[dict[str, Any]], operated: list[dict[str, Any]], locations: list[dict[str, Any]]) -> dict[str, Any]:
    locations = sorted(locations, key=lambda x: (x["name"].lower(), x["uuid"]))
    connectors = [connector for location in locations for connector in location["connectors"]]
    price_counts = Counter(f"{c['pricePerKwhEur']:.2f}" for c in connectors)
    power_counts = Counter(f"{c['powerKw']:g}" for c in connectors)
    if not locations:
        raise ValueError("IONITY France operated-station result is empty")
    if any(location["cpoIdentifier"] != CANONICAL_CPO for location in locations):
        raise ValueError("non-IONITY CPO leaked into France map")
    return {
        "schemaVersion": "1.0.0",
        "dataset": "ionity-direct-operated-stations-france",
        "generatedAt": now_iso(),
        "operator": "IONITY",
        "country": "FR",
        "scope": {
            "requiredCpoIdentifier": CANONICAL_CPO,
            "onlyOperatedLocations": True,
            "tariffFamily": "IONITY DIRECT",
            "subscriberTariffsIncluded": False,
            "roamingTariffsIncluded": False,
            "priceGranularity": "connector",
        },
        "source": {
            "staticUrl": STATIC_URL,
            "detailUrlTemplate": DETAIL_URL,
            "platform": HEADERS["x-adhoc-platform"],
            "appFeatureVersion": APP_FEATURE_VERSION,
        },
        "counts": {
            "staticLocationCount": len(static_locations),
            "operatedStaticLocationCount": len(operated),
            "franceLocationCount": len(locations),
            "franceConnectorCount": len(connectors),
            "franceUnpricedConnectorCount": sum(x["unpricedConnectorCount"] for x in locations),
            "priceCounts": dict(sorted(price_counts.items())),
            "powerCounts": dict(sorted(power_counts.items(), key=lambda x: float(x[0]))),
        },
        "matchPolicy": {
            "exactLocationUuidFirst": True,
            "operatorMatchRequiredForFallback": True,
            "geoFallbackMaxDistanceMeters": 150,
            "ambiguousTariffsFailClosed": True,
        },
        "locations": locations,
    }


def live_build(workers: int) -> dict[str, Any]:
    static_payload = request_json(STATIC_URL)
    static_locations = static_payload.get("locations") or []
    if len(static_locations) < 500:
        raise RuntimeError(f"IONITY static inventory unexpectedly small: {len(static_locations)}")
    operated = [item for item in static_locations if item.get("cpoIdentifier") == CANONICAL_CPO]
    if len(operated) < 500:
        raise RuntimeError(f"IONITY operated inventory unexpectedly small: {len(operated)}")

    locations: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 24))) as pool:
        futures = {pool.submit(hydrate_location, item): item for item in operated}
        for future in as_completed(futures):
            normalized = future.result()
            if normalized:
                locations.append(normalized)
    return make_payload(static_locations, operated, locations)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    payload = live_build(args.workers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.out.suffix == ".gz":
        args.out.write_bytes(gzip.compress(rendered.encode("utf-8"), compresslevel=9, mtime=0))
    else:
        args.out.write_text(rendered, encoding="utf-8")
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    counts = payload["counts"]
    print(
        f"IONITY Direct France: {counts['franceLocationCount']} locations / "
        f"{counts['franceConnectorCount']} priced connectors / sha256={digest}"
    )


if __name__ == "__main__":
    main()
