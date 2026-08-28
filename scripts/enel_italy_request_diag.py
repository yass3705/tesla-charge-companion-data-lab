#!/usr/bin/env python3
"""Diagnose the public Enel map station request without persisting auth material."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

MAP_URL = "https://d2jtbpdp94l0ts.cloudfront.net/?show_only_enel=true"
PREFIX = "https://emobility.enelx.com/api/emobility/v2/charging/station?"
OUT = Path("data/reports/enel_italy_request_diag.json")
SAFE_QUERY_KEYS = {"lat", "lon", "zoomLevel", "isPrivate", "managedByEnelX"}


def safe_business_response(obj):
    if not isinstance(obj, dict):
        return {"type": type(obj).__name__}
    safe = {}
    for key in ("message", "code", "status", "error", "errorCode", "description"):
        value = obj.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            if key in obj:
                safe[key] = value
    safe["topLevelKeys"] = sorted(map(str, obj.keys()))[:50]
    return safe


def main():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = webdriver.Chrome(options=options)
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.get(MAP_URL)
        time.sleep(15)
        logs = driver.get_log("performance")
        reqs, extra, response_ids = {}, {}, set()
        for item in logs:
            try:
                msg = json.loads(item["message"])["message"]
            except Exception:
                continue
            method, params = msg.get("method"), msg.get("params", {})
            rid = str(params.get("requestId") or "")
            if method == "Network.requestWillBeSent":
                reqs[rid] = params.get("request", {})
            elif method == "Network.requestWillBeSentExtraInfo":
                extra[rid] = {str(k): str(v) for k, v in (params.get("headers") or {}).items()}
            elif method == "Network.responseReceived":
                response_ids.add(rid)

        rid = next((r for r, req in reqs.items() if str(req.get("url") or "").startswith(PREFIX) and req.get("method") == "GET"), None)
        if not rid:
            raise RuntimeError("station GET not observed")
        req = reqs[rid]
        url = str(req.get("url"))
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        safe_query = {k: v for k, v in query.items() if k in SAFE_QUERY_KEYS}

        browser_body = None
        if rid in response_ids:
            try:
                raw = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": rid}).get("body") or ""
                browser_body = safe_business_response(json.loads(raw)) if raw else None
            except Exception as exc:
                browser_body = {"captureErrorType": type(exc).__name__}

        merged = {str(k): str(v) for k, v in (req.get("headers") or {}).items()}
        merged.update(extra.get(rid, {}))
        blocked = {"host", "content-length", "cookie", "referer", "origin", ":authority", ":method", ":path", ":scheme"}
        replay_headers = {k: v for k, v in merged.items() if k.lower() not in blocked and not k.startswith(":")}

        exact = requests.get(url, headers=replay_headers, timeout=45)
        try:
            exact_obj = exact.json()
        except Exception:
            exact_obj = None

        rome_query = {k: list(v) for k, v in query.items()}
        rome_query["lat"] = ["41.9028"]
        rome_query["lon"] = ["12.4964"]
        rome_query["zoomLevel"] = ["14"]
        flat = [(k, value) for k, values in rome_query.items() for value in values]
        rome_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(flat), parts.fragment))
        rome = requests.get(rome_url, headers=replay_headers, timeout=45)
        try:
            rome_obj = rome.json()
        except Exception:
            rome_obj = None

        report = {
            "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "security": {
                "authValuesPersisted": False,
                "cookiesPersisted": False,
                "onlySafeQueryValuesPersisted": True,
                "rawBodiesPersisted": False,
            },
            "observedSafeQuery": safe_query,
            "observedReplayHeaderNames": sorted(k.lower() for k in replay_headers),
            "browserObservedResponse": browser_body,
            "exactReplay": {
                "httpStatus": exact.status_code,
                "business": safe_business_response(exact_obj),
            },
            "romeReplay": {
                "httpStatus": rome.status_code,
                "business": safe_business_response(rome_obj),
            },
        }
    finally:
        driver.quit()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
