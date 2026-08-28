#!/usr/bin/env python3
"""Discover public A2A Emoving map endpoints without account credentials.

Loads the public map in a headless browser, records same-site/XHR/fetch traffic and
produces a sanitized report of endpoint URLs, methods, status codes and response
shapes. Cookies/auth material and full bodies are never persisted.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlencode

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

URL = "https://e-movinghub.a2a.it/acEicp/publicMapCMS.action"
OUT = Path("data/reports/a2a_italy_public_map_discovery.json")
SENSITIVE = {"token", "access_token", "authorization", "cookie", "session", "sid", "jsessionid", "password", "code"}
KEYWORDS = ("station", "column", "charge", "connector", "plug", "price", "tariff", "map", "poi", "presa", "colonn")


def sanitize_url(url: str) -> str:
    try:
        u = urlparse(url)
        pairs = []
        for k, v in parse_qsl(u.query, keep_blank_values=True):
            if k.lower() in SENSITIVE:
                pairs.append((k, "<redacted>"))
            else:
                pairs.append((k, v[:200]))
        return u._replace(query=urlencode(pairs, doseq=True)).geturl()
    except Exception:
        return url[:1000]


def shape(value, depth=0):
    if depth >= 4:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): shape(v, depth + 1) for k, v in list(value.items())[:80]}
    if isinstance(value, list):
        return {"type": "list", "length": len(value), "sample": shape(value[0], depth + 1) if value else None}
    return type(value).__name__


def interesting(url: str, resource_type: str) -> bool:
    lower = url.lower()
    host = urlparse(url).hostname or ""
    return (
        host.endswith("a2a.it")
        or host.endswith("e-moving.it")
        or resource_type in {"XHR", "Fetch"}
        or any(k in lower for k in KEYWORDS)
    )


def main():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1440,1600")
    opts.add_argument("--lang=it-IT")
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = webdriver.Chrome(options=opts)
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.get(URL)
        time.sleep(8)
        # Best-effort cookie dismissal.
        for needle in ("Accetta", "Accept", "OK"):
            try:
                for el in driver.find_elements(By.XPATH, f"//*[contains(normalize-space(text()), '{needle}')]"):
                    if el.is_displayed():
                        driver.execute_script("arguments[0].click();", el)
                        time.sleep(0.4)
                        break
            except Exception:
                pass
        # Trigger list/map lazy loads and harmless filters.
        for text in ("Mostra lista", "Rete A2A", "Disponibile"):
            try:
                for el in driver.find_elements(By.XPATH, f"//*[contains(normalize-space(text()), '{text}')]"):
                    if el.is_displayed():
                        driver.execute_script("arguments[0].click();", el)
                        time.sleep(1.0)
                        break
            except Exception:
                pass
        time.sleep(5)

        requests = {}
        responses = {}
        for entry in driver.get_log("performance"):
            try:
                msg = json.loads(entry["message"])["message"]
            except Exception:
                continue
            method = msg.get("method")
            params = msg.get("params", {})
            rid = str(params.get("requestId") or "")
            if method == "Network.requestWillBeSent":
                req = params.get("request") or {}
                requests[rid] = {
                    "url": str(req.get("url") or ""),
                    "method": str(req.get("method") or ""),
                    "resourceType": str(params.get("type") or ""),
                    "hasPostData": bool(req.get("postData")),
                    "postDataLength": len(str(req.get("postData") or "")),
                }
            elif method == "Network.responseReceived":
                res = params.get("response") or {}
                responses[rid] = {
                    "status": res.get("status"),
                    "mimeType": res.get("mimeType"),
                    "url": str(res.get("url") or ""),
                    "resourceType": str(params.get("type") or ""),
                }

        records = []
        for rid, req in requests.items():
            res = responses.get(rid, {})
            url = req.get("url") or res.get("url") or ""
            rtype = req.get("resourceType") or res.get("resourceType") or ""
            if not url or not interesting(url, rtype):
                continue
            rec = {
                "url": sanitize_url(url),
                "method": req.get("method"),
                "resourceType": rtype,
                "status": res.get("status"),
                "mimeType": res.get("mimeType"),
                "hasPostData": req.get("hasPostData"),
                "postDataLength": req.get("postDataLength"),
            }
            # Parse only small JSON response shapes, never persist full body.
            if str(res.get("mimeType") or "").lower().find("json") >= 0:
                try:
                    body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": rid}).get("body", "")
                    if len(body) <= 2_000_000:
                        parsed = json.loads(body)
                        rec["jsonShape"] = shape(parsed)
                        if isinstance(parsed, dict):
                            rec["topLevelKeys"] = list(parsed.keys())[:100]
                        elif isinstance(parsed, list):
                            rec["listLength"] = len(parsed)
                except Exception as exc:
                    rec["jsonShapeError"] = type(exc).__name__
            records.append(rec)

        # Deduplicate by method + sanitized URL + status while preserving shape-rich item.
        dedup = {}
        for rec in records:
            key = (rec.get("method"), rec.get("url"), rec.get("status"))
            old = dedup.get(key)
            if old is None or ("jsonShape" in rec and "jsonShape" not in old):
                dedup[key] = rec
        records = sorted(dedup.values(), key=lambda r: (r.get("resourceType") != "XHR", r.get("url") or ""))
        payload = {
            "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "url": URL,
            "title": driver.title,
            "security": {
                "accountCredentialsUsed": False,
                "authorizationMaterialPersisted": False,
                "cookiesPersisted": False,
                "fullResponseBodiesPersisted": False,
            },
            "counts": {
                "interestingRequests": len(records),
                "resourceTypes": dict(Counter(str(r.get("resourceType")) for r in records)),
                "statusCodes": dict(Counter(str(r.get("status")) for r in records)),
                "jsonResponses": sum(1 for r in records if "jsonShape" in r),
            },
            "requests": records,
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:50000])
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
