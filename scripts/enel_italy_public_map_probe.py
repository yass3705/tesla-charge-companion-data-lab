#!/usr/bin/env python3
"""Discover the public Enel On Your Way map backend without using account credentials.

The current Pay per Use Basic terms state that the applicable unit price may vary
by charging point and is shown on the station detail page in the app. This probe
therefore does not assume a nationwide price. It loads Enel's public web map in a
headless browser, captures public XHR/fetch traffic, and records only sanitized
endpoint metadata plus JSON key evidence useful for a later station-price probe.

No request headers, cookies, authorization values, query-string values, or raw
response bodies are persisted.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

MAP_URL = "https://d2jtbpdp94l0ts.cloudfront.net/?show_only_enel=true"
OUT = Path("data/reports/enel_italy_public_map_probe.json")
OUT_MD = Path("data/reports/enel_italy_public_map_probe.md")
INTERESTING = ("price", "tariff", "cost", "rate", "fee", "evse", "connector", "station", "charge", "operator", "cpo", "poi")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize_url(url: str) -> dict[str, Any]:
    parts = urlsplit(url)
    return {
        "scheme": parts.scheme,
        "host": parts.hostname,
        "path": parts.path or "/",
        "queryKeys": sorted({k for k, _ in parse_qsl(parts.query, keep_blank_values=True)}),
    }


def collect_keys(obj: Any, prefix: str = "", *, depth: int = 0, out: set[str] | None = None) -> set[str]:
    out = out if out is not None else set()
    if depth > 7 or len(out) > 3000:
        return out
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_s = str(key)
            path = f"{prefix}.{key_s}" if prefix else key_s
            out.add(path)
            collect_keys(value, path, depth=depth + 1, out=out)
    elif isinstance(obj, list):
        for value in obj[:10]:
            collect_keys(value, prefix + "[]", depth=depth + 1, out=out)
    return out


def interesting_key_paths(paths: set[str]) -> list[str]:
    return sorted(p for p in paths if any(token in p.lower() for token in INTERESTING))[:300]


def main() -> None:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1200")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL", "browser": "ALL"})

    driver = webdriver.Chrome(options=options)
    responses: dict[str, dict[str, Any]] = {}
    request_meta: dict[str, dict[str, Any]] = {}
    bodies_scanned = 0
    browser_errors: list[str] = []
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.get(MAP_URL)
        time.sleep(15)

        # A small amount of movement/zoom triggers viewport APIs without trying
        # to guess DOM marker implementations.
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 3)")
        except Exception:
            pass
        time.sleep(3)

        logs = driver.get_log("performance")
        for item in logs:
            try:
                msg = json.loads(item["message"])["message"]
            except Exception:
                continue
            method = msg.get("method")
            params = msg.get("params", {})
            if method == "Network.requestWillBeSent":
                req = params.get("request", {})
                rid = str(params.get("requestId") or "")
                url = str(req.get("url") or "")
                rtype = str(params.get("type") or "")
                if rid and url.startswith(("http://", "https://")):
                    request_meta[rid] = {
                        "url": sanitize_url(url),
                        "method": req.get("method"),
                        "resourceType": rtype,
                    }
            elif method == "Network.responseReceived":
                rid = str(params.get("requestId") or "")
                resp = params.get("response", {})
                if rid in request_meta:
                    responses[rid] = {
                        **request_meta[rid],
                        "status": resp.get("status"),
                        "mimeType": resp.get("mimeType"),
                    }

        endpoint_rows = []
        hosts = Counter()
        for rid, row in responses.items():
            resource_type = str(row.get("resourceType") or "")
            mime = str(row.get("mimeType") or "").lower()
            path = str((row.get("url") or {}).get("path") or "")
            likely_api = resource_type in {"XHR", "Fetch"} or "json" in mime or any(x in path.lower() for x in ("api", "graphql", "station", "charge", "poi"))
            if not likely_api:
                continue
            host = str((row.get("url") or {}).get("host") or "")
            hosts[host] += 1
            evidence: dict[str, Any] = {}
            if "json" in mime and bodies_scanned < 40:
                try:
                    body_obj = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": rid})
                    raw = str(body_obj.get("body") or "")
                    if raw and len(raw) <= 2_000_000 and not body_obj.get("base64Encoded"):
                        parsed = json.loads(raw)
                        keys = collect_keys(parsed)
                        evidence = {
                            "topLevelType": type(parsed).__name__,
                            "interestingKeyPaths": interesting_key_paths(keys),
                            "keyPathCount": len(keys),
                        }
                        bodies_scanned += 1
                except Exception:
                    pass
            endpoint_rows.append({**row, "jsonEvidence": evidence})

        # Browser errors are useful for detecting bot/WAF failures; redact to a
        # bounded diagnostic string only.
        try:
            for entry in driver.get_log("browser"):
                if str(entry.get("level")) in {"SEVERE", "WARNING"}:
                    browser_errors.append(re.sub(r"https?://\S+", "<url>", str(entry.get("message") or ""))[:500])
        except Exception:
            pass

        # Deduplicate equivalent endpoint shapes (host/path/method/query-key set).
        unique: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in endpoint_rows:
            url = row.get("url") or {}
            key = (url.get("host"), url.get("path"), row.get("method"), tuple(url.get("queryKeys") or []))
            current = unique.get(key)
            if current is None or (not current.get("jsonEvidence") and row.get("jsonEvidence")):
                unique[key] = row
        rows = sorted(unique.values(), key=lambda r: (str((r.get("url") or {}).get("host")), str((r.get("url") or {}).get("path"))))

        price_evidence = [
            row for row in rows
            if any(any(token in key.lower() for token in ("price", "tariff", "cost", "rate", "fee"))
                   for key in (row.get("jsonEvidence") or {}).get("interestingKeyPaths", []))
        ]
        station_evidence = [
            row for row in rows
            if any(any(token in key.lower() for token in ("evse", "station", "connector", "charge", "poi"))
                   for key in (row.get("jsonEvidence") or {}).get("interestingKeyPaths", []))
        ]

        report = {
            "generatedAt": now_iso(),
            "mapUrl": MAP_URL,
            "scope": "public_web_map_backend_discovery_only",
            "security": {
                "accountCredentialsUsed": False,
                "requestHeadersPersisted": False,
                "cookiesPersisted": False,
                "queryValuesPersisted": False,
                "rawResponseBodiesPersisted": False,
            },
            "counts": {
                "performanceEvents": len(logs),
                "capturedResponses": len(responses),
                "uniqueLikelyApiEndpoints": len(rows),
                "jsonBodiesScanned": bodies_scanned,
                "endpointsWithStationEvidence": len(station_evidence),
                "endpointsWithPriceEvidence": len(price_evidence),
            },
            "apiHosts": hosts.most_common(),
            "endpoints": rows,
            "priceEvidenceEndpoints": price_evidence,
            "stationEvidenceEndpoints": station_evidence,
            "browserDiagnostics": browser_errors[:30],
            "nextStepReady": bool(station_evidence or price_evidence),
        }
    finally:
        driver.quit()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(
        "# Enel Italy public map backend probe\n\n"
        f"- Likely public API endpoint shapes: **{report['counts']['uniqueLikelyApiEndpoints']}**\n"
        f"- Endpoints with station/EVSE evidence: **{report['counts']['endpointsWithStationEvidence']}**\n"
        f"- Endpoints with price/tariff evidence: **{report['counts']['endpointsWithPriceEvidence']}**\n"
        f"- JSON bodies safely inspected: **{report['counts']['jsonBodiesScanned']}**\n"
        f"- Ready for targeted station-detail probe: **{'yes' if report['nextStepReady'] else 'no'}**\n",
        encoding="utf-8",
    )
    print(json.dumps({"counts": report["counts"], "apiHosts": report["apiHosts"], "nextStepReady": report["nextStepReady"]}, ensure_ascii=False, indent=2))
    for row in report["priceEvidenceEndpoints"][:10]:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
