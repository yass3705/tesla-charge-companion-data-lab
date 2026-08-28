#!/usr/bin/env python3
"""Target the public Enel map station endpoint in Italy using its browser session.

This probe obtains the same anonymous/public web-map session that the Enel map
creates in a browser, then replays only safe GET requests against the station
endpoint for several Italian city centres. Authentication material is kept only
in process memory and is never written to reports or logs.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

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
PRICE_TOKENS = ("price", "tariff", "cost", "rate", "fee", "penalty", "occup")
STATION_TOKENS = ("station", "evse", "connector", "socket", "chargepoint", "address", "latitude", "longitude", "operator")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def recursive_paths(obj: Any, prefix: str = "", depth: int = 0, out: set[str] | None = None) -> set[str]:
    out = out if out is not None else set()
    if depth > 9 or len(out) > 8000:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            out.add(p)
            recursive_paths(v, p, depth + 1, out)
    elif isinstance(obj, list):
        for v in obj[:30]:
            recursive_paths(v, prefix + "[]", depth + 1, out)
    return out


def safe_shape(obj: Any, depth: int = 0) -> Any:
    if depth > 3:
        return type(obj).__name__
    if isinstance(obj, dict):
        return {str(k): safe_shape(v, depth + 1) for k, v in list(obj.items())[:30]}
    if isinstance(obj, list):
        return {"type": "list", "length": len(obj), "sampleShape": safe_shape(obj[0], depth + 1) if obj else None}
    return type(obj).__name__


def find_candidate_objects(obj: Any, out: list[dict[str, Any]] | None = None, depth: int = 0) -> list[dict[str, Any]]:
    out = out if out is not None else []
    if depth > 10 or len(out) >= 100:
        return out
    if isinstance(obj, dict):
        keys = {str(k).lower() for k in obj}
        score = sum(any(token in k for token in STATION_TOKENS) for k in keys)
        if score >= 2:
            safe: dict[str, Any] = {}
            for k, v in obj.items():
                lk = str(k).lower()
                if any(t in lk for t in ("id", "name", "address", "city", "latitude", "longitude", "lat", "lon", "status", "power", "type", "operator")):
                    if isinstance(v, (str, int, float, bool)) or v is None:
                        safe[str(k)] = v
            if safe:
                out.append(safe)
        for v in obj.values():
            find_candidate_objects(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj[:200]:
            find_candidate_objects(v, out, depth + 1)
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
                req = params.get("request", {})
                requests_by_id[rid] = req
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
        # Keep only headers needed to reproduce this public GET. Never return
        # them in diagnostics; caller keeps them in memory only.
        blocked = {"host", "content-length", "cookie", "referer", "origin", ":authority", ":method", ":path", ":scheme"}
        replay = {k: v for k, v in merged.items() if k.lower() not in blocked and not k.startswith(":")}
        diagnostic = {
            "observedStationRequest": True,
            "stationRequestHost": urlsplit(str(chosen_req.get("url"))).hostname,
            "stationRequestHeaderNames": sorted(k.lower() for k in replay),
            "authorizationMaterialPersisted": False,
        }
        return replay, diagnostic
    finally:
        driver.quit()


def main() -> None:
    replay_headers, browser_diag = extract_browser_station_headers()
    session = requests.Session()
    city_results = []
    total_candidates = 0
    price_paths: Counter[str] = Counter()
    station_paths: Counter[str] = Counter()

    for city, lat, lon in CITIES:
        params = {
            "lat": lat,
            "lon": lon,
            "zoomLevel": 14,
            "isPrivate": "false",
            "managedByEnelX": "true",
        }
        r = session.get(STATION_URL, params=params, headers=replay_headers, timeout=45)
        row: dict[str, Any] = {"city": city, "httpStatus": r.status_code, "contentType": r.headers.get("content-type")}
        if r.status_code == 200:
            try:
                obj = r.json()
            except Exception:
                obj = None
            if obj is not None:
                paths = recursive_paths(obj)
                prices = sorted(p for p in paths if any(t in p.lower() for t in PRICE_TOKENS))
                stations = sorted(p for p in paths if any(t in p.lower() for t in STATION_TOKENS))
                for p in prices:
                    price_paths[p] += 1
                for p in stations:
                    station_paths[p] += 1
                candidates = find_candidate_objects(obj)
                total_candidates += len(candidates)
                row.update({
                    "responseShape": safe_shape(obj),
                    "keyPathCount": len(paths),
                    "priceLikeKeyPaths": prices[:300],
                    "stationLikeKeyPaths": stations[:300],
                    "candidateStationObjectCount": len(candidates),
                    "candidateStationObjectSample": candidates[:10],
                })
        city_results.append(row)

    report = {
        "generatedAt": now_iso(),
        "scope": "public_enel_map_targeted_station_get",
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
            "candidateStationObjects": total_candidates,
            "distinctStationLikeKeyPaths": len(station_paths),
            "distinctPriceLikeKeyPaths": len(price_paths),
        },
        "cityResults": city_results,
        "commonStationLikeKeyPaths": station_paths.most_common(300),
        "commonPriceLikeKeyPaths": price_paths.most_common(300),
        "stationDataReady": total_candidates > 0,
        "priceDataSeen": bool(price_paths),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(
        "# Enel Italy targeted station probe\n\n"
        f"- Successful city queries: **{report['counts']['successfulCityQueries']}/{len(CITIES)}**\n"
        f"- Candidate station objects: **{total_candidates}**\n"
        f"- Distinct station-like JSON paths: **{len(station_paths)}**\n"
        f"- Distinct price-like JSON paths: **{len(price_paths)}**\n"
        f"- Station data ready for detail probing: **{'yes' if report['stationDataReady'] else 'no'}**\n"
        f"- Price data already visible at map level: **{'yes' if report['priceDataSeen'] else 'no'}**\n",
        encoding="utf-8",
    )
    print(json.dumps({"counts": report["counts"], "stationDataReady": report["stationDataReady"], "priceDataSeen": report["priceDataSeen"]}, ensure_ascii=False, indent=2))
    print(json.dumps(city_results, ensure_ascii=False)[:12000])


if __name__ == "__main__":
    main()
