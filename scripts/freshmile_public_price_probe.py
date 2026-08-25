#!/usr/bin/env python3
"""Probe a very small set of Freshmile public GET routes for EVSE tariff data.

The web map now redirects drivers to the Freshmile mobile app, while an older
public Nuxt bundle exposed the base URL https://prod-driver-api.freshmile.com/charge/api/v2.
This probe performs only unauthenticated GET requests against a bounded route
matrix for known public Freshmile EVSE identifiers. It never sends credentials,
never mutates state and never treats an HTTP 200 or a numeric token as a
validated tariff on its own.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = "https://prod-driver-api.freshmile.com/charge/api/v2"
DEFAULT_OUTPUT = Path("reports/freshmile/public_price_probe_latest.json")
UA = "Tesla-Charge-Companion-Freshmile-Probe/1.0 (+public-GET-only)"
DEFAULT_EVSES = [
    "FRFR1EBVFB2",  # hotel Dolce Vita, Ajaccio
    "FRFR1EPNFH1",  # Hotel Amerique, Palavas-les-Flots
    "FRFR1EUMAR1",  # Champdor-Corcelles
]
ROUTE_TEMPLATES = [
    "/evse/{id}",
    "/evses/{id}",
    "/charge-point/{id}",
    "/charge-points/{id}",
    "/charging-point/{id}",
    "/charging-points/{id}",
    "/station/{id}",
    "/stations/{id}",
    "/location/{id}",
    "/locations/{id}",
]
QUERY_TEMPLATES = [
    ("/evses", "id"),
    ("/stations", "evse"),
    ("/locations", "evse"),
    ("/search", "query"),
]
PRICE_WORDS = re.compile(r"\b(price|pricing|tariff|tarif|cost|fee|rate|kwh|minute|min)\b", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read(256_000)
            status = response.status
            content_type = response.headers.get("content-type", "")
            resolved = response.geturl()
    except urllib.error.HTTPError as exc:
        raw = exc.read(64_000)
        status = exc.code
        content_type = exc.headers.get("content-type", "") if exc.headers else ""
        resolved = exc.geturl()
    except Exception as exc:
        return {"url": url, "error": f"{type(exc).__name__}: {exc}"}

    text = raw.decode("utf-8", errors="replace")
    return {
        "url": url,
        "resolvedUrl": resolved,
        "status": status,
        "contentType": content_type,
        "bytesRead": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bodyLooksJson": text.lstrip().startswith(("{", "[")),
        "priceSemanticTerms": sorted({m.group(0).lower() for m in PRICE_WORDS.finditer(text)}),
        "bodyPreview": re.sub(r"\s+", " ", text[:800]).strip(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evse", action="append", dest="evses")
    args = parser.parse_args()
    evses = args.evses or DEFAULT_EVSES

    requests: list[dict[str, Any]] = []
    for evse in evses:
        safe = urllib.parse.quote(evse, safe="")
        for template in ROUTE_TEMPLATES:
            requests.append(get(BASE + template.format(id=safe)))
        for path, key in QUERY_TEMPLATES:
            query = urllib.parse.urlencode({key: evse})
            requests.append(get(f"{BASE}{path}?{query}"))

    interesting = [
        item for item in requests
        if item.get("status") in {200, 206}
        or item.get("bodyLooksJson")
        or item.get("priceSemanticTerms")
    ]
    payload = {
        "schemaVersion": "1.0.0",
        "generatedAt": now_iso(),
        "baseUrl": BASE,
        "method": "unauthenticated public GET only",
        "knownPublicEvseIds": evses,
        "requestCount": len(requests),
        "statusCounts": {},
        "interestingResponseCount": len(interesting),
        "validatedExactPriceFound": False,
        "policy": "A route/status/numeric value is evidence only. Exact price needs semantic association with a specific EVSE and tariff components before TCC use.",
        "requests": requests,
    }
    for item in requests:
        key = str(item.get("status") or "error")
        payload["statusCounts"][key] = payload["statusCounts"].get(key, 0) + 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "requestCount": payload["requestCount"],
        "statusCounts": payload["statusCounts"],
        "interestingResponseCount": len(interesting),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
