#!/usr/bin/env python3
"""Probe Qwello Germany public web assets for the location/tariff data source.

The public tariff page is JavaScript-rendered and clearly supports location-
specific pricing. This QA-only probe downloads the HTML and its first-party JS
assets, then records candidate API URLs and contextual snippets around tariff,
pricing, known city and price tokens. It does not publish tariffs to TCC.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

URLS = [
    "https://qwello.de/de/how-to",
    "https://qwello.de/de",
]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
TOKENS = [
    "Altenstadt", "Berlin", "0,49", "0.49", "0,51", "0.51",
    "tariff", "tarif", "pricing", "price", "location", "standort",
    "graphql", "api/", "/api", "firebase", "contentful", "strapi",
]


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/javascript,text/javascript,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
        return raw, {
            "requestedUrl": url,
            "url": r.geturl(),
            "status": getattr(r, "status", 200),
            "contentType": r.headers.get("Content-Type"),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }


def snippets(text: str, token: str, radius=300, limit=12):
    out = []
    low = text.lower(); t = token.lower(); start = 0
    while len(out) < limit:
        i = low.find(t, start)
        if i < 0:
            break
        out.append(text[max(0, i-radius):min(len(text), i+len(token)+radius)])
        start = i + len(token)
    return out


def main():
    pages = []
    asset_urls = []
    for url in URLS:
        raw, meta = fetch(url)
        text = raw.decode("utf-8", "replace")
        pages.append({"meta": meta, "htmlSnippets": {t: snippets(text, t, 240, 4) for t in TOKENS if t.lower() in text.lower()}})
        for src in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text, re.I):
            absolute = urllib.parse.urljoin(meta["url"], html.unescape(src))
            if urllib.parse.urlparse(absolute).netloc.endswith("qwello.de") or urllib.parse.urlparse(absolute).netloc.endswith("qwello.eu"):
                asset_urls.append(absolute)

    asset_urls = list(dict.fromkeys(asset_urls))
    assets = []
    url_candidates = Counter()
    token_hits = Counter()
    for asset_url in asset_urls[:40]:
        try:
            raw, meta = fetch(asset_url)
            if len(raw) > 12_000_000:
                assets.append({"meta": meta, "skipped": "too_large"})
                continue
            text = raw.decode("utf-8", "replace")
            hits = {}
            for token in TOKENS:
                if token.lower() in text.lower():
                    token_hits[token] += 1
                    hits[token] = snippets(text, token, 360, 8)
            candidates = set()
            for pattern in (
                r'https?://[^"\'\s)\\]{5,300}',
                r'["\'](/[^"\']*(?:api|tariff|tarif|price|pricing|location|standort)[^"\']*)["\']',
            ):
                for match in re.finditer(pattern, text, re.I):
                    value = match.group(1) if match.lastindex else match.group(0)
                    value = value.replace("\\/", "/")
                    if len(value) <= 400:
                        candidates.add(value)
            for value in candidates:
                url_candidates[value] += 1
            assets.append({
                "meta": meta,
                "tokenHits": hits,
                "candidateUrls": sorted(candidates)[:300],
            })
        except Exception as exc:
            assets.append({"url": asset_url, "error": f"{type(exc).__name__}: {exc}"})

    result = {
        "schemaVersion": "0.1.0",
        "dataset": "germany-qwello-public-web-probe",
        "generatedAt": now(),
        "scope": {"stagedOnly": True, "publishesToTcc": False, "discoveryOnly": True},
        "pages": pages,
        "scriptAssetCount": len(asset_urls),
        "scriptAssets": assets,
        "tokenAssetHitCounts": dict(token_hits),
        "candidateUrls": [{"value": k, "assets": v} for k, v in url_candidates.most_common(500)],
    }
    out = Path("data/germany/qwello_public_web_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("TCC_QWELLO_WEB_PROBE=" + json.dumps({
        "scriptAssetCount": result["scriptAssetCount"],
        "tokenAssetHitCounts": result["tokenAssetHitCounts"],
        "candidateUrls": result["candidateUrls"][:80],
        "assetSummaries": [
            {"url": (a.get("meta") or {}).get("url") or a.get("url"), "tokens": sorted((a.get("tokenHits") or {}).keys()), "error": a.get("error")}
            for a in assets
        ],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
