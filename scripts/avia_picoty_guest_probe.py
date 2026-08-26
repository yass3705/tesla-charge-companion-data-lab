#!/usr/bin/env python3
"""Probe only anonymous/read-only AVIA Picoty/Deftpower public guest surfaces.

No API subscription key, OAuth token, account credential, cookie or customer identifier is
sent. Only GET/OPTIONS requests are issued. Response bodies are truncated and sanitized.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("data/reports/avia_picoty_guest_probe.json")
BASES = [
    "https://pdefweushaapiam01.azure-api.net",
    "https://adefweuappbckfa01.azurewebsites.net",
    "https://api.deftpower.com",
]
PREFIXES = ["", "/v1", "/api", "/api/v1"]
PATHS = [
    "/",
    "/tenants",
    "/registration-groups",
    "/map-locations",
    "/nearby-locations",
    "/locations/nonexistent",
    "/locations/nonexistent/tariffs",
    "/tenants/nonexistent/map-locations",
    "/tenants/nonexistent/nearby-locations",
    "/tenants/nonexistent/locations/nonexistent",
    "/tenants/nonexistent/locations/nonexistent/tariffs",
    "/tenants/nonexistent/app-distribution",
    "/tenants/nonexistent/registration-groups",
]

SECRETISH = re.compile(r"(?i)(authorization|subscription[-_ ]?key|api[-_ ]?key|access[-_ ]?token|refresh[-_ ]?token|client[-_ ]?secret)\s*[:=]\s*[^\s,;]+")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}(?:\.[A-Za-z0-9_-]{10,})?\b")


def sanitize(text: str) -> str:
    text = SECRETISH.sub(lambda m: m.group(1) + "=<redacted>", text)
    text = JWT_RE.sub("<redacted-jwt>", text)
    return text[:2500]


def request(method: str, url: str, params: dict[str, str] | None = None) -> dict:
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        method=method,
        headers={
            "User-Agent": "TeslaChargeCompanion-data-lab/1.0",
            "Accept": "application/json, text/plain, */*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(8192).decode("utf-8", "replace")
            return {
                "method": method,
                "url": url,
                "status": int(r.status),
                "contentType": r.headers.get("content-type"),
                "wwwAuthenticate": r.headers.get("www-authenticate"),
                "allow": r.headers.get("allow"),
                "body": sanitize(body),
            }
    except urllib.error.HTTPError as e:
        body = e.read(8192).decode("utf-8", "replace")
        return {
            "method": method,
            "url": url,
            "status": int(e.code),
            "contentType": e.headers.get("content-type") if e.headers else None,
            "wwwAuthenticate": e.headers.get("www-authenticate") if e.headers else None,
            "allow": e.headers.get("allow") if e.headers else None,
            "body": sanitize(body),
        }
    except Exception as e:
        return {"method": method, "url": url, "status": None, "error": type(e).__name__, "message": sanitize(str(e))}


def main() -> None:
    results = []
    seen = set()
    for base in BASES:
        for prefix in PREFIXES:
            for path in PATHS:
                url = base.rstrip("/") + prefix + path
                if url in seen:
                    continue
                seen.add(url)
                results.append(request("GET", url))
            map_url = base.rstrip("/") + prefix + "/tenants/nonexistent/map-locations"
            results.append(request("GET", map_url, {
                "latLongBottomLeft": "41,-6",
                "latLongTopRight": "52,10",
            }))
            near_url = base.rstrip("/") + prefix + "/tenants/nonexistent/nearby-locations"
            results.append(request("GET", near_url, {"latitude": "48.8", "longitude": "2.3"}))
            results.append(request("OPTIONS", base.rstrip("/") + prefix + "/tenants/nonexistent/map-locations"))

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "credentialsSent": False,
        "writeMethodsUsed": False,
        "bases": BASES,
        "prefixes": PREFIXES,
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {}
    for x in results:
        key = str(x.get("status"))
        summary[key] = summary.get(key, 0) + 1
    print(json.dumps({"count": len(results), "statusCounts": summary}, ensure_ascii=False, indent=2))
    for x in results:
        if x.get("status") not in (404, None):
            print(json.dumps({"method": x["method"], "url": x["url"], "status": x.get("status"), "body": x.get("body", "")[:500]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
