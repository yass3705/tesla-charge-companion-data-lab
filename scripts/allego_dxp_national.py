#!/usr/bin/env python3
"""Build exact Allego France CPO-direct tariffs from Allego's public DXP web client.

Official Data.gouv IRVE rows provide the France inventory and coordinates. Allego
DXP is the only tariff source. Country defaults are diagnostics only and are
never rankable. Ambiguous energy prices and unparsed time/blocking fees fail
closed so TCC never underestimates a direct Allego session.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

SPA = "https://app.allego.eu/price/FRALLEGO8001301"
API = "https://p-dxp-api-acg8edbwd7g2eheg.a01.azurefd.net/api/dxp/poi/chargepoints/"
DATA = "https://www.data.gouv.fr/fr/datasets/r/6523db3c-05f2-4c61-9308-e53a92deab37"
OUT = Path("data/national/allego_direct_stations_france.json.gz")
REPORT = Path("data/reports/allego_station_tariffs_report.json")
COUNTRY_DEFAULTS = {"regular": 0.39, "fast": 0.49, "ultraFast": 0.59}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def capture_public_client_key() -> str:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = webdriver.Chrome(options=options)
    key = None
    try:
        driver.get(SPA)
        time.sleep(6)
        for item in driver.get_log("performance"):
            try:
                msg = json.loads(item["message"])["message"]
            except Exception:
                continue
            if msg.get("method") != "Network.requestWillBeSent":
                continue
            req = msg.get("params", {}).get("request", {})
            if "p-dxp-api-" not in req.get("url", ""):
                continue
            for name, value in (req.get("headers") or {}).items():
                if name.lower() == "ocp-apim-subscription-key":
                    key = str(value)
                    break
            if key:
                break
    finally:
        driver.quit()
    if not key:
        raise RuntimeError("Allego public DXP client key was not observed")
    print("DXP public client configuration captured; sha256=" + hashlib.sha256(key.encode()).hexdigest())
    return key


def _float(value: Any):
    try:
        if value in (None, ""):
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def parse_coordinates(row: dict[str, Any]) -> list[float] | None:
    for lat_key, lon_key in (
        ("consolidated_latitude", "consolidated_longitude"),
        ("latitude", "longitude"),
    ):
        lat, lon = _float(row.get(lat_key)), _float(row.get(lon_key))
        if lat is not None and lon is not None and 41 <= lat <= 52 and -6 <= lon <= 11:
            return [lat, lon]
    raw = str(row.get("coordonneesXY") or row.get("coordonnees_xy") or "").strip()
    if raw:
        try:
            pair = json.loads(raw)
            if isinstance(pair, list) and len(pair) >= 2:
                a, b = _float(pair[0]), _float(pair[1])
            else:
                a = b = None
        except Exception:
            nums = re.findall(r"-?\d+(?:[.,]\d+)?", raw)
            a, b = (_float(nums[0]), _float(nums[1])) if len(nums) >= 2 else (None, None)
        if a is not None and b is not None:
            if 41 <= b <= 52 and -6 <= a <= 11:
                return [b, a]
            if 41 <= a <= 52 and -6 <= b <= 11:
                return [a, b]
    return None


def fetch_inventory() -> tuple[list[dict[str, Any]], int]:
    req = urllib.request.Request(DATA, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8-sig", "replace")
    dialect = csv.Sniffer().sniff(raw[:12000], delimiters=",;\t")
    rows = list(csv.DictReader(io.StringIO(raw), dialect=dialect))
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        evse = None
        for field in ("id_pdc_itinerance", "id_pdc_local", "id_pdc"):
            value = str(row.get(field) or "").upper().strip().replace("*", "")
            match = re.search(r"FRALLEGO[0-9A-Z_-]+", value)
            if match:
                evse = match.group(0)
                break
        if not evse:
            continue
        power = _float(row.get("puiss_max"))
        out.setdefault(evse, {
            "evseId": evse,
            "stationId": str(row.get("id_station_itinerance") or row.get("id_station_local") or "").strip() or None,
            "stationName": str(row.get("nom_station") or "").strip() or None,
            "address": str(row.get("adresse_station") or "").strip() or None,
            "city": str(row.get("consolidated_commune") or row.get("nom_commune") or "").strip() or None,
            "coordinates": parse_coordinates(row),
            "powerKwPublished": power,
            "powerKw": power,
            "kind": "DC" if power is not None and power > 22.5 else "AC",
            "source": "allego-data-gouv",
        })
    return sorted(out.values(), key=lambda x: x["evseId"]), len(rows)


def candidate_ids(evse_id: str) -> list[str]:
    cands = []
    if re.fullmatch(r"FRALLEGO[0-9]+", evse_id) and len(evse_id) > len("FRALLEGO") + 2:
        cands.append(evse_id[:-1])
    cands.append(evse_id)
    return list(dict.fromkeys(cands))


def call_dxp(chargepoint_id: str, key: str) -> tuple[int, str]:
    req = urllib.request.Request(API + chargepoint_id, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://app.allego.eu",
        "Referer": "https://app.allego.eu/",
        "Ocp-Apim-Subscription-Key": key,
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"


def parse_price_text(text: str) -> tuple[list[float], list[dict[str, Any]]]:
    rates = sorted(set(
        float(v.replace(",", "."))
        for v in re.findall(r"(\d+(?:[.,]\d+)?)\s*EUR\s*/?\s*kWh", text or "", re.I)
        if 0.05 <= float(v.replace(",", ".")) <= 2.0
    ))
    fees = []
    for value, unit in re.findall(r"(\d+(?:[.,]\d+)?)\s*EUR\s*/\s*(minute|min|heure|hour)", text or "", re.I):
        val = float(value.replace(",", "."))
        if 0 <= val <= 10:
            fees.append({"value": val, "unit": unit.lower()})
    return rates, fees


def extract_price_info(obj: dict[str, Any]) -> str:
    prices = obj.get("prices") if isinstance(obj, dict) else None
    if isinstance(prices, dict):
        value = prices.get("priceInfoDirectPayment")
        if isinstance(value, str):
            return value
    return ""


def resolve_evse(item: dict[str, Any], key: str) -> dict[str, Any]:
    evse_id = item["evseId"]
    status = None
    body = ""
    chosen = None
    for cid in candidate_ids(evse_id):
        status, body = call_dxp(cid, key)
        if status == 200:
            chosen = cid
            break
    obj = None
    if status == 200:
        try:
            obj = json.loads(body)
        except Exception:
            obj = None
    obj = obj if isinstance(obj, dict) else {}
    info = extract_price_info(obj)
    rates, fee_candidates = parse_price_text(info)
    direct = rates[0] if len(rates) == 1 else None
    own = obj.get("isOwnNetwork")
    unparsed_time_fee = bool(fee_candidates)
    rankable = bool(status == 200 and direct is not None and own is not False and not unparsed_time_fee)
    address = obj.get("address") if isinstance(obj.get("address"), dict) else {}
    result = dict(item)
    result.update({
        "resolvedChargePointId": chosen,
        "dxpChargePointId": chosen,
        "dxpStatus": status,
        "brand": obj.get("brand"),
        "isOwnNetwork": own,
        "subscriberDiscountApplicable": obj.get("subscriberDiscountApplicable"),
        "maxPowerKw": _float(obj.get("maxPowerKw")),
        "dxpAddress": {
            "street": address.get("street") or address.get("addressLine"),
            "postalCode": address.get("postalCode") or address.get("zipCode"),
            "city": address.get("city"),
            "country": address.get("country"),
        } if address else None,
        "directEurPerKwh": direct if rankable else None,
        "parsedEnergyRateEurPerKwh": direct,
        "allDirectRateCandidatesEurPerKwh": rates,
        "feeCandidates": fee_candidates,
        "specialTariff": obj.get("specialTariff"),
        "priceTextPresent": bool(info),
        "rankableDirect": rankable,
        "blockingReason": None if rankable else (
            "not_allego_own_network" if own is False else
            "unparsed_time_or_blocking_fee" if unparsed_time_fee else
            "ambiguous_or_missing_direct_kwh_rate" if status == 200 else
            f"dxp_http_{status}"
        ),
    })
    return result


def station_group_key(row: dict[str, Any]) -> str:
    station_id = str(row.get("stationId") or "").strip()
    if station_id:
        return "id:" + station_id
    coords = row.get("coordinates") or []
    return "fallback:" + "|".join([
        str(row.get("stationName") or "").strip().lower(),
        str(row.get("address") or "").strip().lower(),
        f"{float(coords[0]):.5f},{float(coords[1]):.5f}" if len(coords) >= 2 else "",
    ])


def build_stations(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        groups[station_group_key(row)].append(row)
    stations = []
    for key, evses in groups.items():
        coords = [tuple(x["coordinates"]) for x in evses if isinstance(x.get("coordinates"), list) and len(x["coordinates"]) >= 2]
        coordinate = list(Counter(coords).most_common(1)[0][0]) if coords else None
        ids = sorted({str(x.get("stationId") or "") for x in evses if x.get("stationId")})
        names = [str(x.get("stationName") or "") for x in evses if x.get("stationName")]
        addresses = [str(x.get("address") or "") for x in evses if x.get("address")]
        rankable_count = sum(1 for x in evses if x.get("rankableDirect"))
        status = "exact_official_evse" if rankable_count == len(evses) else ("exact_official_station_partial" if rankable_count else "lookup_required")
        stations.append({
            "stationKey": key,
            "stationId": ids[0] if ids else None,
            "irveStationIds": ids,
            "name": Counter(names).most_common(1)[0][0] if names else "Station Allego",
            "address": Counter(addresses).most_common(1)[0][0] if addresses else None,
            "irveAddress": Counter(addresses).most_common(1)[0][0] if addresses else None,
            "coordinates": coordinate,
            "pricingStatus": status,
            "rankableDirect": rankable_count > 0,
            "rankableEvseCount": rankable_count,
            "evseCount": len(evses),
            "evses": evses,
        })
    stations.sort(key=lambda x: (x.get("name") or "", x.get("stationId") or x.get("stationKey") or ""))
    return stations


def main() -> None:
    key = capture_public_client_key()
    inventory, official_rows = fetch_inventory()
    print(f"Official Allego France inventory: rows={official_rows}, uniqueEVSE={len(inventory)}")
    if len(inventory) < 500:
        raise RuntimeError(f"Allego France EVSE inventory unexpectedly small: {len(inventory)}")

    results = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {pool.submit(resolve_evse, item, key): item["evseId"] for item in inventory}
        for idx, fut in enumerate(as_completed(futures), 1):
            results.append(fut.result())
            if idx % 250 == 0:
                ok = sum(1 for x in results if x["rankableDirect"])
                print(f"DXP {idx}/{len(inventory)}; rankable={ok}")

    results.sort(key=lambda x: x["evseId"])
    stations = build_stations(results)
    rankable = [x for x in results if x["rankableDirect"]]
    blocked = [x for x in results if not x["rankableDirect"]]
    time_fee_blocked = [x for x in blocked if x.get("blockingReason") == "unparsed_time_or_blocking_fee"]
    rates: dict[str, int] = {}
    for row in rankable:
        key_rate = f"{row['directEurPerKwh']:.3f}"
        rates[key_rate] = rates.get(key_rate, 0) + 1
    stations_with_coordinates = sum(1 for station in stations if station.get("coordinates"))
    evses_with_coordinates = sum(1 for row in results if row.get("coordinates"))

    payload = {
        "schemaVersion": "3.0.0",
        "dataset": "allego-direct-operated-evse-france",
        "generatedAt": now_iso(),
        "operator": "Allego",
        "country": "FR",
        "scope": {
            "operatorDirectOnly": True,
            "roamingIncluded": False,
            "exactEvsePriceRequiredForRanking": True,
            "countryDefaultsAreRankable": False,
            "exactDirectPricesFromDxp": True,
            "unparsedTimeFeesAreRankable": False,
            "countryDefaultsEurPerKwh": COUNTRY_DEFAULTS,
        },
        "sources": {
            "inventory": DATA,
            "tariffBackend": "Allego DXP public web client",
            "priceApp": "https://app.allego.eu/price/<FRALLEGO_EVSE_ID>",
        },
        "counts": {
            "officialRows": official_rows,
            "franceStationCount": len(stations),
            "franceEvseCount": len(results),
            "rankableEvseCount": len(rankable),
            "blockedEvseCount": len(blocked),
            "timeFeeBlockedEvseCount": len(time_fee_blocked),
            "coveragePct": round(100 * len(rankable) / len(results), 2) if results else 0,
            "stationsWithCoordinates": stations_with_coordinates,
            "irveLinkedEvseCount": evses_with_coordinates,
            "rankableStationCount": sum(1 for station in stations if station["rankableDirect"]),
            "distinctDirectRatesEurPerKwh": rates,
        },
        "matchPolicy": {
            "exactEvseIdFirst": True,
            "operatorMustBeAllego": True,
            "ambiguousOrDefaultOnlyFailsClosed": True,
            "unparsedTimeFeeFailsClosed": True,
        },
        "stations": stations,
        "evses": results,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    OUT.write_bytes(gzip.compress(rendered.encode("utf-8"), compresslevel=9, mtime=0))

    report = {
        "generatedAt": payload["generatedAt"],
        "counts": payload["counts"],
        "publicationReadyEvseCount": len(rankable),
        "publicationReadyStationCount": payload["counts"]["rankableStationCount"],
        "blockedEvseCount": len(blocked),
        "blockedReasonCounts": dict(Counter(x.get("blockingReason") or "none" for x in blocked)),
        "blockedSample": [
            {
                "evseId": x["evseId"],
                "stationName": x.get("stationName"),
                "reason": x.get("blockingReason"),
                "status": x.get("dxpStatus"),
                "rateCandidates": x.get("allDirectRateCandidatesEurPerKwh"),
                "feeCandidates": x.get("feeCandidates"),
            }
            for x in blocked[:200]
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
