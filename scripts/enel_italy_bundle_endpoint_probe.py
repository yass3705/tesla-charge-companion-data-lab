#!/usr/bin/env python3
"""Discover station-detail/tariff endpoint strings in Enel's public map frontend.

Only public HTML/JavaScript assets are downloaded. The report stores endpoint-like
strings and nearby tariff-related identifiers, never credentials or source bundles.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

MAP_URL = "https://d2jtbpdp94l0ts.cloudfront.net/?show_only_enel=true"
OUT = Path("data/reports/enel_italy_bundle_endpoint_probe.json")
OUT_MD = Path("data/reports/enel_italy_bundle_endpoint_probe.md")
UA = "Mozilla/5.0 TeslaChargeCompanion/1.0"
API_RE = re.compile(r"[\"'`]([^\"'`]{0,160}(?:/api/(?:emobility|authentication)/[^\"'`\\\s]{1,220}))[\"'`]")
PATH_RE = re.compile(r"(?:/api/)?emobility/v\d+/charging/[A-Za-z0-9_{}:/?&=.+$\-]+")
TOKENS = ("tariff", "price", "pricing", "cost", "fee", "rate", "station", "evse", "connector", "serialnumber", "maxpower")


def get(url: str) -> str:
    r = requests.get(url, timeout=45, headers={"User-Agent": UA, "Accept": "text/html,application/javascript,*/*;q=0.5"})
    r.raise_for_status()
    return r.text


def safe_asset(url: str, text: str) -> dict:
    return {
        "host": urlsplit(url).hostname,
        "path": urlsplit(url).path,
        "bytes": len(text.encode("utf-8", "replace")),
        "sha256": hashlib.sha256(text.encode("utf-8", "replace")).hexdigest(),
    }


def main() -> None:
    html = get(MAP_URL)
    srcs = re.findall(r"<script[^>]+src=[\"']([^\"']+)[\"']", html, flags=re.I)
    assets = [urljoin(MAP_URL, src) for src in srcs]
    # Prefer app/runtime chunks, cap scope to avoid downloading unrelated assets.
    assets = list(dict.fromkeys(assets))[:30]

    endpoint_strings: set[str] = set()
    token_contexts: set[str] = set()
    asset_meta = []
    failures = []
    for url in assets:
        try:
            text = get(url)
        except Exception as exc:
            failures.append({"path": urlsplit(url).path, "errorType": type(exc).__name__})
            continue
        asset_meta.append(safe_asset(url, text))
        for match in API_RE.finditer(text):
            value = match.group(1)
            value = value[value.find("/api/"):]
            if len(value) <= 400:
                endpoint_strings.add(value)
        for match in PATH_RE.finditer(text):
            value = match.group(0)
            if not value.startswith("/"):
                value = "/api/" + value
            endpoint_strings.add(value[:400])
        low = text.lower()
        for token in TOKENS:
            start = 0
            hits = 0
            while hits < 40:
                pos = low.find(token, start)
                if pos < 0:
                    break
                snippet = text[max(0, pos-120):min(len(text), pos+220)]
                # Keep only compact string-ish context; remove long encoded blobs.
                snippet = re.sub(r"\s+", " ", snippet)
                snippet = re.sub(r"[A-Za-z0-9+/=_-]{180,}", "<blob>", snippet)
                if len(snippet) <= 500:
                    token_contexts.add(snippet)
                start = pos + len(token)
                hits += 1

    endpoints = sorted(endpoint_strings)
    charging = [e for e in endpoints if "/charging/" in e]
    detail_candidates = [e for e in charging if any(k in e.lower() for k in ("station", "evse", "detail", "tariff", "price"))]
    price_contexts = sorted(c for c in token_contexts if any(t in c.lower() for t in ("tariff", "price", "pricing", "cost", "fee", "rate")))[:300]

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope": "public_frontend_static_asset_endpoint_discovery",
        "security": {
            "credentialsUsed": False,
            "cookiesUsed": False,
            "rawBundlesPersisted": False,
            "onlyEndpointStringsAndBoundedContextsPersisted": True,
        },
        "counts": {
            "scriptAssetsFound": len(srcs),
            "scriptAssetsInspected": len(asset_meta),
            "assetFailures": len(failures),
            "endpointStrings": len(endpoints),
            "chargingEndpointStrings": len(charging),
            "detailCandidateStrings": len(detail_candidates),
            "priceRelatedContexts": len(price_contexts),
        },
        "assets": asset_meta,
        "failures": failures,
        "endpoints": endpoints,
        "chargingEndpoints": charging,
        "detailCandidates": detail_candidates,
        "priceRelatedContexts": price_contexts,
        "nextStepReady": bool(detail_candidates or price_contexts),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(
        "# Enel Italy frontend endpoint discovery\n\n"
        f"- JS assets inspected: **{len(asset_meta)}**\n"
        f"- Charging endpoint strings: **{len(charging)}**\n"
        f"- Station/detail candidates: **{len(detail_candidates)}**\n"
        f"- Price/tariff contexts: **{len(price_contexts)}**\n"
        f"- Ready for targeted detail call: **{'yes' if report['nextStepReady'] else 'no'}**\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "counts": report["counts"],
        "detailCandidates": detail_candidates[:50],
        "priceRelatedContexts": price_contexts[:30],
        "nextStepReady": report["nextStepReady"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
