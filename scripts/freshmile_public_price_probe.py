#!/usr/bin/env python3
"""Resolve Freshmile public location IDs, then probe EVSE tariff semantics.

Freshmile's live public API established two useful contracts through validation:
- /locations accepts an origin through order_by.latitude/order_by.longitude;
- /evses accepts filter.location_id (or an internal filter.ref).

The IRVE/OCPI EVSE IDs are not valid Freshmile internal refs, so this stage
starts from three known Freshmile station coordinates, resolves the nearest
public location object, then performs a bounded EVSE lookup with the returned
internal location id/ref. All requests are unauthenticated GETs. No numeric
value is accepted as a TCC tariff without explicit EVSE + tariff semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = "https://prod-driver-api.freshmile.com/charge/api/v2"
DEFAULT_OUTPUT = Path("reports/freshmile/public_price_probe_latest.json")
UA = "Tesla-Charge-Companion-Freshmile-Probe/1.2 (+public-GET-only)"
TARGETS = [
    {
        "evse": "FRFR1EBVFB2",
        "name": "Ajaccio - Hôtel Dolce Vita",
        "latitude": 41.9307,
        "longitude": 8.73422,
    },
    {
        "evse": "FRFR1EPNFH1",
        "name": "Palavas-les-Flots - Hôtel Amérique",
        "latitude": 43.52927,
        "longitude": 3.92506,
    },
    {
        "evse": "FRFR1EUMAR1",
        "name": "Champdor-Corcelles - Place de la Mairie",
        "latitude": 46.01744,
        "longitude": 5.59686,
    },
]
PRICE_WORDS = re.compile(
    r"\b(price|pricing|tariff|tariffs|tarif|tarifs|cost|fee|rate|kwh|minute|min|amount|currency|eur|euro)\b",
    re.I,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read(512_000)
            status = response.status
            content_type = response.headers.get("content-type", "")
            resolved = response.geturl()
    except urllib.error.HTTPError as exc:
        raw = exc.read(128_000)
        status = exc.code
        content_type = exc.headers.get("content-type", "") if exc.headers else ""
        resolved = exc.geturl()
    except Exception as exc:
        return {"url": url, "error": f"{type(exc).__name__}: {exc}"}

    text = raw.decode("utf-8", errors="replace")
    parsed: Any = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        pass
    return {
        "url": url,
        "resolvedUrl": resolved,
        "status": status,
        "contentType": content_type,
        "bytesRead": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bodyLooksJson": parsed is not None,
        "priceSemanticTerms": sorted({m.group(0).lower() for m in PRICE_WORDS.finditer(text)}),
        "bodyPreview": re.sub(r"\s+", " ", text[:5000]).strip(),
        "json": parsed,
    }


def url(path: str, params: dict[str, Any]) -> str:
    return BASE + path + "?" + urllib.parse.urlencode(params)


def as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def coordinates(record: dict[str, Any]) -> tuple[float, float] | None:
    # Common direct shapes.
    for lat_key, lon_key in (
        ("latitude", "longitude"),
        ("lat", "lng"),
        ("lat", "lon"),
        ("lat", "longitude"),
    ):
        lat = as_float(record.get(lat_key))
        lon = as_float(record.get(lon_key))
        if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    # GeoJSON shape.
    coords = record.get("coordinates")
    if isinstance(coords, list) and len(coords) >= 2:
        lon, lat = as_float(coords[0]), as_float(coords[1])
        if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    return None


def distance_score(lat: float, lon: float, candidate: tuple[float, float] | None) -> float:
    if candidate is None:
        return 10_000.0
    clat, clon = candidate
    # Sufficient for ranking nearby API results; no routing claim is made.
    return (clat - lat) ** 2 + ((clon - lon) * math.cos(math.radians(lat))) ** 2


def location_candidates(payload: Any, lat: float, lon: float) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for record in walk_dicts(payload):
        identifier = record.get("id")
        ref = record.get("ref")
        if identifier is None and ref is None:
            continue
        point = coordinates(record)
        # Records without coordinates can still be useful if they look like
        # location objects, but coordinate-bearing ones rank first.
        name = record.get("name") or record.get("label") or record.get("address")
        key = (str(identifier or ""), str(ref or ""))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "id": identifier,
                "ref": ref,
                "name": name,
                "coordinates": list(point) if point else None,
                "score": distance_score(lat, lon, point),
                "keys": sorted(record.keys())[:40],
            }
        )
    candidates.sort(key=lambda item: item["score"])
    return candidates[:10]


def slim_response(response: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in response.items() if key != "json"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    requests: list[dict[str, Any]] = []
    resolutions: list[dict[str, Any]] = []

    for target in TARGETS:
        location_url = url(
            "/locations",
            {
                "order_by[latitude]": target["latitude"],
                "order_by[longitude]": target["longitude"],
            },
        )
        location_response = request_json(location_url)
        requests.append(slim_response(location_response))
        candidates = location_candidates(
            location_response.get("json"), target["latitude"], target["longitude"]
        )
        selected = candidates[0] if candidates else None
        resolution: dict[str, Any] = {
            "target": target,
            "locationStatus": location_response.get("status"),
            "candidateCount": len(candidates),
            "candidates": candidates[:5],
            "selected": selected,
            "evseLookups": [],
        }

        if selected:
            lookup_params: list[dict[str, Any]] = []
            if selected.get("id") is not None:
                lookup_params.append({"filter[location_id]": selected["id"]})
            if selected.get("ref"):
                lookup_params.append({"filter[ref]": selected["ref"]})
            for params in lookup_params[:2]:
                response = request_json(url("/evses", params))
                requests.append(slim_response(response))
                resolution["evseLookups"].append(
                    {
                        "params": params,
                        "status": response.get("status"),
                        "priceSemanticTerms": response.get("priceSemanticTerms") or [],
                        "bodyPreview": response.get("bodyPreview"),
                    }
                )
        resolutions.append(resolution)

    successful = [item for item in requests if item.get("status") in {200, 206}]
    semantic = [item for item in successful if item.get("priceSemanticTerms")]
    payload = {
        "schemaVersion": "1.2.0",
        "generatedAt": now_iso(),
        "baseUrl": BASE,
        "method": "unauthenticated public GET only",
        "targets": TARGETS,
        "requestCount": len(requests),
        "statusCounts": {},
        "successfulResponseCount": len(successful),
        "successfulResponsesWithPriceSemantics": len(semantic),
        "validatedExactPriceFound": False,
        "policy": (
            "HTTP 200, internal ids and price-like words are discovery evidence only. "
            "Exact price needs the target EVSE identity plus explicit tariff components before TCC ranking."
        ),
        "resolutions": resolutions,
        "requests": requests,
    }
    for item in requests:
        key = str(item.get("status") or "error")
        payload["statusCounts"][key] = payload["statusCounts"].get(key, 0) + 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "requestCount": payload["requestCount"],
                "statusCounts": payload["statusCounts"],
                "successfulResponseCount": payload["successfulResponseCount"],
                "successfulResponsesWithPriceSemantics": payload["successfulResponsesWithPriceSemantics"],
                "resolvedTargets": sum(1 for item in resolutions if item["selected"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
