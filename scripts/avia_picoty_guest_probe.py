#!/usr/bin/env python3
"""Probe only anonymous/read-only AVIA Picoty/Deftpower public guest surfaces.

No API subscription key, OAuth token, account credential, cookie or customer identifier is
sent. Only GET/OPTIONS requests are issued. Response bodies are truncated and sanitized.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("data/reports/avia_picoty_guest_probe.json")
BASES = [
    "https://pdefweushaapiam01.azure-api.net",
    "https://api.deftpower.com",
]
PATHS = [
    "/",
    "/map-locations",
    "/nearby-locations",
    "/locations/nonexistent/tariffs",
    "/tenants/nonexistent/map-locations",
    "/tenants/nonexistent/locations/nonexistent/tariffs",
    "/openapi.json",
    "/swagger/v1/swagger.json",
]

SECRETISH = re.compile(r"(?i)(authorization|subscription[-_ ]?key|api[-_ ]?key|access[-_ ]?token|refresh[-_ ]?token|client[-_ ]?secret)\s*[:=]\s*[^\s,;]+")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}(?:\.[A-Za-z0-9_-]{10,})?\b")


def sanitize(text: str) -> str:
    text = SECRETISH.sub(lambda m: m.group(1) + "=<redacted>", text)
    text = JWT_RE.sub("<redacted-jwt>", text)
    return text[:1500]


def request(method: str, url: str) -> dict:
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
            body = r.read(4096).decode("utf-8", "replace")
            return {
                "method": method,
                "url": url,
                "status": int(r.status),
                "contentType": r.headers.get("content-type"),
                "wwwAuthenticate": r.headers.get("www-authenticate"),
                "body": sanitize(body),
            }
    except urllib.error.HTTPError as e:
        body = e.read(4096).decode("utf-8", "replace")
        return {
            "method": method,
            "url": url,
            "status": int(e.code),
            "contentType": e.headers.get("content-type") if e.headers else None,
            "wwwAuthenticate": e.headers.get("www-authenticate") if e.headers else None,
            "body": sanitize(body),
        }
    except Exception as e:
        return {"method": method, "url": url, "status": None, "error": type(e).__name__, "message": sanitize(str(e))}


def main() -> None:
    results = []
    for base in BASES:
        for path in PATHS:
            results.append(request("GET", base.rstrip("/") + path))
        results.append(request("OPTIONS", base.rstrip("/") + "/map-locations"))
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "credentialsSent": False,
        "writeMethodsUsed": False,
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps([{"method": x["method"], "url": x["url"], "status": x.get("status"), "body": x.get("body", "")[:240]} for x in results], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
