#!/usr/bin/env python3
"""Fetch exact Freshmile direct-CPO tariffs from the public driver API.

Input is the already-pruned Freshmile direct inventory. For almost every
station the IRVE station name contains the exact Freshmile location ref as
``Freshmile France/<ref>``. The script calls only the public GET endpoint
``/locations?filter[ref]=...`` and accepts a tariff only when the returned EVSE
``custom_ref`` matches the IRVE/OCPI EVSE identifier suffix.

No nearby-location substitution is allowed. Regional networks must already be
removed by ``freshmile_prune_regional_networks.py`` before this script runs.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = "https://prod-driver-api.freshmile.com/charge/api/v2"
UA = "Tesla-Charge-Companion-Freshmile-Tariffs/1.0 (+public-GET-only)"
DEFAULT_INPUT = Path("data/national/freshmile_direct_stations_france.json.gz")
DEFAULT_OUTPUT = Path("reports/freshmile/direct_tariffs_sample.json.gz")
LOCATION_REF_RE = re.compile(r"^Freshmile France/([A-Z0-9]+)$", re.I)
NUMBER = r"([0-9]+(?:[.,][0-9]+)?)"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def norm_token(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def target_ref_candidates(evse_id: str) -> set[str]:
    value = norm_token(evse_id)
    out = {value}
    if value.startswith("FRFR1E"):
        out.add(value[len("FRFR1E"):])
    if value.startswith("FRFR1"):
        out.add(value[len("FRFR1"):])
    return {item for item in out if item}


def station_location_ref(station: dict[str, Any]) -> str | None:
    match = LOCATION_REF_RE.match(str(station.get("name") or "").strip())
    return match.group(1) if match else None


def request_json(location_ref: str, attempts: int = 3) -> dict[str, Any]:
    query = urllib.parse.urlencode({"filter[ref]": location_ref})
    url = f"{BASE}/locations?{query}"
    last: dict[str, Any] = {"url": url, "status": None, "json": None}
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(1_500_000)
                text = raw.decode("utf-8", errors="replace")
                parsed = json.loads(text)
                return {"url": url, "status": response.status, "json": parsed}
        except urllib.error.HTTPError as exc:
            raw = exc.read(128_000)
            text = raw.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            last = {"url": url, "status": exc.code, "json": parsed}
            if exc.code not in {429, 500, 502, 503, 504}:
                return last
        except Exception as exc:
            last = {"url": url, "status": None, "json": None, "error": f"{type(exc).__name__}: {exc}"}
        if attempt + 1 < attempts:
            time.sleep(0.75 * (attempt + 1))
    return last


def locations(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [item for item in payload["data"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def exact_location(payload: Any, location_ref: str) -> dict[str, Any] | None:
    wanted = norm_token(location_ref)
    for item in locations(payload):
        if norm_token(item.get("ref")) == wanted:
            return item
    return None


def parse_number(value: str) -> float:
    return float(value.replace(",", "."))


def duration_minutes(value: str, unit: str) -> float:
    number = parse_number(value)
    u = unit.lower()
    return number * 60.0 if u.startswith(("hour", "heure", "hr")) else number


def parse_tariff_description(description: str | None) -> dict[str, Any]:
    text = " ".join(str(description or "").replace("\r", "\n").split())
    out: dict[str, Any] = {"raw": description}
    if not text:
        out["status"] = "missing"
        return out

    energy_patterns = [
        rf"(?:€|EUR)?\s*{NUMBER}\s*(?:€|EUR)?\s*(?:/|per|par)\s*(?:started\s*)?kwh(?:\s*(?:started|entam[eé]e?))?",
        rf"{NUMBER}\s*(?:€|EUR)\s*(?:/|per|par)\s*(?:started\s*)?kwh(?:\s*(?:started|entam[eé]e?))?",
    ]
    for pattern in energy_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            out["energyEurPerKwh"] = parse_number(match.group(1))
            break

    time_patterns = [
        rf"(?:€|EUR)?\s*{NUMBER}\s*(?:€|EUR)?\s*(?:/|per|par)\s*(?:started\s*)?(?:min|minute)s?",
        rf"{NUMBER}\s*(?:€|EUR)\s*(?:/|per|par)\s*(?:started\s*)?(?:min|minute)s?",
    ]
    for pattern in time_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            out["timeEurPerMinute"] = parse_number(match.group(1))
            break

    session_patterns = [
        rf"(?:€|EUR)?\s*{NUMBER}\s*(?:€|EUR)?\s*(?:/|per|par)\s*(?:session|charge)",
        rf"{NUMBER}\s*(?:€|EUR)\s*(?:/|per|par)\s*(?:session|charge)",
    ]
    for pattern in session_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            out["sessionFeeEur"] = parse_number(match.group(1))
            break

    threshold = re.search(
        rf"(?:after|après|apres)\s+{NUMBER}\s*(minutes?|mins?|hours?|hrs?|heures?|h)\b",
        text,
        re.I,
    )
    threshold_minutes = None
    if threshold:
        threshold_minutes = duration_minutes(threshold.group(1), threshold.group(2))

    flat = re.search(
        rf"(?:after|après|apres)\s+{NUMBER}\s*(minutes?|mins?|hours?|hrs?|heures?|h)\b.{{0,120}}?(?:€|EUR)\s*{NUMBER}\s*(?:flat\s*fee|fee\b|forfait)",
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

    if re.search(
        r"continues as long as .*plugged|pricing continues as long as .*plugged|facturation .* tant que .*branch|tarification .* tant que .*branch",
        text,
        re.I,
    ):
        out["continuesWhilePluggedIn"] = True

    keys = {"energyEurPerKwh", "timeEurPerMinute", "sessionFeeEur", "delayedFlatFee"}
    out["status"] = "parsed" if any(key in out for key in keys) else "unparsed"
    return out


def money(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    amount = as_float(value.get("amount"))
    currency = value.get("currency")
    if amount is None and not currency:
        return None
    return {"amount": amount, "currency": currency}


def tariff_from_connector(connector: dict[str, Any]) -> dict[str, Any] | None:
    tariff = connector.get("tariff")
    if not isinstance(tariff, dict):
        return None
    parsed = parse_tariff_description(tariff.get("description"))
    is_free = bool(tariff.get("is_free"))
    is_preferential = bool(tariff.get("is_preferential"))
    currency = tariff.get("currency")
    validated = (
        not is_preferential
        and ((is_free and currency in {None, "EUR"}) or (currency == "EUR" and parsed.get("status") == "parsed"))
    )
    return {
        "tariffId": tariff.get("id"),
        "tariffRef": tariff.get("custom_ref") or tariff.get("origin_ref"),
        "name": tariff.get("name"),
        "currency": currency,
        "isFree": is_free,
        "isPreferential": is_preferential,
        "commissionedAt": tariff.get("commissioned_at"),
        "components": {"free": True, "status": "parsed"} if is_free else parsed,
        "provisionHold": money(tariff.get("provision")),
        "paymentAuthorizationHold": money(tariff.get("payment_authorization_amount")),
        "maxPrice": money(tariff.get("max_price")),
        "validated": validated,
        "tccRankable": validated,
        "source": "freshmile_public_driver_api",
        "connector": {
            "id": connector.get("id"),
            "powerKw": connector.get("power"),
            "standard": connector.get("standard"),
        },
    }


def match_evse(location: dict[str, Any], evse_id: str) -> dict[str, Any] | None:
    refs = target_ref_candidates(evse_id)
    for evse in location.get("evses") or []:
        if isinstance(evse, dict) and norm_token(evse.get("custom_ref")) in refs:
            return evse
    return None


def process_station(station: dict[str, Any], sleep_ms: int) -> tuple[dict[str, Any], dict[str, int]]:
    stats = {
        "requests": 0,
        "http200": 0,
        "locationMatched": 0,
        "evseMatched": 0,
        "tariffFound": 0,
        "tariffValidated": 0,
        "tariffUnparsed": 0,
        "missingLocationRef": 0,
    }
    ref = station_location_ref(station)
    out = {
        "stationId": station.get("stationId"),
        "name": station.get("name"),
        "address": station.get("address"),
        "coordinates": station.get("coordinates"),
        "locationRef": ref,
        "locationId": None,
        "chargePoints": [],
    }
    if not ref:
        stats["missingLocationRef"] = 1
        return out, stats

    response = request_json(ref)
    stats["requests"] = 1
    if sleep_ms > 0:
        time.sleep(sleep_ms / 1000.0)
    if response.get("status") == 200:
        stats["http200"] = 1
    location = exact_location(response.get("json"), ref)
    if location is None:
        return out, stats
    stats["locationMatched"] = 1
    out["locationId"] = location.get("id")
    out["locationName"] = location.get("name")

    for point in station.get("chargePoints") or []:
        evse_id = point.get("evseId")
        evse = match_evse(location, evse_id)
        point_out = {
            "evseId": evse_id,
            "powerKw": point.get("powerKw"),
            "kind": point.get("kind"),
            "matched": evse is not None,
            "freshmileEvseId": evse.get("id") if evse else None,
            "freshmileCustomRef": evse.get("custom_ref") if evse else None,
            "status": evse.get("status") if evse else None,
            "tariffs": [],
        }
        if evse is not None:
            stats["evseMatched"] += 1
            seen = set()
            for connector in evse.get("connectors") or []:
                if not isinstance(connector, dict):
                    continue
                tariff = tariff_from_connector(connector)
                if tariff is None:
                    continue
                identity = (tariff.get("tariffId"), tariff.get("connector", {}).get("standard"), tariff.get("connector", {}).get("powerKw"))
                if identity in seen:
                    continue
                seen.add(identity)
                point_out["tariffs"].append(tariff)
                stats["tariffFound"] += 1
                if tariff["validated"]:
                    stats["tariffValidated"] += 1
                elif (tariff.get("components") or {}).get("status") == "unparsed":
                    stats["tariffUnparsed"] += 1
        out["chargePoints"].append(point_out)
    return out, stats


def read_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_gzip_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def evenly_spaced_sample(items: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    if size <= 0 or size >= len(items):
        return items
    if size == 1:
        return [items[0]]
    indices = sorted({round(i * (len(items) - 1) / (size - 1)) for i in range(size)})
    return [items[i] for i in indices]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-size", type=int, default=120)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--sleep-ms", type=int, default=75)
    args = parser.parse_args()

    inventory = read_gzip_json(args.input)
    stations = list(inventory.get("stations") or [])
    selected = stations if args.all else evenly_spaced_sample(stations, args.sample_size)

    totals = {
        "stationsInInventory": len(stations),
        "chargePointsInInventory": sum(len(s.get("chargePoints") or []) for s in stations),
        "stationsSelected": len(selected),
        "requests": 0,
        "http200": 0,
        "locationMatched": 0,
        "evseMatched": 0,
        "tariffFound": 0,
        "tariffValidated": 0,
        "tariffUnparsed": 0,
        "missingLocationRef": 0,
    }
    results = []
    for index, station in enumerate(selected, 1):
        result, stats = process_station(station, args.sleep_ms)
        results.append(result)
        for key, value in stats.items():
            totals[key] += value
        if index % 25 == 0 or index == len(selected):
            print(json.dumps({"progress": index, "selected": len(selected), "stats": totals}, ensure_ascii=False))

    direct_ref_count = sum(1 for station in stations if station_location_ref(station))
    direct_ref_evse_count = sum(
        len(station.get("chargePoints") or [])
        for station in stations
        if station_location_ref(station)
    )
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "freshmile-direct-cpo-tariffs-france",
        "generatedAt": now_iso(),
        "completeNationalScan": bool(args.all),
        "method": "Freshmile public driver API exact location ref + strict EVSE custom_ref join",
        "sourceInventoryGeneratedAt": inventory.get("generatedAt"),
        "scope": inventory.get("scope"),
        "regionalNetworkAudit": inventory.get("regionalNetworkAudit"),
        "policy": {
            "nearbyStationSubstitutionAllowed": False,
            "regionalNetworksIncluded": False,
            "preferentialTariffRankableByDefault": False,
            "provisionAndAuthorizationAreChargingFees": False,
            "unparsedDescriptionRankable": False,
            "publishToTccStableAllowed": False,
        },
        "coverage": {
            "stationsWithExactFreshmileLocationRef": direct_ref_count,
            "chargePointsCoveredByExactFreshmileLocationRef": direct_ref_evse_count,
            "stationCoveragePct": round(100 * direct_ref_count / len(stations), 4) if stations else 0,
            "chargePointCoveragePct": round(100 * direct_ref_evse_count / totals["chargePointsInInventory"], 4) if totals["chargePointsInInventory"] else 0,
        },
        "stats": totals,
        "stations": results,
    }
    write_gzip_json(args.output, payload)
    print(json.dumps({"output": str(args.output), "coverage": payload["coverage"], "stats": totals}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
