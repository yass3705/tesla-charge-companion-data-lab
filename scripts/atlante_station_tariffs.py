#!/usr/bin/env python3
"""Build the official Atlante-operated France station/connector tariff map.

The read-only guest endpoints are the ones used by myAtlante.  Authentication
is supplied at runtime through ``ATLANTE_API_SUBSCRIPTION_KEY`` and is never
written to the output.  The build is deliberately fail-closed: only FR/ATL
locations returned for the FRATL CPO are accepted and only unconditional EUR
ENERGY components can become rankable direct tariffs.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_URL = "https://pdefweushaapiam01.azure-api.net/app-backend/v1"
TENANT_ID = "390c3ff9-b41c-42dc-aa48-1dd51ad6ce39"
CANONICAL_CPO = "FRATL"
COUNTRY_CODE = "FR"
PARTY_ID = "ATL"
APP_VERSION = "2.1.0"
DEFAULT_OUT = Path("data/national/atlante_direct_stations_france.json.gz")
MAP_URL = f"{BASE_URL}/tenants/{TENANT_ID}/map-locations"
DETAIL_URL = f"{BASE_URL}/tenants/{TENANT_ID}/locations/{{location_id}}"
TARIFF_URL = f"{DETAIL_URL}/tariffs"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def finite_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def request_json(url: str, api_key: str, attempts: int = 4) -> Any:
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Accept": "application/json",
        "Accept-Language": "fr-FR",
        "X-App-Version": APP_VERSION,
        "X-App-Platform": "android",
        "User-Agent": f"myAtlante/{APP_VERSION} (Android; TCC tariff validation)",
    }
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=45) as response:
                if int(getattr(response, "status", 200)) != 200:
                    raise RuntimeError(f"unexpected HTTP status for {url}")
                return json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(0.75 * (2**attempt))
    raise RuntimeError(f"Atlante request failed after {attempts} attempts: {url}: {last}")


def map_request_url() -> str:
    query = urllib.parse.urlencode(
        {
            "latLongBottomLeft": "41,-6",
            "latLongTopRight": "52,10",
            "evseTypes": "AC,DC,HPC",
            "locationStatus": "ALL",
            "connectorTypes": "CCS,CHADEMO,TYPE2",
            "includeCpos": CANONICAL_CPO,
        }
    )
    return f"{MAP_URL}?{query}"


def parse_coordinates(value: Any) -> tuple[float, float]:
    parts = str(value or "").split(",")
    if len(parts) != 2:
        raise ValueError(f"invalid Atlante coordinates: {value!r}")
    latitude, longitude = (finite_number(x.strip()) for x in parts)
    if latitude is None or longitude is None:
        raise ValueError(f"invalid Atlante coordinates: {value!r}")
    return latitude, longitude


def parse_energy_price(raw: dict[str, Any]) -> float | None:
    components = raw.get("priceComponents") or []
    if len(components) != 1:
        return None
    component = components[0]
    validity = component.get("validity") or {}
    relative = validity.get("relative") or {}
    absolute = validity.get("absolute") or {}
    if (
        str(component.get("priceDimension") or "").upper() != "ENERGY"
        or str(component.get("currency") or "").upper() != "EUR"
        or component.get("conditions")
        or component.get("surchargeName")
        or relative.get("timeAfterSessionStartValidityInMinutes") is not None
        or relative.get("displayText")
        or absolute.get("daysOfWeekValidity")
    ):
        return None
    amount = finite_number((component.get("price") or {}).get("incl_vat"))
    return round(amount, 6) if amount is not None and amount > 0 else None


def tariff_index(tariffs: list[dict[str, Any]]) -> dict[tuple[str, str], float]:
    result: dict[tuple[str, str], float] = {}
    for tariff in tariffs:
        ids = tariff.get("identifiers") or {}
        key = (str(ids.get("evseId") or ""), str(ids.get("connectorId") or ""))
        price = parse_energy_price(tariff)
        if not all(key) or price is None:
            continue
        previous = result.get(key)
        if previous is not None and previous != price:
            raise ValueError(f"ambiguous Atlante price for connector {key}")
        result[key] = price
    return result


def normalize_location(
    summary: dict[str, Any], detail: dict[str, Any], tariffs: list[dict[str, Any]]
) -> dict[str, Any] | None:
    if str(summary.get("countryCode") or "").upper() != COUNTRY_CODE:
        return None
    if str(summary.get("partyId") or "").upper() != PARTY_ID:
        return None
    if str(detail.get("countryCode") or "").upper() != COUNTRY_CODE:
        return None
    if str(detail.get("partyId") or "").upper() != PARTY_ID:
        return None
    if str(detail.get("operatorName") or "").strip().lower() not in {"atlante", "atlante france"}:
        return None
    if str(summary.get("id") or "") != str(detail.get("id") or ""):
        raise ValueError("Atlante map/detail location ID mismatch")

    latitude, longitude = parse_coordinates(detail.get("coordinates"))
    prices = tariff_index(tariffs)
    connectors: list[dict[str, Any]] = []
    raw_connector_count = 0
    for evse in detail.get("evses") or []:
        for connector in evse.get("connectors") or []:
            raw_connector_count += 1
            evse_id = str(evse.get("evseId") or "")
            connector_id = str(connector.get("evseConnectorId") or "")
            price = prices.get((evse_id, connector_id))
            power = finite_number(connector.get("max_electric_power"))
            if price is None or power is None or power <= 0:
                continue
            power_type = str(connector.get("evsePowerType") or "").upper()
            connectors.append(
                {
                    "evseId": evse_id,
                    "connectorId": connector_id,
                    "externalConnectorId": str(connector.get("externalConnectorId") or ""),
                    "connectorType": str(connector.get("evseCommonConnectorType") or ""),
                    "kind": "DC" if power_type == "DC" else "AC",
                    "powerKw": round(power, 3),
                    "pricePerKwhEur": price,
                    "status": str(evse.get("evseStatus") or "UNKNOWN").upper(),
                    "statusLastUpdated": evse.get("statusLastUpdated"),
                }
            )
    if not connectors:
        raise ValueError(f"Atlante France location has no usable direct tariff: {detail.get('id')}")
    connectors.sort(key=lambda x: (x["kind"], x["powerKw"], x["pricePerKwhEur"], x["evseId"], x["connectorId"]))
    return {
        "id": str(detail.get("id") or ""),
        "locationId": str(detail.get("locationId") or ""),
        "countryCode": COUNTRY_CODE,
        "partyId": PARTY_ID,
        "operatorName": "Atlante",
        "subOperatorName": str(detail.get("subOperatorName") or ""),
        "name": str(detail.get("displayName") or detail.get("locationName") or "").strip(),
        "address": str(detail.get("address") or "").strip(),
        "postalCode": str(detail.get("postalCode") or "").strip(),
        "city": str(detail.get("city") or "").strip(),
        "latitude": latitude,
        "longitude": longitude,
        "openTwentyFourSeven": bool(detail.get("locationOpenTwentyFourSeven")),
        "connectors": connectors,
        "connectorCount": raw_connector_count,
        "pricedConnectorCount": len(connectors),
        "unpricedConnectorCount": raw_connector_count - len(connectors),
    }


def make_payload(map_payload: dict[str, Any], locations: list[dict[str, Any]]) -> dict[str, Any]:
    summaries = map_payload.get("locations") or []
    operated = [
        x for x in summaries
        if str(x.get("countryCode") or "").upper() == COUNTRY_CODE
        and str(x.get("partyId") or "").upper() == PARTY_ID
    ]
    locations = sorted(locations, key=lambda x: (x["name"].lower(), x["id"]))
    connectors = [connector for location in locations for connector in location["connectors"]]
    if len(locations) != len(operated) or not locations:
        raise ValueError(f"Atlante hydration incomplete: {len(locations)} / {len(operated)}")
    price_counts = Counter(f"{x['pricePerKwhEur']:.2f}" for x in connectors)
    power_counts = Counter(f"{x['powerKw']:g}" for x in connectors)
    return {
        "schemaVersion": "1.0.0",
        "dataset": "atlante-direct-operated-stations-france",
        "generatedAt": now_iso(),
        "operator": "Atlante",
        "country": COUNTRY_CODE,
        "scope": {
            "requiredCpo": CANONICAL_CPO,
            "requiredCountryCode": COUNTRY_CODE,
            "requiredPartyId": PARTY_ID,
            "onlyOperatedLocations": True,
            "partnerLocationsIncluded": False,
            "tariffFamily": "myAtlante direct without subscription",
            "atlanteGoIncluded": False,
            "roamingTariffsIncluded": False,
            "priceGranularity": "connector",
            "onlyUnconditionalEnergyPrices": True,
        },
        "source": {
            "mapUrl": MAP_URL,
            "detailUrlTemplate": DETAIL_URL,
            "tariffUrlTemplate": TARIFF_URL,
            "tenantId": TENANT_ID,
            "appVersion": APP_VERSION,
            "credentialsStored": False,
        },
        "counts": {
            "mapLocationCount": len(summaries),
            "franceLocationCount": len(locations),
            "franceConnectorCount": len(connectors),
            "franceUnpricedConnectorCount": sum(x["unpricedConnectorCount"] for x in locations),
            "priceCounts": dict(sorted(price_counts.items())),
            "powerCounts": dict(sorted(power_counts.items(), key=lambda item: float(item[0]))),
        },
        "matchPolicy": {
            "exactLocationIdFirst": True,
            "operatorMatchRequiredForFallback": True,
            "geoFallbackMaxDistanceMeters": 150,
            "ambiguousTariffsFailClosed": True,
        },
        "locations": locations,
    }


def live_build(api_key: str, workers: int) -> dict[str, Any]:
    map_payload = request_json(map_request_url(), api_key)
    summaries = [
        x for x in (map_payload.get("locations") or [])
        if str(x.get("countryCode") or "").upper() == COUNTRY_CODE
        and str(x.get("partyId") or "").upper() == PARTY_ID
    ]
    if len(summaries) < 100:
        raise RuntimeError(f"Atlante France inventory unexpectedly small: {len(summaries)}")

    def hydrate(summary: dict[str, Any]) -> dict[str, Any] | None:
        location_id = str(summary.get("id") or "")
        if not location_id:
            raise ValueError("Atlante map location without ID")
        detail = request_json(DETAIL_URL.format(location_id=location_id), api_key)
        tariffs = request_json(TARIFF_URL.format(location_id=location_id), api_key)
        return normalize_location(summary, detail, tariffs)

    locations: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 16))) as pool:
        futures = [pool.submit(hydrate, summary) for summary in summaries]
        for future in as_completed(futures):
            location = future.result()
            if location:
                locations.append(location)
    return make_payload(map_payload, locations)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    api_key = os.environ.get("ATLANTE_API_SUBSCRIPTION_KEY", "").strip()
    if not api_key:
        raise SystemExit("ATLANTE_API_SUBSCRIPTION_KEY is required and is never stored in output")
    payload = live_build(api_key, args.workers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.out.suffix == ".gz":
        args.out.write_bytes(gzip.compress(rendered.encode("utf-8"), compresslevel=9, mtime=0))
    else:
        args.out.write_text(rendered, encoding="utf-8")
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    counts = payload["counts"]
    print(
        f"Atlante direct France: {counts['franceLocationCount']} locations / "
        f"{counts['franceConnectorCount']} priced connectors / sha256={digest}"
    )


if __name__ == "__main__":
    main()
