#!/usr/bin/env python3
"""Discover public NextCharge map data endpoints without account credentials.

Research-only probe for the Italy GES CPO investigation. It loads the public
NextCharge browser map centered on Bologna and records only first-party network
metadata plus safely-sanitized public API response shapes/samples.

Safety rules:
- no login, registration, charging, payment, wallet, userAuth or session calls;
- request/response headers, cookies and browser storage are never persisted;
- potentially identifying/auth fields in request bodies are redacted;
- only JSON/text bodies from NextCharge/Go Electric Stations first-party hosts
  are sampled, with strict size limits.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

MAP_URL = "https://nextcharge.app/map?location=44.4949%2C11.3426&nextcharge=only&lang=it"
OUT = Path("data/reports/ges_nextcharge_public_network_probe.json")
ALLOWED_HOST_SUFFIXES = ("nextcharge.app", "goelectricstations.com")
BLOCKED_PATH_WORDS = ("userauth", "login", "signup", "register", "payment", "wallet", "transaction", "recharge", "startcharge", "stopcharge")
SENSITIVE_KEY_RE = re.compile(r"(auth|token|cookie|session|user.?id|email|phone|device|public.?key|password|secret|card|payment)", re.I)
MAX_BODY_CHARS = 500_000


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def allowed_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
        return any(host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_HOST_SUFFIXES)
    except Exception:
        return False


def blocked_url(url: str) -> bool:
    low = url.lower()
    return any(word in low for word in BLOCKED_PATH_WORDS)


def shape(value: Any, depth: int = 0) -> Any:
    if depth >= 5:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): shape(v, depth + 1) for k, v in list(value.items())[:100]}
    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "sampleShape": shape(value[0], depth + 1) if value else None,
        }
    return type(value).__name__


def sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "<depth-limit>"
    if isinstance(value, dict):
        out = {}
        for k, v in list(value.items())[:150]:
            if SENSITIVE_KEY_RE.search(str(k)):
                out[str(k)] = "<redacted>"
            else:
                out[str(k)] = sanitize(v, depth + 1)
        return out
    if isinstance(value, list):
        return [sanitize(v, depth + 1) for v in value[:40]]
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


def parse_post_data(text: str | None) -> Any:
    if not text:
        return None
    if len(text) > 20_000:
        return {"redacted": "request_body_too_large", "length": len(text)}
    try:
        return sanitize(json.loads(text))
    except Exception:
        # Form bodies can contain IDs/auth material, so persist only field names.
        fields = []
        for part in text.split("&"):
            key = part.split("=", 1)[0]
            if key:
                fields.append(key[:100])
        return {"formFieldNames": fields[:100], "rawNotPersisted": True}


def compact_json_sample(value: Any) -> Any:
    """Keep enough public station data to identify endpoint semantics, not a dump."""
    if isinstance(value, list):
        return [sanitize(x) for x in value[:3]]
    if isinstance(value, dict):
        # Preserve top-level counters/metadata and at most 3 entries in list fields.
        out = {}
        for k, v in list(value.items())[:100]:
            if isinstance(v, list):
                out[str(k)] = [sanitize(x) for x in v[:3]]
            elif isinstance(v, dict):
                out[str(k)] = sanitize(v)
            else:
                out[str(k)] = sanitize(v)
        return out
    return sanitize(value)


def main() -> None:
    opts = Options()
    for arg in (
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--window-size=1440,1600",
        "--lang=it-IT",
        "--disable-geolocation",
    ):
        opts.add_argument(arg)
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(options=opts)
    request_meta: dict[str, dict[str, Any]] = {}
    response_meta: dict[str, dict[str, Any]] = {}
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.get(MAP_URL)
        # Let map JS load public station tiles/data. No DOM interaction is needed.
        for _ in range(4):
            time.sleep(5)
            for entry in driver.get_log("performance"):
                try:
                    msg = json.loads(entry["message"])["message"]
                    method = msg.get("method")
                    params = msg.get("params") or {}
                    if method == "Network.requestWillBeSent":
                        req = params.get("request") or {}
                        url = str(req.get("url") or "")
                        if allowed_url(url):
                            request_meta[str(params.get("requestId"))] = {
                                "url": url,
                                "method": req.get("method"),
                                "resourceType": params.get("type"),
                                "postData": parse_post_data(req.get("postData")),
                                "blockedCategoryPath": blocked_url(url),
                            }
                    elif method == "Network.responseReceived":
                        res = params.get("response") or {}
                        url = str(res.get("url") or "")
                        rid = str(params.get("requestId"))
                        if allowed_url(url):
                            response_meta[rid] = {
                                "url": url,
                                "status": res.get("status"),
                                "mimeType": res.get("mimeType"),
                                "resourceType": params.get("type"),
                            }
                except Exception:
                    continue

        rows = []
        for rid, res in response_meta.items():
            req = request_meta.get(rid, {})
            row = {**res, "method": req.get("method"), "postData": req.get("postData"), "blockedCategoryPath": req.get("blockedCategoryPath", False)}
            mime = str(res.get("mimeType") or "").lower()
            if not row["blockedCategoryPath"] and ("json" in mime or "text" in mime or "javascript" in mime):
                try:
                    body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": rid})
                    text = str(body.get("body") or "")
                    if len(text) <= MAX_BODY_CHARS:
                        try:
                            parsed = json.loads(text)
                            row["jsonShape"] = shape(parsed)
                            row["jsonSample"] = compact_json_sample(parsed)
                        except Exception:
                            # JS/text is useful only for endpoint discovery. Keep tiny snippets
                            # that mention API-like paths; never persist the full bundle.
                            api_fragments = sorted(set(re.findall(r"[A-Za-z0-9_./?-]{4,160}(?:api|station|connector|chargepoint|marker)[A-Za-z0-9_./?=&-]{0,160}", text, flags=re.I)))
                            if api_fragments:
                                row["apiLikeTextFragments"] = api_fragments[:100]
                    else:
                        row["bodyNotPersisted"] = {"reason": "too_large", "length": len(text)}
                except Exception as exc:
                    row["bodyReadError"] = type(exc).__name__
            rows.append(row)

        rows.sort(key=lambda x: (str(x.get("url")), str(x.get("method"))))
        endpoint_rows = [r for r in rows if r.get("resourceType") in {"Fetch", "XHR"} or "json" in str(r.get("mimeType") or "").lower()]
        payload = {
            "generatedAt": now_iso(),
            "mapUrl": MAP_URL,
            "security": {
                "accountCredentialsUsed": False,
                "loginOrRegistrationPerformed": False,
                "chargingPaymentOrWalletEndpointsCalledIntentionally": False,
                "requestHeadersPersisted": False,
                "responseHeadersPersisted": False,
                "cookiesPersisted": False,
                "browserStoragePersisted": False,
                "sensitiveRequestFieldsRedacted": True,
            },
            "counts": {
                "firstPartyRequests": len(request_meta),
                "firstPartyResponses": len(rows),
                "xhrFetchOrJsonResponses": len(endpoint_rows),
                "blockedCategoryPathsObserved": sum(1 for r in rows if r.get("blockedCategoryPath")),
            },
            "hosts": dict(sorted(Counter((urlparse(str(r.get("url") or "")).hostname or "unknown") for r in rows).items())),
            "endpointResponses": endpoint_rows,
            "allFirstPartyResponseMetadata": [
                {k: r.get(k) for k in ("url", "method", "status", "mimeType", "resourceType", "blockedCategoryPath")}
                for r in rows
            ],
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:100000])
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
