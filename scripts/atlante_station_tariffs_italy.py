#!/usr/bin/env python3
"""Build a strict Atlante-operated Italy direct tariff candidate from myAtlante.

Only IT / party ATE locations are accepted. Only unconditional EUR ENERGY
components are rankable. Partner/ChargeLeague and subscription pricing are not
included. The workflow independently validates every returned EVSE against the
current PUN ATE inventory before this dataset can be used by V9.
"""
from __future__ import annotations

import argparse
import gzip
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
COUNTRY_CODE = "IT"
PARTY_ID = "ATE"
APP_VERSION = "2.1.0"
OUT = Path("data/national/atlante_direct_stations_italy.json.gz")
REPORT = Path("data/reports/atlante_direct_stations_italy_report.json")
MAP_URL = f"{BASE_URL}/tenants/{TENANT_ID}/map-locations"
DETAIL_URL = f"{BASE_URL}/tenants/{TENANT_ID}/locations/{{location_id}}"
TARIFF_URL = f"{DETAIL_URL}/tariffs"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def finite_number(value: Any) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def request_json(url: str, api_key: str, attempts: int = 4) -> Any:
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Accept": "application/json",
        "Accept-Language": "it-IT",
        "X-App-Version": APP_VERSION,
        "X-App-Platform": "android",
        "User-Agent": f"myAtlante/{APP_VERSION} (Android; TCC Italy validation)",
    }
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(0.75 * (2**attempt))
    raise RuntimeError(f"Atlante request failed: {url}: {last}")


def map_request_url() -> str:
    # Italy + small border margin. We intentionally do not guess a CPO code:
    # countryCode=IT + partyId=ATE is the authoritative commercial filter.
    query = urllib.parse.urlencode({
        "latLongBottomLeft": "35,5",
        "latLongTopRight": "48,19",
        "evseTypes": "AC,DC,HPC",
        "locationStatus": "ALL",
        "connectorTypes": "CCS,CHADEMO,TYPE2",
    })
    return f"{MAP_URL}?{query}"


def parse_energy_price(raw: dict[str, Any]) -> float | None:
    components = raw.get("priceComponents") or []
    if len(components) != 1:
        return None
    c = components[0]
    validity = c.get("validity") or {}
    relative = validity.get("relative") or {}
    absolute = validity.get("absolute") or {}
    if (
        str(c.get("priceDimension") or "").upper() != "ENERGY"
        or str(c.get("currency") or "").upper() != "EUR"
        or c.get("conditions")
        or c.get("surchargeName")
        or relative.get("timeAfterSessionStartValidityInMinutes") is not None
        or relative.get("displayText")
        or absolute.get("daysOfWeekValidity")
    ):
        return None
    amount = finite_number((c.get("price") or {}).get("incl_vat"))
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
            raise ValueError(f"ambiguous price for {key}")
        result[key] = price
    return result


