#!/usr/bin/env python3
"""Probe Freshmile's public GET API for EVSE tariff semantics.

The first bounded probe established that /evses is a live public route and its
422 validation error explicitly requires filter.location_id when filter.ref is
absent. This second-stage probe tests only the nested/dotted filter.ref forms
for known public Freshmile EVSE identifiers. No authentication, credentials or
state-changing requests are used, and no numeric token is accepted as a TCC
tariff without semantic validation.
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
UA = "Tesla-Charge-Companion-Freshmile-Probe/1.1 (+public-GET-only)"
DEFAULT_EVSES = [
    "FRFR1EBVFB2",  # hotel Dolce Vita, Ajaccio
    "FRFR1EPNFH1",  # Hotel Amerique, Palavas-les-Flots
    "FRFR1EUMAR1",  # Champdor-Corcelles
]
PRICE_WORDS = re.compile(r"\b(price|pricing|tariff|tarif|cost|fee|rate|kwh|minute|min|amount|currency)\b", re.I)


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
        "bodyPreview": re.sub(r"\s+", " ", text[:1600]).strip(),
    }


def url(path: str, params: dict[str, str]) -> str:
    return BASE + path + "?" + urllib.parse.urlencode(params)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evse", action="append", dest="evses")
    args = parser.parse_args()
    evses = args.evses or DEFAULT_EVSES

    requests: list[dict[str, Any]] = []
    for evse in evses:
        # Laravel-style nested query plus dotted form, both suggested by the
        # live validation response returned by the first probe.
        candidates = [
            url("/evses", {"filter[ref]": evse}),
            url("/evses", {"filter.ref": evse}),
            url("/locations", {"filter[ref]": evse}),
            url("/locations", {"filter.ref": evse}),
        ]
        requests.extend(get(candidate) for candidate in candidates)

    successful = [item for item in requests if item.get("status") in {200, 206}]
    semantic = [item for item in successful if item.get("priceSemanticTerms")]
    payload = {
        "schemaVersion": "1.1.0",
        "generatedAt": now_iso(),
        "baseUrl": BASE,
        "method": "unauthenticated public GET only",
        "knownPublicEvseIds": evses,
        "requestCount": len(requests),
        "statusCounts": {},
        "successfulResponseCount": len(successful),
        "successfulResponsesWithPriceSemantics": len(semantic),
        "validatedExactPriceFound": False,
        "policy": "HTTP 200 and price-like words are discovery evidence only. Exact price needs EVSE identity plus explicit tariff components before TCC ranking.",
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
        "successfulResponseCount": payload["successfulResponseCount"],
        "successfulResponsesWithPriceSemantics": payload["successfulResponsesWithPriceSemantics"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
