#!/usr/bin/env python3
"""Build exact Allego France direct tariffs from Allego's public DXP web client.

The public app.allego.eu client is opened once to observe its public APIM client
header in memory. The value is never written to disk or logs. Allego's official
Data.gouv IRVE publication supplies the France EVSE inventory; Allego DXP is the
only tariff source. Country defaults are retained only as diagnostics.
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
        out.setdefault(evse, {
            "evseId": evse,
            "stationId": str(row.get("id_station_itinerance") or row.get("id_station_local") or "").strip() or None,
            "stationName": str(row.get("nom_station") or "").strip() or None,
            "address": str(row.get("adresse_station") or "").strip() or None,
            "city": str(row.get("consolidated_commune") or row.get("nom_commune") or "").strip() or None,
            "powerKwPublished": _float(row.get("puiss_max")),
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
    rankable = bool(status == 200 and direct is not None and own is not False)
    address = obj.get("address") if isinstance(obj.get("address"), dict) else {}
    result = dict(item)
    result.update({
        "resolvedChargePointId": chosen,
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
        "directEurPerKwh": direct,
        "allDirectRateCandidatesEurPerKwh": rates,
        "feeCandidates": fee_candidates,
        "specialTariff": obj.get("specialTariff"),
        "priceTextPresent": bool(info),
        "rankableDirect": rankable,
        "blockingReason": None if rankable else (
            "not_allego_own_network" if own is False else
            "ambiguous_or_missing_direct_kwh_rate" if status == 200 else
            f"dxp_http_{status}"
        ),
    })
    return result

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
    station_ids = {x["stationId"] for x in results if x.get("stationId")}
    rankable = [x for x in results if x["rankableDirect"]]
    blocked = [x for x in results if not x["rankableDirect"]]
    rates = {}
    for row in rankable:
        key_rate = f"{row['directEurPerKwh']:.3f}"
        rates[key_rate] = rates.get(key_rate, 0) + 1

    payload = {
        "schemaVersion": "2.0.0",
        "dataset": "allego-direct-operated-evse-france",
        "generatedAt": now_iso(),
        "operator": "Allego",
        "country": "FR",
        "scope": {
            "operatorDirectOnly": True,
            "roamingIncluded": False,
            "exactEvsePriceRequiredForRanking": True,
            "countryDefaultsAreRankable": False,
            "countryDefaultsEurPerKwh": COUNTRY_DEFAULTS,
        },
        "sources": {
            "inventory": DATA,
            "tariffBackend": "Allego DXP public web client",
            "priceApp": "https://app.allego.eu/price/<FRALLEGO_EVSE_ID>",
        },
        "counts": {
            "officialRows": official_rows,
            "franceStationCount": len(station_ids),
            "franceEvseCount": len(results),
            "rankableEvseCount": len(rankable),
            "blockedEvseCount": len(blocked),
            "coveragePct": round(100 * len(rankable) / len(results), 2) if results else 0,
            "distinctDirectRatesEurPerKwh": rates,
        },
        "matchPolicy": {
            "exactEvseIdFirst": True,
            "operatorMustBeAllego": True,
            "ambiguousOrDefaultOnlyFailsClosed": True,
        },
        "evses": results,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    OUT.write_bytes(gzip.compress(rendered.encode("utf-8"), compresslevel=9, mtime=0))

    report = {
        "generatedAt": payload["generatedAt"],
        "counts": payload["counts"],
        "publicationReadyEvseCount": len(rankable),
        "blockedEvseCount": len(blocked),
        "blockedSample": [
            {
                "evseId": x["evseId"],
                "stationName": x.get("stationName"),
                "reason": x.get("blockingReason"),
                "status": x.get("dxpStatus"),
                "rateCandidates": x.get("allDirectRateCandidatesEurPerKwh"),
            }
            for x in blocked[:200]
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