def normalize(summary: dict[str, Any], detail: dict[str, Any], tariffs: list[dict[str, Any]]) -> dict[str, Any] | None:
    if str(summary.get("countryCode") or "").upper() != COUNTRY_CODE or str(summary.get("partyId") or "").upper() != PARTY_ID:
        return None
    if str(detail.get("countryCode") or "").upper() != COUNTRY_CODE or str(detail.get("partyId") or "").upper() != PARTY_ID:
        return None
    if not str(detail.get("operatorName") or "").strip().lower().startswith("atlante"):
        return None
    if str(summary.get("id") or "") != str(detail.get("id") or ""):
        raise ValueError("map/detail location mismatch")

    prices = tariff_index(tariffs)
    connectors: list[dict[str, Any]] = []
    raw_count = 0
    for evse in detail.get("evses") or []:
        evse_id = str(evse.get("evseId") or "")
        if not evse_id.startswith("IT*ATE*"):
            continue
        for connector in evse.get("connectors") or []:
            raw_count += 1
            cid = str(connector.get("evseConnectorId") or "")
            price = prices.get((evse_id, cid))
            power = finite_number(connector.get("max_electric_power"))
            if price is None or power is None or power <= 0:
                continue
            connectors.append({
                "evseId": evse_id,
                "connectorId": cid,
                "kind": "DC" if str(connector.get("evsePowerType") or "").upper() == "DC" else "AC",
                "powerKw": round(power, 3),
                "pricePerKwhEur": price,
                "status": str(evse.get("evseStatus") or "UNKNOWN").upper(),
            })
    if not connectors:
        return None
    connectors.sort(key=lambda x: (x["evseId"], x["connectorId"]))
    return {
        "id": str(detail.get("id") or ""),
        "countryCode": COUNTRY_CODE,
        "partyId": PARTY_ID,
        "operatorName": "Atlante",
        "name": str(detail.get("displayName") or detail.get("locationName") or "").strip(),
        "city": str(detail.get("city") or "").strip(),
        "address": str(detail.get("address") or "").strip(),
        "connectors": connectors,
        "connectorCount": raw_count,
        "pricedConnectorCount": len(connectors),
        "unpricedConnectorCount": raw_count - len(connectors),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    key = os.environ.get("ATLANTE_API_SUBSCRIPTION_KEY", "").strip()
    if not key:
        raise SystemExit("ATLANTE_API_SUBSCRIPTION_KEY is required")

    map_payload = request_json(map_request_url(), key)
    summaries = [x for x in (map_payload.get("locations") or [])
                 if str(x.get("countryCode") or "").upper() == COUNTRY_CODE
                 and str(x.get("partyId") or "").upper() == PARTY_ID]
    if len(summaries) < 500:
        raise RuntimeError(f"unexpectedly small Atlante Italy inventory: {len(summaries)}")

    def hydrate(summary: dict[str, Any]) -> dict[str, Any] | None:
        lid = str(summary.get("id") or "")
        if not lid:
            raise ValueError("map location without id")
        detail = request_json(DETAIL_URL.format(location_id=lid), key)
        tariffs = request_json(TARIFF_URL.format(location_id=lid), key)
        return normalize(summary, detail, tariffs)

    locations: list[dict[str, Any]] = []
    failures = 0
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 16))) as pool:
        futures = [pool.submit(hydrate, x) for x in summaries]
        for future in as_completed(futures):
            try:
                row = future.result()
                if row:
                    locations.append(row)
            except Exception:
                failures += 1

    connectors = [c for x in locations for c in x["connectors"]]
    evse_ids = sorted({c["evseId"] for c in connectors})
    prices = Counter(f"{c['pricePerKwhEur']:.2f}" for c in connectors)
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "atlante-direct-operated-stations-italy-candidate",
        "generatedAt": now_iso(),
        "country": "IT",
        "operator": "Atlante",
        "partyId": PARTY_ID,
        "scope": {
            "onlyOperatedLocations": True,
            "partnerLocationsIncluded": False,
            "atlanteGoIncluded": False,
            "roamingTariffsIncluded": False,
            "onlyUnconditionalEnergyPrices": True,
            "requiresExactPunAteValidationBeforeV9": True,
        },
        "counts": {
            "mapAteLocationCount": len(summaries),
            "pricedLocationCount": len(locations),
            "pricedConnectorCount": len(connectors),
            "pricedEvseCount": len(evse_ids),
            "hydrationFailureCount": failures,
            "priceCounts": dict(sorted(prices.items())),
        },
        "evseIds": evse_ids,
        "locations": sorted(locations, key=lambda x: (x["name"].lower(), x["id"])),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    OUT.write_bytes(gzip.compress(raw.encode("utf-8"), compresslevel=9, mtime=0))
    report = {"generatedAt": payload["generatedAt"], "counts": payload["counts"], "scope": payload["scope"]}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
