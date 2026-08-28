#!/usr/bin/env python3
"""Probe Enel X Way public map and station-detail endpoints in Italy.

The script reproduces the anonymous session created by Enel's public web map,
queries a few Italian city centres, then tests the public station-detail route
advertised by the frontend bundle with real station identifiers returned by
the map. Authentication material stays only in process memory and is never
written to reports or logs.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

MAP_URL = "https://d2jtbpdp94l0ts.cloudfront.net/?show_only_enel=true"
STATION_URL = "https://emobility.enelx.com/api/emobility/v2/charging/station"
OUT = Path("data/reports/enel_italy_station_probe.json")
OUT_MD = Path("data/reports/enel_italy_station_probe.md")
CITIES = [
    ("Rome", 41.9028, 12.4964),
    ("Milan", 45.4642, 9.1900),
    ("Bologna", 44.4949, 11.3426),
]
PRICE_TOKENS = ("price", "tariff", "cost", "rate", "fee", "penalty", "occup", "currency", "amount")
DETAIL_TOKENS = ("evse", "connector", "socket", "plug", "power", "status", "station", "address")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def recursive_paths(obj: Any, prefix: str = "", depth: int = 0, out: set[str] | None = None) -> set[str]:
    out = out if out is not None else set()
    if depth > 10 or len(out) > 12000:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            out.add(p)
            recursive_paths(v, p, depth + 1, out)
    elif isinstance(obj, list):
        for v in obj[:50]:
            recursive_paths(v, prefix + "[]", depth + 1, out)
    return out


def safe_shape(obj: Any, depth: int = 0) -> Any:
    if depth > 4:
        return type(obj).__name__
    if isinstance(obj, dict):
        return {str(k): safe_shape(v, depth + 1) for k, v in list(obj.items())[:40]}
    if isinstance(obj, list):
        return {
            "type": "list",
            "length": len(obj),
            "sampleShape": safe_shape(obj[0], depth + 1) if obj else None,
        }
    return type(obj).__name__


def extract_matching_scalars(obj: Any, tokens: tuple[str, ...], prefix: str = "", depth: int = 0, out: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    out = out if out is not None else []
    if depth > 10 or len(out) >= 120:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            if any(t in str(k).lower() for t in tokens) and (isinstance(v, (str, int, float, bool)) or v is None):
                value = v
                if isinstance(value, str) and len(value) > 250:
                    value = value[:250]
                out.append({"path": p, "value": value})
            extract_matching_scalars(v, tokens, p, depth + 1, out)
    elif isinstance(obj, list):
        for v in obj[:50]:
            extract_matching_scalars(v, tokens, prefix + "[]", depth + 1, out)
    return out


def extract_browser_station_headers() -> tuple[dict[str, str], dict[str, Any]]:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1200")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = webdriver.Chrome(options=options)
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.get(MAP_URL)
        time.sleep(15)
        logs = driver.get_log("performance")
        requests_by_id: dict[str, dict[str, Any]] = {}
        extra_headers: dict[str, dict[str, str]] = {}
        for item in logs:
            try:
                msg = json.loads(item["message"])["message"]
            except Exception:
                continue
            method = msg.get("method")
            params = msg.get("params", {})
            rid = str(params.get("requestId") or "")
            if method == "Network.requestWillBeSent":
                requests_by_id[rid] = params.get("request", {})
            elif method == "Network.requestWillBeSentExtraInfo":
                extra_headers[rid] = {str(k): str(v) for k, v in (params.get("headers") or {}).items()}
        chosen_id = None
        chosen_req = None
        for rid, req in requests_by_id.items():
            if str(req.get("url") or "").startswith(STATION_URL + "?") and str(req.get("method")) == "GET":
                chosen_id, chosen_req = rid, req
                break
        if not chosen_req:
            raise RuntimeError("public Enel station request was not observed")
        merged = {str(k): str(v) for k, v in (chosen_req.get("headers") or {}).items()}
        merged.update(extra_headers.get(chosen_id or "", {}))
        blocked = {"host", "content-length", "cookie", "referer", "origin", ":authority", ":method", ":path", ":scheme"}
        replay = {k: v for k, v in merged.items() if k.lower() not in blocked and not k.startswith(":")}
        diagnostic = {
            "observedStationRequest": True,
            "stationRequestHost": urlsplit(str(chosen_req.get("url"))).hostname,
            "stationRequestHeaderNames": sorted(set(k.lower() for k in replay)),
            "authorizationMaterialPersisted": False,
        }
        return replay, diagnostic
    finally:
        driver.quit()


def get_city_map(session: requests.Session, headers: dict[str, str], city: str, lat: float, lon: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    params = {
        "lat": lat,
        "lon": lon,
        "zoomLevel": 14,
        "isPrivate": "false",
        "managedByEnelX": "MANAGED_BY_ENELX_TRUE",
    }
    r = session.get(STATION_URL, params=params, headers=headers, timeout=45)
    row: dict[str, Any] = {"city": city, "httpStatus": r.status_code, "contentType": r.headers.get("content-type")}
    stations: list[dict[str, Any]] = []
    if r.status_code == 200:
        try:
            obj = r.json()
        except Exception:
            obj = None
        if isinstance(obj, dict):
            result = obj.get("result")
            if isinstance(result, list):
                stations = [x for x in result if isinstance(x, dict)]
            row.update({
                "businessMessage": obj.get("message"),
                "businessCode": obj.get("code"),
                "resultType": type(result).__name__,
                "resultLength": len(result) if isinstance(result, (list, dict)) else None,
                "responseShape": safe_shape(obj),
            })
    return row, stations


def probe_detail(session: requests.Session, headers: dict[str, str], station: dict[str, Any], identifier_kind: str) -> dict[str, Any]:
    ident = station.get(identifier_kind)
    row: dict[str, Any] = {
        "identifierKind": identifier_kind,
        "identifier": ident if isinstance(ident, (str, int, float, bool)) else None,
        "mapAddress": station.get("address"),
        "mapMaxPower": station.get("maxPower"),
        "mapStatus": station.get("status"),
    }
    if ident is None:
        row["skipped"] = "missing_identifier"
        return row
    url = STATION_URL + "/" + quote(str(ident), safe="")
    r = session.get(url, headers=headers, timeout=45)
    row["httpStatus"] = r.status_code
    row["contentType"] = r.headers.get("content-type")
    if r.status_code != 200:
        return row
    try:
        obj = r.json()
    except Exception:
        row["json"] = False
        return row
    row["json"] = True
    if isinstance(obj, dict):
        result = obj.get("result")
        row.update({
            "businessMessage": obj.get("message"),
            "businessCode": obj.get("code"),
            "resultType": type(result).__name__,
            "resultNonEmpty": bool(result),
            "responseShape": safe_shape(obj),
        })
    else:
        row["resultNonEmpty"] = bool(obj)
        row["responseShape"] = safe_shape(obj)
    paths = recursive_paths(obj)
    row["priceLikeKeyPaths"] = sorted(p for p in paths if any(t in p.lower() for t in PRICE_TOKENS))[:300]
    row["detailLikeKeyPaths"] = sorted(p for p in paths if any(t in p.lower() for t in DETAIL_TOKENS))[:300]
    row["priceLikeScalars"] = extract_matching_scalars(obj, PRICE_TOKENS)[:100]
    return row


def main() -> None:
    replay_headers, browser_diag = extract_browser_station_headers()
    session = requests.Session()
    city_results: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    for city, lat, lon in CITIES:
        row, stations = get_city_map(session, replay_headers, city, lat, lon)
        city_results.append(row)
        if city == "Rome":
            samples = stations[:3]
    detail_results: list[dict[str, Any]] = []
    for station in samples:
        for kind in ("num", "serialNumber"):
            detail_results.append(probe_detail(session, replay_headers, station, kind))
    detail_price_paths: Counter[str] = Counter()
    for row in detail_results:
        for p in row.get("priceLikeKeyPaths", []):
            detail_price_paths[p] += 1
    successful_detail = sum(1 for x in detail_results if x.get("httpStatus") == 200 and x.get("json") is True)
    nonempty_detail = sum(1 for x in detail_results if x.get("resultNonEmpty") is True)
    price_detail = sum(1 for x in detail_results if x.get("priceLikeKeyPaths"))
    report = {
        "generatedAt": now_iso(),
        "scope": "public_enel_map_and_station_detail_probe",
        "security": {
            "accountCredentialsUsed": False,
            "browserSessionMaterialKeptOnlyInMemory": True,
            "authorizationMaterialPersisted": False,
            "cookiesPersisted": False,
            "rawResponseBodiesPersisted": False,
        },
        "browser": browser_diag,
        "counts": {
            "cityQueries": len(CITIES),
            "successfulCityQueries": sum(1 for x in city_results if x.get("httpStatus") == 200),
            "mapStationsReturned": sum(int(x.get("resultLength") or 0) for x in city_results),
            "detailRequests": len(detail_results),
            "successfulDetailJsonResponses": successful_detail,
            "nonEmptyDetailResponses": nonempty_detail,
            "detailResponsesWithPriceEvidence": price_detail,
            "distinctDetailPriceLikeKeyPaths": len(detail_price_paths),
        },
        "cityResults": city_results,
        "detailProbe": detail_results,
        "commonDetailPriceLikeKeyPaths": detail_price_paths.most_common(300),
        "stationDataReady": any(int(x.get("resultLength") or 0) > 0 for x in city_results),
        "detailDataReady": nonempty_detail > 0,
        "priceDataSeenInDetail": price_detail > 0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(
        "# Enel Italy station/detail probe\n\n"
        f"- City queries successful: **{report['counts']['successfulCityQueries']}/{len(CITIES)}**\n"
        f"- Map stations returned: **{report['counts']['mapStationsReturned']}**\n"
        f"- Detail requests: **{report['counts']['detailRequests']}**\n"
        f"- Non-empty detail responses: **{nonempty_detail}**\n"
        f"- Detail responses with price evidence: **{price_detail}**\n"
        f"- Detail endpoint usable: **{'yes' if report['detailDataReady'] else 'no'}**\n"
        f"- Price data visible in detail: **{'yes' if report['priceDataSeenInDetail'] else 'no'}**\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "counts": report["counts"],
        "stationDataReady": report["stationDataReady"],
        "detailDataReady": report["detailDataReady"],
        "priceDataSeenInDetail": report["priceDataSeenInDetail"],
        "detailProbe": detail_results,
    }, ensure_ascii=False, indent=2)[:30000])


if __name__ == "__main__":
    main()
