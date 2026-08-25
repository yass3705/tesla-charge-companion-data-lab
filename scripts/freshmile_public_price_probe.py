#!/usr/bin/env python3
"""Resolve Freshmile public EVSE tariffs with strict identity matching.

Freshmile's public driver API exposes location objects with nested EVSEs,
connectors and tariff descriptions. This probe uses only unauthenticated GETs.
It first tries an exact Freshmile location ref when one is known from the IRVE
station name, then falls back to a bounded geographic lookup. A tariff is
validated only when the returned EVSE custom_ref matches the IRVE/OCPI EVSE
identifier suffix. Nearby stations are never accepted as substitutes.
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
UA = "Tesla-Charge-Companion-Freshmile-Probe/1.3 (+public-GET-only)"
TARGETS = [
    {
        "evse": "FRFR1EPNFH1",
        "name": "Palavas-les-Flots - Hôtel Amérique",
        "latitude": 43.52927,
        "longitude": 3.92506,
        "location_ref": "LMGJ5N47IHDCDD",
        "scope": "direct_candidate",
    },
    {
        "evse": "FRFR1ELNHY1",
        "name": "Le Mans - Crédit Agricole Anjou Maine",
        "latitude": 48.01419,
        "longitude": 0.18728,
        "location_ref": "LM5M9K1802BBB6",
        "scope": "direct_candidate",
    },
    {
        "evse": "FRFR1ELZLB1",
        "name": "Natzwiller - Auberge Metzger",
        "latitude": 48.43651,
        "longitude": 7.25808,
        "location_ref": "AC2FNB43AS",
        "scope": "direct_candidate",
    },
    {
        "evse": "FRFR1EHYAP1",
        "name": "Rennes - Groupe Pandora",
        "latitude": 48.09679,
        "longitude": -1.62903,
        "location_ref": "WBFROMXNDZ",
        "scope": "direct_candidate",
    },
    {
        "evse": "FRFR1EUMAR1",
        "name": "Champdor-Corcelles - Place de la Mairie",
        "latitude": 46.01744,
        "longitude": 5.59686,
        "location_ref": "LMFMK9ROZVF5R3",
        "scope": "regional_control_siea",
    },
    {
        "evse": "FRFR1EBVFB2",
        "name": "Ajaccio - Hôtel Dolce Vita",
        "latitude": 41.9307,
        "longitude": 8.73422,
        "location_ref": None,
        "scope": "direct_candidate_negative_join_control",
    },
]
PRICE_WORDS = re.compile(
    r"\b(price|pricing|tariff|tariffs|tarif|tarifs|cost|fee|rate|kwh|minute|min|amount|currency|eur|euro)\b",
    re.I,
)
NUMBER = r"([0-9]+(?:[.,][0-9]+)?)"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read(768_000)
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
        "bodyPreview": re.sub(r"\s+", " ", text[:2500]).strip(),
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


def coordinates(record: dict[str, Any]) -> tuple[float, float] | None:
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
    coords = record.get("coordinates")
    if isinstance(coords, dict):
        lat = as_float(coords.get("latitude") if "latitude" in coords else coords.get("lat"))
        lon = as_float(
            coords.get("longitude")
            if "longitude" in coords
            else coords.get("lng", coords.get("lon"))
        )
        if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    if isinstance(coords, list) and len(coords) >= 2:
        lon, lat = as_float(coords[0]), as_float(coords[1])
        if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    return None


def distance_m(lat: float, lon: float, candidate: tuple[float, float] | None) -> float | None:
    if candidate is None:
        return None
    clat, clon = candidate
    r = 6_371_000.0
    p1, p2 = math.radians(lat), math.radians(clat)
    dp = math.radians(clat - lat)
    dl = math.radians(clon - lon)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def norm_token(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def target_ref_candidates(evse_id: str) -> set[str]:
    value = norm_token(evse_id)
    candidates = {value}
    if value.startswith("FRFR1E"):
        candidates.add(value[len("FRFR1E"):])
    if value.startswith("FRFR1"):
        candidates.add(value[len("FRFR1"):])
    return {item for item in candidates if item}


def data_locations(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [item for item in payload["data"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def find_target_evse(payload: Any, target: dict[str, Any]) -> dict[str, Any] | None:
    refs = target_ref_candidates(target["evse"])
    hits: list[dict[str, Any]] = []
    for location in data_locations(payload):
        for evse in location.get("evses") or []:
            if not isinstance(evse, dict):
                continue
            custom_ref = norm_token(evse.get("custom_ref"))
            if custom_ref not in refs:
                continue
            point = coordinates(location)
            hits.append(
                {
                    "location": location,
                    "evse": evse,
                    "distanceM": distance_m(target["latitude"], target["longitude"], point),
                }
            )
    if not hits:
        return None
    hits.sort(key=lambda item: item["distanceM"] if item["distanceM"] is not None else 1e12)
    return hits[0]


def parse_number(value: str) -> float:
    return float(value.replace(",", "."))


def duration_minutes(value: str, unit: str) -> float:
    number = parse_number(value)
    return number * 60.0 if unit.lower().startswith("hour") else number


def parse_tariff_description(description: str | None) -> dict[str, Any]:
    text = " ".join(str(description or "").replace("\r", "\n").split())
    out: dict[str, Any] = {"rawDescription": description}
    if not text:
        out["parseStatus"] = "missing_description"
        return out

    energy_patterns = [
        rf"(?:€|EUR)?\s*{NUMBER}\s*(?:€|EUR)?\s*(?:/|per)\s*(?:started\s*)?kwh",
        rf"{NUMBER}\s*(?:€|EUR)\s*(?:/|per)\s*(?:started\s*)?kwh",
    ]
    for pattern in energy_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            out["energyEurPerKwh"] = parse_number(match.group(1))
            break

    time_patterns = [
        rf"(?:€|EUR)?\s*{NUMBER}\s*(?:€|EUR)?\s*(?:/|per)\s*(?:started\s*)?(?:min|minute)",
        rf"{NUMBER}\s*(?:€|EUR)\s*(?:/|per)\s*(?:started\s*)?(?:min|minute)",
    ]
    for pattern in time_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            out["timeEurPerMinute"] = parse_number(match.group(1))
            break

    threshold = re.search(
        rf"after\s+{NUMBER}\s*(minutes?|mins?|hours?|hrs?)",
        text,
        re.I,
    )
    threshold_minutes = None
    if threshold:
        threshold_minutes = duration_minutes(threshold.group(1), threshold.group(2))

    flat = re.search(
        rf"after\s+{NUMBER}\s*(minutes?|mins?|hours?|hrs?).{{0,100}}?(?:€|EUR)\s*{NUMBER}\s*(?:flat\s*fee|fee\b)",
        text,
        re.I,
    )
    if flat:
        out["delayedFlatFee"] = {
            "afterMinutes": duration_minutes(flat.group(1), flat.group(2)),
            "amountEur": parse_number(flat.group(3)),
        }
    elif threshold_minutes is not None and "timeEurPerMinute" in out:
        out["timeFeeStartsAfterMinutes"] = threshold_minutes

    if re.search(r"continues as long as .*plugged|pricing continues as long as .*plugged", text, re.I):
        out["continuesWhilePluggedIn"] = True

    component_keys = {
        "energyEurPerKwh",
        "timeEurPerMinute",
        "delayedFlatFee",
    }
    out["parseStatus"] = (
        "parsed_components" if any(key in out for key in component_keys) else "description_unparsed"
    )
    return out


def money_object(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    amount = as_float(value.get("amount"))
    currency = value.get("currency")
    if amount is None and currency is None:
        return None
    return {"amount": amount, "currency": currency}


def extract_tariffs(evse: dict[str, Any]) -> list[dict[str, Any]]:
    tariffs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for connector in evse.get("connectors") or []:
        if not isinstance(connector, dict):
            continue
        tariff = connector.get("tariff")
        if not isinstance(tariff, dict):
            continue
        identity = str(tariff.get("id") or tariff.get("custom_ref") or tariff.get("description") or "")
        if identity in seen:
            continue
        seen.add(identity)
        parsed = parse_tariff_description(tariff.get("description"))
        tariffs.append(
            {
                "tariffId": tariff.get("id"),
                "tariffRef": tariff.get("custom_ref") or tariff.get("origin_ref"),
                "name": tariff.get("name"),
                "currency": tariff.get("currency"),
                "isFree": bool(tariff.get("is_free")),
                "isPreferential": bool(tariff.get("is_preferential")),
                "commissionedAt": tariff.get("commissioned_at"),
                "components": parsed,
                "provisionHold": money_object(tariff.get("provision")),
                "paymentAuthorizationHold": money_object(tariff.get("payment_authorization_amount")),
                "maxPrice": money_object(tariff.get("max_price")),
                "connector": {
                    "id": connector.get("id"),
                    "powerKw": connector.get("power"),
                    "standard": connector.get("standard"),
                },
            }
        )
    return tariffs


def tariff_is_validated(tariff: dict[str, Any]) -> bool:
    if tariff.get("currency") != "EUR" or tariff.get("isFree"):
        return False
    components = tariff.get("components") or {}
    return components.get("parseStatus") == "parsed_components"


def slim_response(response: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in response.items() if key != "json"}


def resolve_target(target: dict[str, Any], requests: list[dict[str, Any]]) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    hit = None

    if target.get("location_ref"):
        exact = request_json(url("/locations", {"filter[ref]": target["location_ref"]}))
        requests.append(slim_response(exact))
        hit = find_target_evse(exact.get("json"), target)
        attempts.append(
            {
                "kind": "location_ref",
                "status": exact.get("status"),
                "matchedEvse": bool(hit),
                "priceSemanticTerms": exact.get("priceSemanticTerms") or [],
            }
        )

    if hit is None:
        geo = request_json(
            url(
                "/locations",
                {
                    "order_by[latitude]": target["latitude"],
                    "order_by[longitude]": target["longitude"],
                },
            )
        )
        requests.append(slim_response(geo))
        hit = find_target_evse(geo.get("json"), target)
        attempts.append(
            {
                "kind": "geo",
                "status": geo.get("status"),
                "matchedEvse": bool(hit),
                "priceSemanticTerms": geo.get("priceSemanticTerms") or [],
            }
        )

    resolution: dict[str, Any] = {
        "target": target,
        "attempts": attempts,
        "matched": bool(hit),
        "validatedTariffs": [],
    }
    if hit is None:
        return resolution

    location = hit["location"]
    evse = hit["evse"]
    tariffs = extract_tariffs(evse)
    validated = [item for item in tariffs if tariff_is_validated(item)]
    resolution.update(
        {
            "location": {
                "id": location.get("id"),
                "ref": location.get("ref"),
                "name": location.get("name"),
                "address": location.get("address"),
                "coordinates": location.get("coordinates"),
                "distanceM": hit.get("distanceM"),
            },
            "matchedEvse": {
                "id": evse.get("id"),
                "customRef": evse.get("custom_ref"),
                "status": evse.get("status"),
                "isRemoteCapable": evse.get("is_remote_capable"),
            },
            "tariffs": tariffs,
            "validatedTariffs": validated,
        }
    )
    return resolution


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    requests: list[dict[str, Any]] = []
    resolutions = [resolve_target(target, requests) for target in TARGETS]
    matched_target_count = sum(1 for item in resolutions if item["matched"])
    validated_tariff_count = sum(len(item["validatedTariffs"]) for item in resolutions)
    direct_validated_count = sum(
        len(item["validatedTariffs"])
        for item in resolutions
        if item["target"].get("scope") == "direct_candidate"
    )
    successful = [item for item in requests if item.get("status") in {200, 206}]
    semantic = [item for item in successful if item.get("priceSemanticTerms")]

    payload = {
        "schemaVersion": "1.3.0",
        "generatedAt": now_iso(),
        "baseUrl": BASE,
        "method": "unauthenticated public GET only",
        "targets": TARGETS,
        "requestCount": len(requests),
        "statusCounts": {},
        "successfulResponseCount": len(successful),
        "successfulResponsesWithPriceSemantics": len(semantic),
        "matchedTargetCount": matched_target_count,
        "validatedTariffCount": validated_tariff_count,
        "directCandidateValidatedTariffCount": direct_validated_count,
        "validatedExactPriceFound": validated_tariff_count > 0,
        "policy": (
            "A Freshmile tariff is validated only when the returned EVSE custom_ref matches the IRVE/OCPI EVSE suffix, "
            "the tariff currency is EUR, and explicit price components are parsed from that EVSE's tariff description. "
            "Provision/payment-authorization amounts are holds, not charging fees. Regional-control samples never authorize publication in the direct-CPO dataset."
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
                "matchedTargetCount": matched_target_count,
                "validatedTariffCount": validated_tariff_count,
                "directCandidateValidatedTariffCount": direct_validated_count,
                "validated": [
                    {
                        "evse": item["target"]["evse"],
                        "scope": item["target"].get("scope"),
                        "customRef": (item.get("matchedEvse") or {}).get("customRef"),
                        "tariffs": [tariff.get("components") for tariff in item["validatedTariffs"]],
                    }
                    for item in resolutions
                    if item["validatedTariffs"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
