#!/usr/bin/env python3
"""Discover public NextCharge map data endpoints without account credentials.

Research-only probe for the Italy GES CPO investigation. It loads the public
NextCharge browser map centered on Bologna and observes network metadata.

Safety rules:
- no login, registration, charging, payment, wallet, userAuth or session calls;
- request/response headers, cookies and browser storage are never persisted;
- cross-domain requests retain only hostname + path (query strings discarded);
- request bodies are retained only for trusted NextCharge/GES first-party hosts
  and sensitive fields are redacted;
- response bodies are sampled only from trusted first-party hosts.
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
TRUSTED_HOST_SUFFIXES = ("nextcharge.app", "goelectricstations.com")
BLOCKED_PATH_WORDS = ("userauth", "login", "signup", "register", "payment", "wallet", "transaction", "recharge", "startcharge", "stopcharge")
SENSITIVE_KEY_RE = re.compile(r"(auth|token|cookie|session|user.?id|email|phone|device|public.?key|password|secret|card|payment)", re.I)
MAX_BODY_CHARS = 500_000


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parsed_url(url: str):
    try:
        return urlparse(url)
    except Exception:
        return urlparse("")


def trusted_url(url: str) -> bool:
    host = (parsed_url(url).hostname or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in TRUSTED_HOST_SUFFIXES)


def blocked_url(url: str) -> bool:
    low = (parsed_url(url).path or "").lower()
    return any(word in low for word in BLOCKED_PATH_WORDS)


def safe_url_metadata(url: str) -> dict[str, Any]:
    p = parsed_url(url)
    host = (p.hostname or "unknown").lower()
    trusted = trusted_url(url)
    return {
        "host": host,
        "path": p.path or "/",
        "trustedFirstParty": trusted,
        "url": url if trusted else None,
        "queryPersisted": trusted,
    }


def shape(value: Any, depth: int = 0) -> Any:
    if depth >= 5:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): shape(v, depth + 1) for k, v in list(value.items())[:100]}
    if isinstance(value, list):
        return {"type": "list", "length": len(value), "sampleShape": shape(value[0], depth + 1) if value else None}
    return type(value).__name__


def sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "<depth-limit>"
    if isinstance(value, dict):
        out = {}
        for k, v in list(value.items())[:150]:
            out[str(k)] = "<redacted>" if SENSITIVE_KEY_RE.search(str(k)) else sanitize(v, depth + 1)
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
        fields = []
        for part in text.split("&"):
            key = part.split("=", 1)[0]
            if key:
                fields.append(key[:100])
        return {"formFieldNames": fields[:100], "rawNotPersisted": True}


def compact_json_sample(value: Any) -> Any:
    if isinstance(value, list):
        return [sanitize(x) for x in value[:3]]
    if isinstance(value, dict):
        out = {}
        for k, v in list(value.items())[:100]:
            if isinstance(v, list):
                out[str(k)] = [sanitize(x) for x in v[:3]]
            else:
                out[str(k)] = sanitize(v)
        return out
    return sanitize(value)


def main() -> None:
    opts = Options()
    for arg in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,1600", "--lang=it-IT", "--disable-geolocation"):
        opts.add_argument(arg)
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(options=opts)
    requests: dict[str, dict[str, Any]] = {}
    responses: dict[str, dict[str, Any]] = {}
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.get(MAP_URL)
        for _ in range(5):
            time.sleep(5)
            for entry in driver.get_log("performance"):
                try:
                    msg = json.loads(entry["message"])["message"]
                    method = msg.get("method")
                    params = msg.get("params") or {}
                    rid = str(params.get("requestId"))
                    if method == "Network.requestWillBeSent":
                        req = params.get("request") or {}
                        url = str(req.get("url") or "")
                        meta = safe_url_metadata(url)
                        trusted = bool(meta["trustedFirstParty"])
                        requests[rid] = {
                            **meta,
                            "method": req.get("method"),
                            "resourceType": params.get("type"),
                            "blockedCategoryPath": blocked_url(url),
                            "postData": parse_post_data(req.get("postData")) if trusted else None,
                        }
                    elif method == "Network.responseReceived":
                        res = params.get("response") or {}
                        url = str(res.get("url") or "")
                        responses[rid] = {
                            **safe_url_metadata(url),
                            "status": res.get("status"),
                            "mimeType": res.get("mimeType"),
                            "resourceType": params.get("type"),
                        }
                except Exception:
                    continue

        rows = []
        for rid, res in responses.items():
            req = requests.get(rid, {})
            row = {
                **res,
                "method": req.get("method"),
                "postData": req.get("postData") if res.get("trustedFirstParty") else None,
                "blockedCategoryPath": req.get("blockedCategoryPath", blocked_url(str(res.get("url") or res.get("path") or ""))),
            }
            mime = str(res.get("mimeType") or "").lower()
            if row.get("trustedFirstParty") and not row["blockedCategoryPath"] and ("json" in mime or "text" in mime or "javascript" in mime):
                try:
                    body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": rid})
                    text = str(body.get("body") or "")
                    if len(text) <= MAX_BODY_CHARS:
                        try:
                            parsed = json.loads(text)
                            row["jsonShape"] = shape(parsed)
                            row["jsonSample"] = compact_json_sample(parsed)
                        except Exception:
                            fragments = sorted(set(re.findall(r"[A-Za-z0-9_./?-]{4,160}(?:api|station|connector|chargepoint|marker)[A-Za-z0-9_./?=&-]{0,160}", text, flags=re.I)))
                            if fragments:
                                row["apiLikeTextFragments"] = fragments[:100]
                    else:
                        row["bodyNotPersisted"] = {"reason": "too_large", "length": len(text)}
                except Exception as exc:
                    row["bodyReadError"] = type(exc).__name__
            rows.append(row)

        rows.sort(key=lambda x: (str(x.get("host")), str(x.get("path")), str(x.get("method"))))
        dynamic_rows = [r for r in rows if r.get("resourceType") in {"Fetch", "XHR", "WebSocket"} or "json" in str(r.get("mimeType") or "").lower()]
        external_dynamic = [
            {k: r.get(k) for k in ("host", "path", "method", "status", "mimeType", "resourceType", "blockedCategoryPath")}
            for r in dynamic_rows if not r.get("trustedFirstParty")
        ]
        trusted_dynamic = [r for r in dynamic_rows if r.get("trustedFirstParty")]
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
                "externalQueryStringsPersisted": False,
                "externalRequestBodiesPersisted": False,
                "sensitiveFirstPartyRequestFieldsRedacted": True,
            },
            "counts": {
                "allRequestsObserved": len(requests),
                "allResponsesObserved": len(rows),
                "dynamicResponses": len(dynamic_rows),
                "trustedDynamicResponses": len(trusted_dynamic),
                "externalDynamicResponses": len(external_dynamic),
                "blockedCategoryPathsObserved": sum(1 for r in rows if r.get("blockedCategoryPath")),
            },
            "allResponseHosts": dict(sorted(Counter(str(r.get("host") or "unknown") for r in rows).items())),
            "dynamicResponseHosts": dict(sorted(Counter(str(r.get("host") or "unknown") for r in dynamic_rows).items())),
            "externalDynamicResponseMetadata": external_dynamic,
            "trustedDynamicResponses": trusted_dynamic,
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:100000])
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
