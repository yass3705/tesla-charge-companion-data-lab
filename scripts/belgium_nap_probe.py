#!/usr/bin/env python3
"""Probe and profile the official Belgium NAP DATEX II feed.

The bearer token is read only from BELGIUM_NAP_TOKEN and is never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

BASE_URL = "https://nap-be.eco-movement.com"
LOCATIONS_PATH = "/datex2/v1/locations"


def fetch_json(url: str, token: str, timeout: int = 180) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "tesla-charge-companion-data-lab/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        ctype = resp.headers.get("Content-Type", "")
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        if "json" not in ctype.lower() and not body.lstrip().startswith((b"{", b"[")):
            raise RuntimeError(f"Unexpected content type: {ctype}")
        return json.loads(body)


def walk(obj: Any, path: str = "$"):
    yield path, obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[]")


def list_shape(payload: Any) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    sample_types: dict[str, str] = {}
    for path, obj in walk(payload):
        if isinstance(obj, list):
            counts[path] = max(counts[path], len(obj))
            if obj:
                sample_types[path] = type(obj[0]).__name__
    rows = [
        {"path": p, "maxLength": n, "firstItemType": sample_types.get(p, "")}
        for p, n in counts.items()
    ]
    rows.sort(key=lambda r: (-r["maxLength"], r["path"]))
    return rows[:100]


def find_location_list(payload: Any) -> tuple[str, list[dict[str, Any]]]:
    # DATEX II Belgium location records can be recognized by station + entrance/brand fields.
    candidates: list[tuple[str, list[dict[str, Any]]]] = []
    for path, obj in walk(payload):
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            sample = obj[: min(10, len(obj))]
            score = sum(
                1 for x in sample
                if "energyInfrastructureStation" in x and ("entrance" in x or "brand" in x or "idG" in x)
            )
            if score:
                candidates.append((path, obj))
    if candidates:
        candidates.sort(key=lambda x: len(x[1]), reverse=True)
        return candidates[0]
    return "", []


def org_name(obj: Any) -> str:
    try:
        vals = obj["afacAnOrganisation"]["name"]["values"]
        if isinstance(vals, list):
            for v in vals:
                if isinstance(v, dict) and isinstance(v.get("value"), str) and v["value"].strip():
                    return v["value"].strip()
    except Exception:
        pass
    return ""


def price_rows(cp: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for product in cp.get("energyProduct", []) or []:
        energy = product.get("aegiElectricEnergy", {}) if isinstance(product, dict) else {}
        for rate in energy.get("energyRate", []) or []:
            if not isinstance(rate, dict):
                continue
            policy = ((rate.get("ratePolicy") or {}).get("value")
                      if isinstance(rate.get("ratePolicy"), dict) else None)
            currencies = rate.get("applicableCurrency") or []
            for p in rate.get("energyPrice", []) or []:
                if not isinstance(p, dict):
                    continue
                out.append({
                    "rateId": rate.get("idG"),
                    "ratePolicy": policy,
                    "lastUpdated": rate.get("lastUpdated"),
                    "currency": currencies[0] if currencies else None,
                    "priceType": ((p.get("priceType") or {}).get("value")
                                  if isinstance(p.get("priceType"), dict) else None),
                    "value": p.get("value"),
                    "taxIncluded": p.get("taxIncluded"),
                    "taxRate": p.get("taxRate"),
                })
    return out


def parse_locations(locations: list[dict[str, Any]]) -> dict[str, Any]:
    station_count = 0
    evse_count = 0
    connector_count = 0
    priced_evse_count = 0
    adhoc_priced_evse_count = 0
    operators = Counter()
    prefixes = Counter()
    current_types = Counter()
    connector_types = Counter()
    price_types = Counter()
    price_fingerprints = Counter()
    evse_ids: list[str] = []
    sample_status_ids: list[str] = []

    for loc in locations:
        loc_op = org_name(loc.get("energyDistributor", {}))
        if loc_op:
            operators[loc_op] += 1

        stations = loc.get("energyInfrastructureStation") or []
        if not isinstance(stations, list):
            continue
        station_count += len(stations)

        for st in stations:
            if not isinstance(st, dict):
                continue
            st_op = org_name(st.get("energyDistributor", {}))
            if st_op and not loc_op:
                operators[st_op] += 1

            for rp in st.get("refillPoint", []) or []:
                if not isinstance(rp, dict):
                    continue
                cp = rp.get("aegiElectricChargingPoint")
                if not isinstance(cp, dict):
                    continue
                evse_count += 1
                current = ((cp.get("currentType") or {}).get("value")
                           if isinstance(cp.get("currentType"), dict) else None)
                if current:
                    current_types[str(current)] += 1

                connectors = cp.get("connector") or []
                if isinstance(connectors, list):
                    connector_count += len(connectors)
                    for conn in connectors:
                        if not isinstance(conn, dict):
                            continue
                        ctype = ((conn.get("connectorType") or {}).get("value")
                                 if isinstance(conn.get("connectorType"), dict) else None)
                        if ctype:
                            connector_types[str(ctype)] += 1
                        for ext in conn.get("externalIdentifier", []) or []:
                            if not isinstance(ext, dict):
                                continue
                            ident = ext.get("identifier")
                            if isinstance(ident, str) and ident:
                                if ident not in evse_ids:
                                    evse_ids.append(ident)
                                normalized = ident.replace("*", "-")
                                parts = normalized.split("-")
                                if len(parts) >= 2:
                                    prefixes["-".join(parts[:2])] += 1
                                if len(sample_status_ids) < 12 and ident not in sample_status_ids:
                                    sample_status_ids.append(ident)

                rows = price_rows(cp)
                if rows:
                    priced_evse_count += 1
                    if any(r.get("ratePolicy") == "adHoc" for r in rows):
                        adhoc_priced_evse_count += 1
                    for r in rows:
                        if r.get("priceType"):
                            price_types[str(r["priceType"])] += 1
                        fp = (
                            r.get("ratePolicy"), r.get("currency"), r.get("priceType"),
                            r.get("value"), r.get("taxIncluded"), r.get("taxRate")
                        )
                        price_fingerprints[str(fp)] += 1

    return {
        "stationCount": station_count,
        "evseCount": evse_count,
        "connectorCount": connector_count,
        "pricedEvseCount": priced_evse_count,
        "adHocPricedEvseCount": adhoc_priced_evse_count,
        "priceCoveragePct": round((priced_evse_count / evse_count * 100), 2) if evse_count else 0,
        "adHocPriceCoveragePct": round((adhoc_priced_evse_count / evse_count * 100), 2) if evse_count else 0,
        "operatorLocationCounts": dict(operators.most_common()),
        "evseCountryPartyPrefixes": dict(prefixes.most_common()),
        "currentTypes": dict(current_types.most_common()),
        "connectorTypes": dict(connector_types.most_common()),
        "priceTypes": dict(price_types.most_common()),
        "topPriceFingerprints": [
            {"fingerprint": k, "evseOccurrences": v}
            for k, v in price_fingerprints.most_common(100)
        ],
        "sampleEvseIdsForStatusProbe": sample_status_ids,
    }


def sanitize_sample(locations: list[dict[str, Any]], max_items: int = 3) -> list[dict[str, Any]]:
    forbidden = {"token", "authorization", "apikey", "api_key", "secret", "password"}
    def scrub(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: scrub(v) for k, v in obj.items() if str(k).lower() not in forbidden}
        if isinstance(obj, list):
            return [scrub(x) for x in obj[:30]]
        return obj
    return [scrub(x) for x in locations[:max_items]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-output", default="")
    ap.add_argument("--summary-output", default="reports/belgium-nap-probe-summary.json")
    ap.add_argument("--sample-output", default="reports/belgium-nap-locations-sample.json")
    args = ap.parse_args()

    token = os.environ.get("BELGIUM_NAP_TOKEN", "").strip()
    if not token:
        print("BELGIUM_NAP_TOKEN is required", file=sys.stderr)
        return 2

    payload = fetch_json(BASE_URL + LOCATIONS_PATH, token)
    location_path, locations = find_location_list(payload)
    exact = parse_locations(locations)

    summary = {
        "source": BASE_URL + LOCATIONS_PATH,
        "httpAuthenticated": True,
        "topLevelType": type(payload).__name__,
        "topLevelKeys": sorted(payload.keys()) if isinstance(payload, dict) else [],
        "detectedLocationPath": location_path,
        "locationCount": len(locations),
        **exact,
        "largestListPaths": list_shape(payload),
        "note": "Counts are derived from the detected DATEX II Belgium location list and the nested energyInfrastructureStation/refillPoint/aegiElectricChargingPoint structure."
    }

    Path(args.summary_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary_output).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(args.sample_output).write_text(json.dumps(sanitize_sample(locations), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.raw_output:
        Path(args.raw_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.raw_output).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
